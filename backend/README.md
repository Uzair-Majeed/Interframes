# InterFrames API

FastAPI handles image uploads, moderation, generation history, cancellation, and exports. A background worker runs GMA motion guidance and the epoch-14 InterFrames model, then saves grayscale PNG frames.

## Run locally

From the repository root:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-ml.txt
uvicorn app.main:app --app-dir backend --reload
```

Set `DATABASE_PATH`, `ARTIFACTS_DIR`, `MODEL_DIR`, `MODERATION_DIR`, and `GMA_DIR` to override defaults (`GMA_DIR` defaults to `backend/app/models/gma_config`). Uploads are limited to PNG/JPEG/WebP, 12 MiB, and 20 megapixels. The API is a local single-user app; do not expose it to untrusted clients.

## API

All routes are under `/api/v1`.

- `POST /assets` ? upload and moderate an image.
- `POST /generations` ? create an idempotent 1/3/7-frame generation.
- `GET /generations` and `GET /generations/{id}` ? list and poll history.
- `POST /generations/{id}/cancel` and `DELETE /generations/{id}` ? cancel or remove a generation.
- `POST /generations/{id}/exports` ? render a GIF or numbered PNG ZIP.

## Models

`models/Interframes_Model/epoch14.keras` is the only in-between generator. GMA estimates motion for each interval. The local and remote model health checks cover epoch14, GMA, and moderation.
