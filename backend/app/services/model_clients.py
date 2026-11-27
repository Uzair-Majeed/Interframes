"""Small JSON client helpers for the separate model containers."""
import base64
import io
import json
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from app.config import MODEL_SERVICE_TOKEN


def post_json(base_url: str, payload: dict, timeout: int = 300, *, cache: bool = True) -> dict:
    """Call a model service and return its parsed JSON response."""
    del cache
    headers = {"Content-Type": "application/json"}
    if MODEL_SERVICE_TOKEN:
        headers["Authorization"] = f"Bearer {MODEL_SERVICE_TOKEN}"
    request = Request(
        f"{base_url.rstrip('/')}/predict",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def encode_image(image: Image.Image) -> str:
    """Send images as compact base64 PNGs in the JSON model-service protocol."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def decode_array(value: str, shape: tuple[int, ...], dtype: str) -> np.ndarray:
    """Restore a typed model result and reject corrupt numeric output."""
    raw = base64.b64decode(value)
    result = np.frombuffer(raw, dtype=dtype).reshape(shape).copy()
    if not np.isfinite(result).all():
        raise ValueError("Model service returned non-finite values.")
    return result


def encode_array(value: np.ndarray) -> str:
    """Serialize a contiguous array for the matching model-service decoder."""
    return base64.b64encode(np.ascontiguousarray(value).tobytes()).decode("ascii")
