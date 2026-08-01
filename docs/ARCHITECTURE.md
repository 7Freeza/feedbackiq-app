# FeedbackIQ — Architecture

## Purpose

FeedbackIQ is a web application that:

1. Ingests one or more Excel (`.xlsx`) files containing free-text rows (reviews, clauses, incidents, etc.).
2. Counts tokens **exactly** with `tiktoken` encoding `o200k_base`.
3. Optionally optimizes token cost via **local neural ES→EN translation** (CTranslate2 + OPUS-MT int8).
4. Classifies each row into a **structured JSON** schema using domain rule packs.
5. Exports a clean Excel and surfaces **savings analytics** (multi-model cost, 30-day projection, break-even).

Design priority: **measurable token savings**, **sub-2s core path** for normal batches, and **backend stability** under large files.

---

## High-level system

```
┌─────────────┐     proxy /api      ┌──────────────────┐
│  Vite UI    │ ──────────────────► │  FastAPI (uvicorn)│
│  :5173      │ ◄────────────────── │  :4004            │
└─────────────┘   JSON + XLSX      └────────┬─────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    ▼                        ▼                        ▼
             excel_ingest            translator (CT2)           domains/*
             (openpyxl/pandas)       opus-mt-es-en int8         rules packs
                    │                        │                        │
                    └────────────► pipeline ◄─┴────────────────────────┘
                                       │
                         tokenizer · classifier · export · analytics
                                       │
                                       ▼
                              exports/feedbackiq_*.xlsx
```

---

## Request lifecycle

### Synchronous path (≤ `MAX_SYNC_ROWS`, default 3 000)

1. `POST /api/analyze` receives multipart files.
2. Files are validated and written to a temp directory.
3. A fast ingest pass estimates row count.
4. Heavy work runs in a **thread pool** (`asyncio.to_thread` + semaphore) so the event loop stays responsive.
5. Response includes core KPIs, timings, preview rows, analytics, and download URL.

### Asynchronous path (> `MAX_SYNC_ROWS`, ≤ `MAX_ROWS` = 50 000)

1. API returns **HTTP 202** with `job_id` and `poll_url`.
2. Work runs in `ThreadPoolExecutor` (`app/core/jobs.py`).
3. Frontend polls `GET /api/jobs/{job_id}` until `status=done|error`.

### Isolation guarantees

- Pipeline objects are discarded after each job; large batches trigger `gc.collect()`.
- Translation cache is an **LRU** (bounded), not unbounded accumulation.
- Dictionary “comparison (a)” uses a **sample** (≤200 rows), not a second full CT2 pass.

---

## Core modules (`backend/app/core/`)

| Module | Responsibility |
|--------|----------------|
| `excel_ingest.py` | Column detection, junk filtering, streaming `read_only` for larger files, batch multi-file |
| `tokenizer.py` | `o200k_base` counts, multi-model USD pricing table |
| `translator.py` | CTranslate2 OPUS-MT ES→EN, int8 CPU, LRU cache, dictionary fallback only if model missing |
| `optimizer.py` | Legacy dictionary ES→EN (comparison / emergency fallback) |
| `semantic_dedup.py` | Exact MD5 dedup always; semantic (model2vec) only if ≥40 unique texts |
| `classifier.py` | Applies domain `rules_fn` → structured dict + `_method` |
| `pipeline.py` | Orchestrates ingest → dedup → tokenize → (opt) translate → classify → export → analytics |
| `export.py` | openpyxl workbook with domain-specific columns |
| `analytics.py` | Batch savings, 30-day series, break-even, stage timings, model table |
| `jobs.py` | In-memory job registry + heavy worker pool |

---

## Domains (`backend/app/domains/`)

Domain **does not** change tokenization or translation. It only changes:

- Rule keywords → classification fields
- Excel/JSON column set (`error_type` vs `clause_type` vs `incident_type`, etc.)

| ID | Use case | Primary fields |
|----|----------|----------------|
| `reviews` | App Store / Play feedback | `error_type`, `component`, `severity`, `sentiment`, `summary` |
| `contracts` | Lease / legal snippets | `clause_type`, `amount_hint`, `date_hint`, `severity`, `summary` |
| `incidents` | Support / scheduling | `incident_type`, `priority`, `department`, `summary` |

---

## Frontend (`frontend/`)

| Piece | Role |
|-------|------|
| Vite | Dev server + proxy `/api` → `:4004` |
| Hash router | `#/` analyze, `#/docs` method page |
| Chart.js | Model cost bars, 30-day line, stage bars, type distribution |
| Design | “Vacío numérico”: void background, mint savings, mono tabular numbers, no glassmorphism |

Progressive disclosure: **core KPIs first**, then analytics panel.

---

## Configuration (`app/config.py`)

| Setting | Default | Meaning |
|---------|---------|---------|
| `PORT` | 4004 | API port |
| `MAX_UPLOAD_MB` | 80 | Upload size cap |
| `MAX_SYNC_ROWS` | 3000 | Sync response threshold |
| `MAX_ROWS` | 50000 | Hard row cap |
| `PIPELINE_CHUNK_SIZE` | 500 | Translate/tokenize batch size |
| `MAX_HEAVY_WORKERS` | 2 | Concurrent heavy jobs |
| `REFERENCE_PRICE_PER_MILLION` | 2.50 | Default USD / MTok |
| `TOKENIZER_ENCODING` | o200k_base | tiktoken encoding |

---

## Translation engine

- Model directory: `backend/models/opus-mt-es-en-ct2` (CTranslate2 export of OPUS-MT es→en).
- Loaded once at process startup (`lifespan` warm-up).
- Requires `</s>` on source SPM pieces; otherwise Marian decoding can loop.
- Reported savings to the user always use **CT2 path (b)**, never the dictionary stub.

---

## Failure modes

| Condition | Behavior |
|-----------|----------|
| Corrupt / empty Excel | Per-file error; batch continues for other files |
| No text column | Actionable 422 message |
| CT2 model missing | Dictionary fallback + engine status reflects it |
| > MAX_ROWS | HTTP 413 with clear limit message |
| Heavy queue full | Job/error: wait and retry |

---

## Non-goals

- Cloud translation APIs on the critical path.
- Full LLM classification by default (rules first; method is transparent).
- Multi-process job store without Redis (in-memory jobs require `UVICORN_WORKERS=1`).
