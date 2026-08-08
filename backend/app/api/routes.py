"""Rutas HTTP de FeedbackIQ — no bloquean el event loop en trabajos pesados."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app import __version__
from app.api.schemas import AnalyticsRecalcRequest, HealthResponse, ProblemReportRequest
from app.config import get_settings
from app.core.analytics import build_extended_analytics
from app.core.excel_ingest import extract_from_files, validate_upload_meta
from app.core.jobs import JobRequest, get_job, run_pipeline_isolated, submit_analyze_job
from app.core.report_service import submit_problem_report
from app.core.semantic_dedup import encoder_info
from app.core.tokenizer import DEFAULT_MODEL_PRICING
from app.core.translator import engine_info
from app.domains import list_domains

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        ok=True,
        version=__version__,
        tokenizer="o200k_base",
        domains=[d["id"] for d in list_domains()],
    )


@router.get("/engine")
def engine_status():
    settings = get_settings()
    return {
        "translator": engine_info(),
        "embeddings": encoder_info(),
        "limits": {
            "max_sync_rows": settings.MAX_SYNC_ROWS,
            "max_rows": settings.MAX_ROWS,
            "max_upload_mb": settings.MAX_UPLOAD_MB,
            "pipeline_chunk_size": settings.PIPELINE_CHUNK_SIZE,
            "max_heavy_workers": settings.MAX_HEAVY_WORKERS,
        },
    }


@router.get("/domains")
def domains():
    return {"domains": list_domains()}


@router.get("/models")
def models():
    settings = get_settings()
    return {
        "reference_price_per_million": settings.REFERENCE_PRICE_PER_MILLION,
        "default_daily_volume": settings.DEFAULT_DAILY_VOLUME,
        "models": DEFAULT_MODEL_PRICING,
    }


async def _save_uploads(files: list[UploadFile], job_id: str) -> tuple[Path, list[Path]]:
    settings = get_settings()
    tmpdir = Path(tempfile.mkdtemp(prefix=f"fiq_{job_id}_"))
    saved: list[Path] = []
    for uf in files:
        name = uf.filename or "upload.xlsx"
        data = await uf.read()
        err = validate_upload_meta(name, len(data), settings.max_upload_bytes)
        if err:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(400, err)
        dest = tmpdir / Path(name).name
        if dest.exists():
            dest = tmpdir / f"{dest.stem}_{uuid.uuid4().hex[:6]}{dest.suffix}"
        dest.write_bytes(data)
        saved.append(dest)
    if not saved:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(400, "No se pudo guardar ningún archivo")
    return tmpdir, saved


@router.post("/analyze")
async def analyze(
    files: list[UploadFile] = File(..., description="Uno o varios .xlsx"),
    optimize_tokens: bool = Form(True),
    domain: str = Form("reviews"),
    price_per_million: float | None = Form(None),
    daily_volume: int | None = Form(None),
):
    """Analiza Excel.

    - Lotes ≤ MAX_SYNC_ROWS: respuesta síncrona (en thread pool, no bloquea event loop).
    - Lotes mayores: job en segundo plano + job_id (polling /api/jobs/{id}).
    """
    settings = get_settings()
    if not files:
        raise HTTPException(400, "Debes subir al menos un archivo .xlsx")

    job_id = uuid.uuid4().hex[:12]
    tmpdir, saved = await _save_uploads(files, job_id)

    ppm = price_per_million if price_per_million is not None else settings.REFERENCE_PRICE_PER_MILLION
    daily = daily_volume if daily_volume is not None else settings.DEFAULT_DAILY_VOLUME

    # Conteo rápido de filas (streaming) en thread — no bloquea el loop
    try:
        ingest_preview = await asyncio.to_thread(extract_from_files, saved)
    except Exception as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(422, f"No se pudo leer el Excel: {exc}") from exc

    n_rows = ingest_preview.total_rows
    if n_rows == 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(
            422,
            detail={
                "message": ingest_preview.errors[0] if ingest_preview.errors else "No se extrajo texto usable.",
                "errors": ingest_preview.errors,
                "files": [
                    {"filename": f.filename, "rows": f.row_count, "column": f.column_detected, "error": f.error}
                    for f in ingest_preview.files
                ],
            },
        )

    if n_rows > settings.MAX_ROWS:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(
            413,
            detail=(
                f"El archivo tiene ~{n_rows} filas de texto; el máximo soportado es "
                f"{settings.MAX_ROWS}. Divide el archivo o reduce el lote."
            ),
        )

    # Archivo grande → job asíncrono (libera HTTP de inmediato)
    if n_rows > settings.MAX_SYNC_ROWS:
        # Mover tmpdir a ruta estable por job (el worker lo limpiará al final vía paths)
        # Mantener archivos en tmpdir; el job los usa y no los borramos hasta done
        req = JobRequest(
            file_paths=saved,
            optimize_tokens=optimize_tokens,
            domain_id=domain,
            price_per_million=ppm,
            daily_volume=daily,
            job_id=job_id,
        )
        # Guardar tmpdir en el job para cleanup
        from app.core.jobs import _set_job

        submit_analyze_job(req)
        _set_job(job_id, tmpdir=str(tmpdir), rows_estimate=n_rows)

        return JSONResponse(
            status_code=202,
            content={
                "ok": True,
                "async": True,
                "job_id": job_id,
                "rows_estimate": n_rows,
                "message": (
                    f"Archivo grande (~{n_rows} filas). Procesando en segundo plano. "
                    f"Consulta GET /api/jobs/{job_id} cada 1–2 s."
                ),
                "poll_url": f"/api/jobs/{job_id}",
                "status": "queued",
            },
        )

    # Síncrono: aislado en pool (otra request pequeña no espera en el event loop)
    try:
        result = await asyncio.to_thread(
            run_pipeline_isolated,
            file_paths=saved,
            optimize_tokens=optimize_tokens,
            domain_id=domain,
            price_per_million=ppm,
            daily_volume=daily,
            job_id=job_id,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if not result.get("ok"):
        raise HTTPException(
            422 if "error" in result else 503,
            detail={
                "message": result.get("error", "Fallo de procesamiento"),
                "errors": result.get("errors", []),
                "files": result.get("files", []),
            },
        )
    return result


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado o expirado")

    status = job.get("status")
    base = {
        "job_id": job_id,
        "status": status,
        "progress": job.get("progress", 0),
        "message": job.get("message") or job.get("error"),
        "rows_estimate": job.get("rows_estimate"),
        "files": job.get("files"),
    }

    if status == "done" and job.get("result"):
        # Cleanup tmpdir del job
        tmp = job.get("tmpdir")
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
            from app.core.jobs import _set_job

            _set_job(job_id, tmpdir=None)
        return {"ok": True, "async": True, **base, "result": job["result"]}

    if status == "error":
        tmp = job.get("tmpdir")
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        return JSONResponse(
            status_code=200,
            content={"ok": False, "async": True, **base, "error": job.get("error")},
        )

    return {"ok": True, "async": True, **base}


@router.post("/report")
async def problem_report(body: ProblemReportRequest, request: Request):
    """Recibe un reporte del footer y lo reenvía al webhook de n8n.

    Clasifica localmente por reglas (misma lógica que el nodo Code de n8n)
    y hace POST al webhook configurado en N8N_WEBHOOK_URL.
    """
    result = await submit_problem_report(
        body.mensaje,
        page=body.page,
        user_agent=request.headers.get("user-agent"),
        email=body.email,
    )
    if not result.get("ok"):
        raise HTTPException(502 if result.get("n8n_status") else 400, detail=result.get("error") or "No se pudo enviar el reporte")
    return result


@router.get("/report/status")
def report_channel_status():
    """Indica si el canal n8n está configurado (sin filtrar secretos)."""
    settings = get_settings()
    url = (settings.N8N_WEBHOOK_URL or "").strip()
    return {
        "configured": bool(url),
        "dry_run": settings.N8N_DRY_RUN,
        "webhook_host": url.split("/")[2] if url.startswith("http") and len(url.split("/")) > 2 else None,
        "has_secret": bool((settings.N8N_WEBHOOK_SECRET or "").strip()),
    }


@router.post("/analytics/recalculate")
def recalculate_analytics(body: AnalyticsRecalcRequest):
    data = build_extended_analytics(
        tokens_original=body.tokens_original,
        tokens_optimized=body.tokens_optimized,
        item_count=body.item_count,
        optimize_enabled=body.optimize_enabled,
        price_per_million=body.price_per_million,
        daily_volume=body.daily_volume,
    )
    return {"ok": True, "analytics": data}


@router.get("/download/{filename}")
def download(filename: str):
    settings = get_settings()
    safe = Path(filename).name
    if not safe.endswith(".xlsx") or ".." in filename:
        raise HTTPException(400, "Nombre de archivo inválido")
    path = settings.export_path / safe
    if not path.exists():
        raise HTTPException(404, "Archivo no encontrado o expirado")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=safe,
    )
