"""HTTP entrypoint for one model container, selected by MODEL_SERVICE_KIND."""
import base64
import io
import os

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image


KIND = os.getenv("MODEL_SERVICE_KIND", "")
app = FastAPI(title=f"InterFrames {KIND} model", docs_url=None, redoc_url=None)


class Prediction(BaseModel):
    image: str | None = None
    start: str | None = None
    end: str | None = None
    flow: str | None = None


def _image(encoded: str) -> Image.Image:
    """Decode one PNG image sent by the backend model client."""
    return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")


def _array(encoded: str, shape: tuple[int, ...], dtype: str) -> np.ndarray:
    """Restore the exact tensor shape expected by this model adapter."""
    return np.frombuffer(base64.b64decode(encoded), dtype=dtype).reshape(shape).copy()


def _encoded(value: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(value).tobytes()).decode("ascii")


def _model():
    """Load only the adapter assigned to this model container."""
    if KIND == "moderation":
        from app.models.moderation import moderator

        return moderator
    if KIND == "gma":
        from app.models.gma import gma

        return gma
    if KIND == "interframes":
        from app.models.interframes import model

        return model
    raise RuntimeError("MODEL_SERVICE_KIND must be moderation, gma, or interframes.")


@app.get("/health")
def health():
    """Load the assigned weights before reporting the container as ready."""
    try:
        model = _model()
        model._load()
        return {"status": "ok", "model": KIND}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/predict")
def predict(payload: Prediction):
    """Validate a model-specific request and return its prediction as JSON."""
    model = _model()
    try:
        if KIND == "moderation" and payload.image:
            score, blocked = model.score(_image(payload.image))
            return {"score": score, "blocked": blocked}
        if KIND == "gma" and payload.start and payload.end:
            flow = model.bidirectional_low(_image(payload.start), _image(payload.end))
            return {"flow": _encoded(flow.astype("<f2"))}
        if KIND == "interframes" and payload.start and payload.end and payload.flow:
            ink = model.predict(
                _array(payload.start, (256, 256), "<f4"),
                _array(payload.end, (256, 256), "<f4"),
                _array(payload.flow, (2, 32, 32, 2), "<f2"),
            )
            return {"ink": _encoded(ink.astype("<f4"))}
        raise HTTPException(status_code=422, detail=f"Invalid request for the {KIND} model.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
