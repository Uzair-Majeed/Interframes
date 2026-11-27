# InterFrames Codebase Explanation

This document explains the architecture, application logic, and file-by-file responsibilities of the InterFrames codebase (excluding `notebooks/`).

---

## 1. High-Level Architecture

InterFrames is a local-first line-art frame interpolation application composed of three layers:

1. **Frontend (`web/`)** — A React + TypeScript + Vite single-page studio where users upload start/end drawings, pick `1`, `3`, or `7` in-between frames, preview playback on an HTML5 `<canvas>`, customize ink/background colors and cleanup (`raw`, `crisp` de-halo, or `threshold`), edit the frame sequence (add, move, remove frames), regenerate sequences without re-uploading, manage generation history, and export GIFs or PNG ZIP archives.
2. **Backend API & Worker (`backend/app/`)** — A FastAPI service backed by SQLite (WAL mode) and a background polling worker thread. It validates and moderates uploads, queues generation jobs idempotently, caches GMA motion fields on disk, runs recursive midpoint interpolation, and renders colorized exports.
3. **Model Runtime (`backend/app/models/` + Docker / Kaggle Gateway)** — Supports three execution modes without changing application logic:
   - **In-process local**: Loads Moderation, AnimeRun GMA, and InterFrames Epoch-14 weights directly in the backend process.
   - **Docker Compose (5 containers)**: Runs `model-moderation`, `model-gma`, `model-interframes`, `backend`, and `web`.
   - **Kaggle Gateway + Local Docker (2 containers)**: Runs `backend` and `web` locally while forwarding model calls over HTTPS to a Kaggle notebook running `app/model_gateway.py` behind a Cloudflare Quick Tunnel with bearer-token authentication.

---

## 2. End-to-End Application Flow

```
[StudioPage]
  │ 1. POST /api/v1/assets (Start & End images)
  ▼
[assets.py] -> decode_upload (guardrails.py) -> moderator.score (moderation.py) -> save_upload (storage.py) -> SQLite assets table
  │
  │ 2. POST /api/v1/generations (start_asset_id, end_asset_id, inbetween_count)
  ▼
[generations.py] -> _check_asset_approval -> repositories.create_generation (idempotent) -> returns queued job
  │
  │ 3. Background Worker loop (worker.py)
  ▼
[worker.py] -> claim_generation -> inference.generate():
    - preprocess_image() fits endpoints onto 256x256 white canvas (ink = 1 - gray/255)
    - recursive midpoint(left, right, depth={1|2|3}):
        - _cached_gma_flow(left, right) -> checks ARTIFACTS_DIR/gma_cache/<sha256>.npy or calls gma.bidirectional_low()
        - model.predict(left, right, flow) -> computes 8-channel feature tensor (features.py) -> Keras U-Net logits -> sigmoid
    - saves frame-00.png .. frame-(N+1).png (256x256 grayscale) in ARTIFACTS_DIR/generations/<id>/
    - updates SQLite status = "ready" with result_json
  │
  │ 4. Polling & Preview (GenerationPage -> useGeneration)
  ▼
[CanvasPlayer] -> colorizeFrame() (renderInk.ts) renders grayscale ink with ink/bg colors & raw/crisp/threshold mode
  │
  │ 5. Frame Editing / Regeneration / Export
  ▼
- Regenerate: POST /api/v1/generations with existing start_asset_id & end_asset_id (no re-upload, reuses cached GMA & moderation)
- Add in-between: POST /api/v1/generations/{id}/frames/insert -> interpolate_pair() -> appends new frame PNG
- Export: POST /api/v1/generations/{id}/exports -> build_export() (render.py) -> GIF or PNG ZIP
```

---

## 3. Repository Root Files

