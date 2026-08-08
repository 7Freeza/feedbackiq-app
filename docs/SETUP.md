# FeedbackIQ — Setup Guide

## Requirements

- **Python** 3.11+ (3.12–3.14 tested in development)
- **Node.js** 18+ and npm
- **Disk** ~200–400 MB free for the CTranslate2 model (first download)
- **RAM** 8 GB+ recommended when processing large Excel batches with CT2

No GPU required. No paid translation API required.

---

## 1. Clone

```bash
git clone https://github.com/7Freeza/feedbackiq-app.git
cd feedbackiq-app
```

---

## 2. Install dependencies

From the monorepo root:

```bash
npm install
npm run setup
```

This creates `backend/.venv`, installs Python requirements, and installs the frontend packages.

Manual alternative:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ../frontend
npm install
```

---

## 3. Download the translation model (once)

The neural ES→EN engine expects weights at:

```text
backend/models/opus-mt-es-en-ct2/
```

If missing, download the pre-converted CTranslate2 checkpoint:

```bash
cd backend
.venv/bin/python - <<'PY'
from pathlib import Path
from huggingface_hub import snapshot_download

dest = Path("models/opus-mt-es-en-ct2")
if not (dest / "model.bin").exists():
    snapshot_download(
        repo_id="gaudi/opus-mt-es-en-ctranslate2",
        local_dir=str(dest),
    )
    print("Model ready:", dest)
else:
    print("Already present:", dest)
PY
```

Optional: set `FEEDBACKIQ_CT2_MODEL=/absolute/path/to/ct2/dir`.

Without the model, the API still starts, but optimization falls back to the **dictionary** path (not professional savings reporting).

---

## 4. Run (development)

**Recommended — both processes:**

```bash
cd FeedBackIQ
npm run dev
```

| Service | URL |
|---------|-----|
| UI (Vite) | http://localhost:5173 |
| API | http://127.0.0.1:4004 |
| API docs (OpenAPI) | http://127.0.0.1:4004/docs |

Vite proxies `/api` → backend `:4004` (`frontend/vite.config.js`).

**Backend only:**

```bash
cd backend && .venv/bin/python run.py
```

**Frontend only:**

```bash
cd frontend && npm run dev
```

---

## 5. Sample data

| File | Description |
|------|-------------|
| `samples/reviews_sample.xlsx` | Spanish app reviews |
| `samples/contracts_sample.xlsx` | Lease-clause style text |

---

## 6. Environment (optional)

Copy `backend/.env.example` → `backend/.env`:

```env
PORT=4004
CORS_ORIGIN=http://localhost:5173
MAX_UPLOAD_MB=80
MAX_SYNC_ROWS=3000
MAX_ROWS=50000
REFERENCE_PRICE_PER_MILLION=2.50
```

---

## 7. Port already in use

```bash
fuser -k 4004/tcp
fuser -k 5173/tcp
```

Then run `npm run dev` again.

---

## 8. Reportes de problemas (n8n)

El footer de la UI envía reportes a `POST /api/report`, que reenvía a un webhook de n8n.

1. Instala/arranca n8n (Docker) — ver **[N8N_REPORTES.md](N8N_REPORTES.md)**.
2. Crea el workflow y copia la Production URL del Webhook.
3. Configura en `backend/.env`:

```env
N8N_DRY_RUN=false
N8N_WEBHOOK_URL=http://localhost:5678/webhook/feedbackiq-report
N8N_WEBHOOK_SECRET=tu-secreto
```

Sin n8n aún, puedes probar el formulario con `N8N_DRY_RUN=true`.

---

## 9. Production notes

- Keep `UVICORN_WORKERS=1` while jobs are in-memory (`jobs.py`). Multi-worker needs a shared job store (Redis/RQ).
- Do not commit `backend/models/**/model.bin` or `node_modules` / `.venv`.
- For 50k-row files, expect async jobs (HTTP 202 + polling), not a 2-second sync response.
