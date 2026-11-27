"""Generate every in-between with GMA motion guidance and InterFrames epoch 14."""
import hashlib
import os
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import ARTIFACTS_DIR
from app.models.gma import gma
from app.models.interframes import model, preprocess_image
from app.services.storage import remove_paths


class GenerationCancelled(Exception):
    pass


def _gma_cache_path(left_bytes: bytes, right_bytes: bytes) -> Path:
    digest = hashlib.sha256(left_bytes + b"|" + right_bytes).hexdigest()
    return ARTIFACTS_DIR / "gma_cache" / f"{digest}.npy"


def _cached_gma_flow(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Return cached bidirectional coarse flow for an ink pair or compute and store it."""
    left_u8 = np.uint8(np.clip((1 - left) * 255, 0, 255))
    right_u8 = np.uint8(np.clip((1 - right) * 255, 0, 255))
    cache_file = _gma_cache_path(left_u8.tobytes(), right_u8.tobytes())
    if cache_file.is_file():
        try:
            cached = np.load(cache_file)
            if cached.shape == (2, 32, 32, 2) and np.isfinite(cached).all():
                return cached
        except Exception:
            pass
    left_image = Image.fromarray(left_u8, mode="L").convert("RGB")
    right_image = Image.fromarray(right_u8, mode="L").convert("RGB")
    flow = gma.bidirectional_low(left_image, right_image)
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(".tmp.npy")
        np.save(tmp, flow)
        os.replace(tmp, cache_file)
    except Exception:
        pass
    return flow


def interpolate_pair(left_path: str, right_path: str, target_path: Path) -> None:
    """Generate a single in-between frame from two existing frame paths."""
    _, left_ink = _read_asset(left_path)
    _, right_ink = _read_asset(right_path)
    flow = _cached_gma_flow(left_ink, right_ink)
    prediction = model.predict(left_ink, right_ink, flow)
    grayscale = np.uint8(np.rint(np.clip(1 - prediction, 0, 1) * 255))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = target_path.with_suffix(".part")
    Image.fromarray(grayscale, mode="L").save(temporary, format="PNG", optimize=True)
    os.replace(temporary, target_path)


def _read_asset(path: str) -> tuple[Image.Image, np.ndarray]:
    """Read an approved upload and prepare its normalized model input."""
    with Image.open(path) as source:
        image = source.convert("RGB")
        return image, preprocess_image(image)


def generate(generation_id: str, request: dict, asset_paths: tuple[str, str], update, is_cancelled) -> dict:
    """Create the requested in-betweens and save their raw grayscale PNGs."""
    _, start_ink = _read_asset(asset_paths[0])
    _, end_ink = _read_asset(asset_paths[1])
    count = request["inbetween_count"]
    intervals = count + 1
    depth = {1: 1, 3: 2, 7: 3}[count]
    generated: dict[int, np.ndarray] = {}
    completed = 0

    def midpoint(left: np.ndarray, right: np.ndarray, left_index: int, right_index: int, level: int):
        nonlocal completed
        if is_cancelled():
            raise GenerationCancelled()
        if level == 0:
            return

        update("estimating motion", completed, count)
        flow = _cached_gma_flow(left, right)
        update("generating frames", completed, count)
        prediction = model.predict(left, right, flow)

        middle_index = (left_index + right_index) // 2
        generated[middle_index] = prediction
        completed += 1
        update("generating frames", completed, count)
        midpoint(left, prediction, left_index, middle_index, level - 1)
        midpoint(prediction, right, middle_index, right_index, level - 1)

    midpoint(start_ink, end_ink, 0, intervals, depth)
    if len(generated) != count:
        raise ValueError(f"Expected {count} in-between frames, produced {len(generated)}.")

    ordered = [start_ink] + [generated[index] for index in range(1, intervals)] + [end_ink]
    if any(frame.shape != (256, 256) for frame in ordered):
        raise ValueError("Generated frame sequence has an unexpected shape.")
    if not all(np.isfinite(frame).all() and frame.min() >= 0 and frame.max() <= 1 for frame in ordered):
        raise ValueError("Generated frame sequence contains invalid ink values.")

    output_dir = ARTIFACTS_DIR / "generations" / generation_id
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_items = []
    try:
        for index, ink in enumerate(ordered):
            if is_cancelled():
                raise GenerationCancelled()
            grayscale = np.uint8(np.rint(np.clip(1 - ink, 0, 1) * 255))
            target = output_dir / f"frame-{index:02d}.png"
            temporary = target.with_suffix(".part")
            Image.fromarray(grayscale, mode="L").save(temporary, format="PNG", optimize=True)
            os.replace(temporary, target)
            frame_items.append({"index": index, "path": str(target), "model": "endpoint" if index in (0, len(ordered) - 1) else "GMA + InterFrames epoch 14"})
    except Exception:
        remove_paths([item["path"] for item in frame_items])
        raise

    warnings = []
    for index, ink in enumerate(ordered[1:-1], start=1):
        ink_ratio = float((ink > 0.15).mean())
        if ink_ratio < 0.001:
            warnings.append(f"Frame {index} is nearly empty.")
        elif ink_ratio > 0.65:
            warnings.append(f"Frame {index} is heavily saturated.")

    return {
        "frames": frame_items,
        "frame_models": [item["model"] for item in frame_items],
        "warnings": warnings,
        "width": 256,
        "height": 256,
    }
