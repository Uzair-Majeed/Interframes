# InterFrames

InterFrames turns two line drawings into 1, 3, or 7 in-between frames. It includes a React studio, a FastAPI service, a persistent local job queue, and model adapters for the Stage 10 epoch-14 network and AnimeRun GMA.

## Quick start

1. Install Python 3.12+ and Node.js 20+.
2. From the repository root, create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Ensure the three model files exist under `models/` (`Interframes_Model/epoch14.keras`, `GMA_Model/gma.pth`, and `Moderation_Model/moderation.safetensors`); see [Model setup](docs/models.md).
4. Install API and inference dependencies with `python -m pip install -r backend/requirements-ml.txt`, then start the API and worker with `uvicorn app.main:app --app-dir backend --reload`.
5. In a second terminal, run `npm install` and `npm run dev` from `web/`.
6. Open the Vite URL (normally `http://localhost:5173`). The API is at `http://localhost:8000`.

## Docker Compose

Run `docker compose up --build` from the repository root. It starts 5 containers: three model containers (`model-moderation`, `model-gma`, `model-interframes`), the FastAPI `backend`, and the React `web` app; SQLite data and generated files persist in a Docker volume. Open `http://localhost:8080`.

For Kaggle inference, attach a Kaggle input dataset containing `models.zip` and `kaggle_setup.zip` (containing `backend/`):

- [`models.zip`](https://drive.google.com/file/d/1ecLTIFNVF7I8OGS9NeEaVsjV77fsr2xi/view?usp=sharing) — contains `Interframes_Model/epoch14.keras`, `GMA_Model/gma.pth`, and `Moderation_Model/moderation.safetensors`.
- [`kaggle_setup.zip`](https://drive.google.com/file/d/12fEFGe1hIsUNj5zhJ-2fsm9bVvb-tSHD/view?usp=sharing) — contains `backend/app/` source and model configs (or rebuild it locally from `backend/app/`).

Import [the Kaggle gateway notebook](scripts/kaggle_setup.ipynb), run its cells, and copy the printed gateway URL and the same token into `.env`. Then start the app with `docker compose -f docker-compose.yml -f docker-compose.kaggle.yml up --build`. The Kaggle session must stay running; this mode does not require local model weights.

The root `.env` is ignored by Git and holds local credentials and settings. Keep real service tokens there; use `.env.example` as the shareable template. Local Python, Vite, Docker Compose, and the Kaggle setup check read the root environment file.

The local API is single-user and stores jobs, uploaded artwork and generated frames under `backend/data/`. It fails closed when the NSFW classifier is unavailable. Do not expose this development configuration to a network or use it as a hosted multi-user service; see [Deployment and limitations](docs/development.md).

## Project map

- [Backend](backend/README.md): API, persistent jobs, validation and inference.
- [Web app](web/README.md): React/Vite studio and generation history.
- [Model setup](docs/models.md): verified epoch-14 checkpoint and optional model downloads.
- [Implementation specification](implementation.md): full product and model requirements.

The large checkpoint files are ignored by Git. The three model files live in `models/Interframes_Model`, `models/GMA_Model`, and `models/Moderation_Model`.