- **`README.md`**: Setup instructions for local Python/Node, Docker Compose, and Kaggle hybrid mode (including `models.zip` and `kaggle_setup.zip` download links).
- **`docker-compose.yml`**: Defines the 5-service stack (`model-moderation`, `model-gma`, `model-interframes`, `backend`, `web`), persistent `interframes_data` volume, and model-service environment variables.
- **`docker-compose.kaggle.yml`**: Compose override that disables the 3 local model containers (`profiles: ["local-models"]`) and points `backend` to `KAGGLE_MODEL_GATEWAY_URL` (`/moderation`, `/gma`, `/interframes`) using `KAGGLE_MODEL_SERVICE_TOKEN`.
- **`.env` / `.env.example`**: Local environment variables (`KAGGLE_MODEL_GATEWAY_URL`, `KAGGLE_MODEL_SERVICE_TOKEN`, ports, paths).
- **`implementation.md`**: Full product and technical specification.
- **`scripts/kaggle_setup.ipynb`**: Interactive Kaggle notebook that extracts `models.zip` and `kaggle_setup.zip`, verifies SHA-256 checksums of all three weights, launches `app.model_gateway:app`, and opens a Cloudflare Quick Tunnel.

---

## 4. Backend (`backend/`)

### Configuration, Schemas, and Entrypoints
- **`backend/app/config.py`**: Centralizes paths (`MODELS_DIR`, `DATA_DIR`, `ARTIFACTS_DIR`, `DATABASE_PATH`), upload limits (`MAX_UPLOAD_BYTES`, `MAX_IMAGE_PIXELS`), moderation threshold/policy version, pinned SHA-256 digests (`MODEL_SHA256`, `GMA_DIR`), and optional remote service URLs (`MODERATION_SERVICE_URL`, `GMA_SERVICE_URL`, `INTERFRAMES_SERVICE_URL`).
- **`backend/app/schemas.py`**: Pydantic models for API contracts:
  - `AssetResponse`: Uploaded image metadata (`id`, `preview_url`, `width`, `height`, `sha256`).
  - `GenerationInput`: `start_asset_id`, `end_asset_id`, `inbetween_count` (`1`, `3`, or `7`).
  - `FrameExportStyle` & `ExportInput`: Format (`gif` | `png_zip`), dimensions, FPS, `ink_color`, `background_color`, `cutoff`, `cutoff_mode` (`raw` | `threshold` | `crisp`), per-frame `frame_styles`, and optional ordered `frame_indices`.
  - `InsertFrameInput`: `left_index` and `right_index` for inserting a new frame between two existing frames.
  - `ErrorResponse`: Standard `{code, detail}` error payload.
- **`backend/app/main.py`**: Initializes the FastAPI app, runs `session.initialize()` and starts/stops the background worker in `lifespan`, configures CORS for `localhost:5173`, mounts `assets` and `generations` routers under `/api/v1`, and exposes `GET /health`.
- **`backend/app/worker.py`**: Daemon thread polling `repositories.claim_generation()` every 0.75s, running `inference.generate()`, handling cancellation (`GenerationCancelled`) and model errors, and persisting terminal statuses (`ready`, `cancelled`, `failed`).
- **`backend/app/model_service.py`**: Standalone HTTP microservice wrapper used by the 3 Docker model containers (`MODEL_SERVICE_KIND=moderation|gma|interframes`), exposing `/health` and `/predict`.
- **`backend/app/model_gateway.py`**: Single-process FastAPI gateway used on Kaggle. Loads all 3 models at startup, enforces `Authorization: Bearer <MODEL_SERVICE_TOKEN>` via constant-time `hmac.compare_digest`, and exposes `/{kind}/health` and `/{kind}/predict`.
- **`backend/app/wait_for_models.py`**: Startup pre-flight script for the `backend` Docker container; polls configured model service `/health` endpoints until all are ready (up to 30 minutes).

### Database (`backend/app/database/`)
- **`backend/app/database/session.py`**: Defines the SQLite schema (`assets`, `generations`, `exports`), creates `DATABASE_PATH` on startup, and provides a `connect()` context manager with `WAL` mode and `IMMEDIATE` transactions.
- **`backend/app/database/repositories.py`**: All SQL queries:
  - Assets: `create_asset`, `get_asset`, `update_asset_moderation`.
  - Generations: `create_generation` (idempotent via `(owner_id, idempotency_key)`), `get_generation`, `list_generations` (keyset cursor pagination), `claim_generation` (atomic `queued` -> `running`), `update_generation`, `generation_request`, `request_cancel`, `remove_generation`.
  - Exports: `create_export`, `update_export`, `get_export`, `export_paths`.

