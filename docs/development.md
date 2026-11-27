# Local development and deployment limits

## Local runtime

The API uses a persistent SQLite database at `backend/data/interframes.sqlite3`, a local worker thread, and private artifact directories under `backend/data/`. Override them with `DATABASE_PATH`, `ARTIFACTS_DIR`, and `CACHE_DIR`. Uploads are moderated before a durable asset ID or preview is returned. Per-user identity is intentionally fixed to one local workspace.

Start the API from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-ml.txt
uvicorn app.main:app --app-dir backend --reload
```

Start the web studio in another terminal:

```powershell
cd web
npm install
npm run dev
```

The worker and API run in one process for local development. GMA and TensorFlow are loaded lazily at first inference. The `/health` endpoint indicates whether the expected model files are present.

## Security and production scope

This repository is a local single-user application, not a hosted multi-account service. There is no login, signed-in owner model, PostgreSQL deployment, external object store, cross-process job lease, cache eviction policy, or hosted worker configuration in this implementation. The API binds to a local development interface by default. Do not expose it to untrusted clients or use it for multi-user deployment. Before hosting, implement authenticated owner-scoped access across assets, jobs and exports; migrate persistence to PostgreSQL; add lease/heartbeat semantics and private object storage; and restrict API/worker network access.

Input validation limits file size and decoded pixel count, accepts only supported static image formats, strips EXIF orientation metadata by canonicalizing pixels, . Moderation is fail-closed. Artifacts remain private behind API routes; filenames and artwork are not logged.

## Implemented and deferred spec items

Implemented: upload validation and explicit-image moderation; persistent local queue and cursor-paginated history; epoch-14 + GMA inference; 1/3/7 recursively subdivided frames; live preview palette, cutoff, width and playback controls; cancellation and GIF/PNG ZIP exports; local setup checks.

Deferred: PostgreSQL and hosted multi-user operation; production authentication and object storage; cache eviction and a generation-level cache policy (the optional Redis model-call cache uses a 24-hour TTL); formal moderation-threshold calibration and notebook parity/quality benchmarks; hosted deployment automation.

## Configuration

The backend and Vite development server read settings from the root `.env` when present. Docker Compose also reads this file for variable substitution. Start from `.env.example`; keep real tokens only in the ignored `.env` file.

| Variable | Default | Description |
|---|---|---|
| `MODEL_DIR` | repository `models/` | Model artifact directory |
| `MODERATION_DIR` | `models/Moderation_Model/` | Local pinned classifier weights |
| `GMA_DIR` | `backend/app/models/gma_core/` | Pinned GMA inference source |
| `DATABASE_PATH` | `backend/data/interframes.sqlite3` | Local durable SQLite database |
| `ARTIFACTS_DIR` | `backend/data/artifacts/` | Private uploaded and generated files |
| `CACHE_DIR` | `backend/data/cache/` | Local artifact cache directory |
| `REDIS_URL` | empty | Optional Redis cache for model predictions |
| `MODERATION_THRESHOLD` | `0.5` | NSFW probability blocking threshold |
| `MAX_UPLOAD_BYTES` | `12582912` | Maximum encoded upload size |
| `MAX_IMAGE_PIXELS` | `20000000` | Maximum decoded image pixel count |
