# FeedbackIQ — HTTP API Reference

Base URL (dev): `http://127.0.0.1:4004`  
Via Vite proxy: `http://localhost:5173/api/...`

All JSON responses use UTF-8. File uploads use `multipart/form-data`.

---

## Health & metadata

### `GET /api/health`

```json
{
  "ok": true,
  "version": "1.0.0",
  "tokenizer": "o200k_base",
  "domains": ["reviews", "contracts", "incidents"]
}
```

### `GET /api/engine`

Translator readiness, embedding status, and runtime limits (`max_sync_rows`, `max_rows`, etc.).

### `GET /api/domains`

List of classification presets with labels and result keys.

### `GET /api/models`

Reference price table used for multi-model cost comparison.

---

## Analyze

### `POST /api/analyze`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `files` | file[] | required | One or more `.xlsx` / `.xls` |
| `optimize_tokens` | bool | `true` | Run CT2 ES→EN optimization |
| `domain` | string | `reviews` | `reviews` \| `contracts` \| `incidents` |
| `price_per_million` | float | settings | USD per million tokens |
| `daily_volume` | int | 10000 | Projection volume |

#### Sync success (`200`)

Body includes:

- `ok`, `job_id`
- `core` — tokens, savings, elapsed_ms, `within_sla`, download URL, method labels
- `timings` — stage latencies (ms)
- `files` — per-file column detection / errors
- `results_preview` — up to 50 rows
- `analytics` — projections, models, break-even, comparisons a/b/c
- `translator` — engine info

#### Async accepted (`202`)

When estimated rows **> `MAX_SYNC_ROWS`**:

```json
{
  "ok": true,
  "async": true,
  "job_id": "a1b2c3d4e5f6",
  "rows_estimate": 12000,
  "poll_url": "/api/jobs/a1b2c3d4e5f6",
  "status": "queued",
  "message": "…"
}
```

#### Errors

| Code | Meaning |
|------|---------|
| 400 | Invalid file type/size |
| 413 | Above `MAX_ROWS` |
| 422 | No usable text / corrupt Excel |
| 503 | Heavy queue unavailable |

---

## Jobs

### `GET /api/jobs/{job_id}`

| `status` | Meaning |
|----------|---------|
| `queued` | Waiting for worker |
| `running` | Pipeline executing |
| `done` | `result` present (full analyze payload) |
| `error` | `error` message set |

---

## Analytics recalculation

### `POST /api/analytics/recalculate`

JSON body:

```json
{
  "tokens_original": 7159,
  "tokens_optimized": 6040,
  "item_count": 500,
  "optimize_enabled": true,
  "price_per_million": 2.5,
  "daily_volume": 10000
}
```

Returns refreshed `analytics` without re-ingesting Excel.

---

## Download

### `GET /api/download/{filename}`

Returns the generated `.xlsx` (`Content-Type: spreadsheetml`). Filename is path-safe (basename only).

---

## Example (curl)

```bash
# Sync small batch
curl -s -X POST http://127.0.0.1:4004/api/analyze \
  -F "files=@samples/reviews_sample.xlsx" \
  -F "optimize_tokens=true" \
  -F "domain=reviews" \
  -F "price_per_million=2.50" \
  -F "daily_volume=10000" | jq '.core'

# Download (use export_filename from response)
curl -OJ http://127.0.0.1:4004/api/download/feedbackiq_XXXXXXXXXXXX.xlsx
```

---

## Row result shape (preview)

```json
{
  "source": "reviews.xlsx",
  "text": "La app se cierra…",
  "text_optimized": "The app closes…",
  "tokens_original": 24,
  "tokens_optimized": 18,
  "savings_tokens": 6,
  "optimized": true,
  "optimize_method": "ctranslate2",
  "method": "rules",
  "classification": {
    "error_type": "crash",
    "component": "app_core",
    "severity": "high",
    "sentiment": "negative",
    "summary": "App crashes unexpectedly during use.",
    "_method": "rules"
  }
}
```
