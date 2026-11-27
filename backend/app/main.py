"""Configure the FastAPI app, its startup lifecycle, and model health checks."""
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, generations
from app.config import (
    ARTIFACTS_DIR,
    GMA_DIR,
    GMA_SERVICE_URL,
    INTERFRAMES_SERVICE_URL,
    MODEL_SERVICE_TOKEN,
    MODERATION_SERVICE_URL,
)
from app.database.session import initialize
from app.models.gma import CHECKPOINT
from app.models.interframes import MODEL_PATH, PROTOCOL_PATH
from app.models.moderation import model_status
from app.worker import start_worker, stop_worker


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Prepare local storage and start the queue worker alongside the API.
    initialize()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    start_worker()
    try:
        yield
    finally:
        stop_worker()


app = FastAPI(title="InterFrames API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
app.include_router(assets.router, prefix="/api/v1")
app.include_router(generations.router, prefix="/api/v1")


@app.get("/health")
def health():
    """Report which model files or model-service endpoints are available."""
    models = model_status()
    models["interframes"] = _service_ready(INTERFRAMES_SERVICE_URL) if INTERFRAMES_SERVICE_URL else MODEL_PATH.is_file() and PROTOCOL_PATH.is_file()
    models["gma"] = _service_ready(GMA_SERVICE_URL) if GMA_SERVICE_URL else CHECKPOINT.is_file() and (GMA_DIR / "network.py").is_file()
    models["moderation"] = _service_ready(MODERATION_SERVICE_URL) if MODERATION_SERVICE_URL else models["moderation"]
    return {"status": "ok", "models": models}


def _service_ready(base_url: str) -> bool:
    """Probe a model container without failing the whole health response."""
    try:
        headers = {"Authorization": f"Bearer {MODEL_SERVICE_TOKEN}"} if MODEL_SERVICE_TOKEN else {}
        from urllib.request import Request

        with urlopen(Request(f"{base_url.rstrip('/')}/health", headers=headers), timeout=2) as response:
            return response.status == 200
    except Exception:
        return False
