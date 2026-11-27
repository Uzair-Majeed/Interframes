"""Serve the three model adapters behind one authenticated HTTP origin."""
import base64
import hmac
import io
import os
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PIL import Image


MODEL_KINDS = {"moderation", "gma", "interframes"}
SERVICE_TOKEN = os.getenv("MODEL_SERVICE_TOKEN", "")


class Prediction(BaseModel):
    """Fields accepted by the model-specific prediction routes."""

    image: str | None = None
    start: str | None = None
    end: str | None = None
    flow: str | None = None


def _model(kind: str):
    """Import only the selected adapter so each path uses the right weights."""
    if kind == "moderation":
        from app.models.moderation import moderator

        return moderator
    if kind == "gma":
        from app.models.gma import gma

        return gma
    if kind == "interframes":
        from app.models.interframes import model

        return model
    raise HTTPException(404, detail="Unknown model route.")


def _image(encoded: str) -> Image.Image:
    """Decode a base64 image sent by the backend client."""
    try:
        raw = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            return image.convert("RGB")
    except Exception as exc:
        raise HTTPException(422, detail="Invalid encoded image.") from exc


def _array(encoded: str, shape: tuple[int, ...], dtype: str) -> np.ndarray:
    """Decode a tensor and enforce the expected shape and finite values."""
    try:
        raw = base64.b64decode(encoded, validate=True)
        value = np.frombuffer(raw, dtype=dtype).reshape(shape).copy()
    except Exception as exc:
        raise HTTPException(422, detail="Invalid encoded model input.") from exc
    if not np.isfinite(value).all():
        raise HTTPException(422, detail="Model input contains non-finite values.")
    return value


def _encoded(value: np.ndarray) -> str:
    """Encode a contiguous tensor for the backend's JSON client."""
    return base64.b64encode(np.ascontiguousarray(value).tobytes()).decode("ascii")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load all model weights before the gateway becomes reachable."""
    if not SERVICE_TOKEN:
        raise RuntimeError("Set MODEL_SERVICE_TOKEN before exposing the model gateway.")
    for kind in sorted(MODEL_KINDS):
        _model(kind)._load()
    yield


app = FastAPI(
    title="InterFrames Kaggle Model Gateway",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def require_service_token(request: Request, call_next):
    """Require the shared bearer token on every tunneled request."""
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {SERVICE_TOKEN}"
    if not SERVICE_TOKEN or not hmac.compare_digest(supplied, expected):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized."})
    return await call_next(request)


@app.get("/{kind}/health")
def health(kind: str):
    """Report readiness for one adapter after startup loaded its weights."""
    if kind not in MODEL_KINDS:
        raise HTTPException(404, detail="Unknown model route.")
    return {"status": "ok", "model": kind}


@app.post("/{kind}/predict")
def predict(kind: str, payload: Prediction):
    """Dispatch one request to its model and return the shared wire format."""
    model = _model(kind)
    try:
        if kind == "moderation" and payload.image:
            score, blocked = model.score(_image(payload.image))
            return {"score": score, "blocked": blocked}
        if kind == "gma" and payload.start and payload.end:
            flow = model.bidirectional_low(_image(payload.start), _image(payload.end))
            return {"flow": _encoded(flow.astype("<f2"))}
        if kind == "interframes" and payload.start and payload.end and payload.flow:
            ink = model.predict(
                _array(payload.start, (256, 256), "<f4"),
                _array(payload.end, (256, 256), "<f4"),
                _array(payload.flow, (2, 32, 32, 2), "<f2"),
            )
            return {"ink": _encoded(ink.astype("<f4"))}
        raise HTTPException(422, detail=f"Invalid request for the {kind} model.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, detail=f"{kind} prediction failed: {exc}") from exc
