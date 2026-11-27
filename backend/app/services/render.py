"""Colorize saved grayscale frames and package them as GIFs or PNG archives."""
import io
import os
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from app.config import MAX_RENDER_DIMENSION


def _hex_rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def _separable_gaussian(ink: np.ndarray, sigma: float = 3.0, radius: int = 6) -> np.ndarray:
    """Estimate the wide local halo around strokes using a separable 1D Gaussian."""
    offsets = np.arange(-radius, radius + 1, dtype=np.float32)
    weights = np.exp(-0.5 * (offsets / sigma) ** 2)
    weights /= weights.sum()
    height, width = ink.shape
    xs = np.arange(width)
    horiz = np.zeros_like(ink)
    for offset, weight in zip(offsets.astype(int), weights):
        horiz += weight * ink[:, np.clip(xs + offset, 0, width - 1)]
    ys = np.arange(height)
    out = np.zeros_like(ink)
    for offset, weight in zip(offsets.astype(int), weights):
        out += weight * horiz[np.clip(ys + offset, 0, height - 1), :]
    return out


def crisp_ink(ink: np.ndarray, level: float = 0.5) -> np.ndarray:
    """Suppress wide low-confidence blur halos while keeping thin line ridges and dark cores."""
    blur = _separable_gaussian(ink)
    ridge = np.maximum(0.0, ink - 0.85 * blur)
    floor = 0.04 + 0.14 * level
    detail = np.clip((ridge - floor) / max(1e-4, 0.30 - 0.08 * level), 0.0, 1.0)
    core_t = 0.65 + 0.25 * level
    core = np.clip((ink - core_t) / max(1e-4, 1.0 - core_t), 0.0, 1.0)
    out = np.maximum(detail, core)
    return np.where(ink < 0.10 + 0.18 * level, 0.0, out).astype(np.float32)


def render_frame(path: str, settings: dict) -> Image.Image:
    """Apply export-only cutoff or crisp-lines cleanup and palette, then fit within size."""
    with Image.open(path) as source:
        gray = source.convert("L")
        cutoff = settings.get("cutoff")
        mode = settings.get("cutoff_mode") or ("raw" if cutoff is None else "threshold")
        if mode == "crisp":
            level = 0.5 if cutoff is None else float(cutoff)
            ink = 1.0 - np.asarray(gray, dtype=np.float32) / 255.0
            cleaned = crisp_ink(ink, level)
            gray = Image.fromarray(np.uint8(np.rint(np.clip(1.0 - cleaned, 0.0, 1.0) * 255.0)), mode="L")
        elif mode == "threshold" and cutoff is not None:
            threshold = round((1 - cutoff) * 255)
            gray = gray.point(lambda pixel: 0 if pixel < threshold else 255)
        ink_color = _hex_rgb(settings["ink_color"])
        background_color = _hex_rgb(settings["background_color"])
        image = ImageOps.colorize(gray, black=ink_color, white=background_color)
        image.thumbnail(
            (min(settings["width"], MAX_RENDER_DIMENSION), min(settings["height"], MAX_RENDER_DIMENSION)),
            Image.Resampling.LANCZOS,
        )
        return image


def build_export(frame_paths: list[str], settings: dict, target: Path) -> None:
    """Write the selected format to a temporary file before publishing it."""
    frame_styles = settings.get("frame_styles", {})
    frame_indices = settings.get("frame_indices")
    frames = []
    for pos, path in enumerate(frame_paths):
        style_key = frame_indices[pos] if frame_indices and pos < len(frame_indices) else pos
        style = frame_styles.get(style_key, frame_styles.get(str(style_key), {}))
        frames.append(render_frame(path, {**settings, **style}))
    if not frames:
        raise ValueError("Generation has no frames to export.")
    temporary = target.with_suffix(target.suffix + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    if settings["format"] == "gif":
        frames[0].save(
            temporary,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=round(1000 / settings["fps"]),
            loop=0,
            disposal=2,
            optimize=False,
        )
    else:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, frame in enumerate(frames):
                buffer = io.BytesIO()
                frame.save(buffer, format="PNG")
                archive.writestr(f"frame-{index:02d}.png", buffer.getvalue())
    os.replace(temporary, target)