### API Routes (`backend/app/api/`)
- **`backend/app/api/assets.py`**:
  - `POST /api/v1/assets`: Validates static PNG/JPEG/WebP via `decode_upload()`, scores NSFW probability via `moderator.score()` (fails closed with `503` if unavailable, `422` if blocked), saves normalized PNG, and records it in SQLite.
  - `GET /api/v1/assets/{asset_id}/preview`: Serves the stored endpoint PNG.
- **`backend/app/api/generations.py`**:
  - `POST /api/v1/generations`: Requires `Idempotency-Key`, verifies both assets exist and pass the current `MODERATION_POLICY_VERSION` (without re-running moderation if already approved under the current version), and queues the job. Returns `start_asset_id` and `end_asset_id` in `_public_generation`.
  - `GET /api/v1/generations`: Paginated history list.
  - `GET /api/v1/generations/{id}`: Job status, progress, frame URLs, warnings, and asset IDs.
  - `GET /api/v1/generations/{id}/frames/{frame_index}`: Serves an individual raw grayscale PNG frame.
  - `POST /api/v1/generations/{id}/frames/insert`: Runs `interpolate_pair()` between `left_index` and `right_index`, saves the new PNG frame, updates `result_json`, and returns `{index, url}`.
  - `POST /api/v1/generations/{id}/cancel`: Requests cancellation.
  - `DELETE /api/v1/generations/{id}`: Deletes the DB row and cleans up frame and export files from disk.
  - `POST /api/v1/generations/{id}/exports` & `GET .../exports/{export_id}/download`: Renders GIF or PNG ZIP using `build_export()` (respecting `frame_indices` and per-frame `frame_styles`) and serves the file.

### Services (`backend/app/services/`)
- **`backend/app/services/guardrails.py`**: Enforces MIME type (`PNG`, `JPEG`, `WebP`), byte and pixel limits, rejects animated inputs and decompression bombs, applies EXIF transpose, composites transparency onto white, and computes a canonical pixel SHA-256.
- **`backend/app/services/storage.py`**: Atomically writes uploaded PNGs (`.part` -> `os.replace`) into `ARTIFACTS_DIR/assets/` and safely removes artifact paths.
- **`backend/app/services/model_clients.py`**: Lightweight `urllib` JSON client + base64 PNG/NumPy array serialization for calling Docker or Kaggle model services with bearer auth.
- **`backend/app/services/features.py`**: Builds the 8-channel `(256, 256, 8)` float32 input tensor for InterFrames from `(start, end, low_flow)`:
  1. `upsample_low()` scales GMA's `32x32` flow to `256x256` (`* 8.0`).
  2. `forward_splat()` bilinearly splats start/end ink along forward/backward flows, producing warped ink and binary coverage maps.
  3. `distance_map()` computes normalized Euclidean distance transforms (`scipy.ndimage.distance_transform_edt`, capped at radius 32).
  4. Stacks `[start, end, warped_start, warped_end, dist_start, dist_end, cov_start, cov_end]`.
- **`backend/app/services/inference.py`**:
  - `_cached_gma_flow()`: Computes SHA-256 of the `(left, right)` pair and caches `2x32x32x2` GMA flow fields on disk (`ARTIFACTS_DIR/gma_cache/`) so regenerations and frame insertions reuse cached motion without re-running GMA.
  - `generate()`: Runs recursive binary midpoint subdivision (`depth=1, 2, or 3` for `1, 3, or 7` frames), validates finite `[0, 1]` outputs, saves grayscale PNGs (`1 - ink`), and emits quality warnings if frames are nearly empty or oversaturated.
  - `interpolate_pair()`: Generates a single in-between frame between two existing frame files.
- **`backend/app/services/render.py`**:
  - `crisp_ink()` & `_separable_gaussian()`: Post-processing de-halo filter that subtracts a wide Gaussian halo (`sigma=3.0`, `radius=6`) to preserve thin line ridges and dark stroke cores while suppressing low-confidence motion blur.
  - `render_frame()`: Applies `raw`, `crisp`, or `threshold` cutoff, colorizes ink/background via `ImageOps.colorize`, and Lanczos-resizes to export dimensions.
  - `build_export()`: Packages rendered frames into an animated GIF (`disposal=2`) or numbered PNG ZIP archive, mapping `frame_styles` by original frame index.

### Model Adapters (`backend/app/models/`)
- **`backend/app/models/moderation.py`**: Loads a local HuggingFace image classification model (`moderation.safetensors` + `moderation_config/`) on CPU (or calls `MODERATION_SERVICE_URL`) and returns `(nsfw_probability, blocked)`.
- **`backend/app/models/gma.py`**: Verifies `gma.pth` SHA-256, loads `RAFTGMA` from `gma_config/` on CPU (or calls `GMA_SERVICE_URL`), and estimates bidirectional `32x32` float16 optical flow (`iters=12`).
- **`backend/app/models/interframes.py`**: Verifies `epoch14.keras` against `interframes_protocol.json` SHA-256, loads the Keras U-Net (or calls `INTERFRAMES_SERVICE_URL`), runs inference on the 8-channel feature tensor, applies sigmoid to logits, and provides `preprocess_image()`.
- **`backend/app/models/gma_config/` & `moderation_config/` & `interframes_protocol.json`**: Pinned model architectures, configs, and checksums.

---

## 5. Frontend (`web/`)

- **`web/package.json` & `vite.config.ts`**: React 19, `react-router-dom`, TypeScript, and Vite dev proxy forwarding `/api` to the backend.
- **`web/nginx.conf` & `web/Dockerfile`**: Builds static assets and serves them via Nginx in Docker, proxying `/api/` requests to `backend:8000`.
- **`web/src/main.tsx` & `web/src/router.tsx`**: Mounts `BrowserRouter` with routes `/studio`, `/studio/:id`, and `/history`.
- **`web/src/lib/api.ts`**: Typed fetch wrapper for assets, generations, regeneration (`regenerateGeneration` reusing `start_asset_id`/`end_asset_id`), frame insertion (`insertFrame`), cancellation, deletion, and exports.
- **`web/src/lib/renderInk.ts`**: Client-side `<canvas>` pixel processor matching the backend's `render.py` (`raw`, `threshold`, and `crisp` separable-Gaussian de-halo modes + hex ink/background colorization).
- **`web/src/hooks/useGeneration.ts`**: Polls `GET /api/v1/generations/{id}` every 900ms while `queued` or `running`, stopping on terminal states.
- **`web/src/pages/StudioPage.tsx`**: Upload workspace for Start (A) and End (B) drawings, swap button, sequence length selector (`CustomizationPanel`), and empty preview player.
- **`web/src/pages/GenerationPage.tsx`**: Displays live job progress, cancellation, interactive `CanvasPlayer` with per-frame style & sequence editing (move, remove, add in-between), `CustomizationPanel` configured for **Regenerate frames** without re-upload, model details, and `ExportDialog`.
- **`web/src/pages/HistoryPage.tsx` & `web/src/components/history/` (`GenerationList.tsx`, `GenerationRow.tsx`)**: Paginated generation history with status badges, thumbnails, quick **↺ Regenerate** navigation, and **× Delete** with confirmation.
- **`web/src/components/studio/`**:
  - `EndpointUpload.tsx`: File picker & upload status card for endpoint A/B.
  - `CustomizationPanel.tsx`: Reusable `1 / 3 / 7` in-between frame selector and Generate/Regenerate action button.
  - `CanvasPlayer.tsx`: Real-time `<canvas>` animation player with play/pause, scrubber, FPS slider, zoom controls, thumbnail strip, frame editing bar (move left/right, add in-between, remove), and per-frame or global ink/background/cutoff controls.
  - `ExportDialog.tsx`: Export modal inheriting the preview's ink, background, cutoff, and edited frame order, prompting only for width/height (and FPS for GIFs).
- **`web/src/styles.css`**: Dark-theme studio layout, responsive grids, player controls, modal styling, and history table styles.
