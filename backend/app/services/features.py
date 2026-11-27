"""Build the eight image channels expected by the InterFrames checkpoint."""
import numpy as np
from scipy.ndimage import distance_transform_edt


def distance_map(ink: np.ndarray, threshold: float = 0.15, radius: int = 32) -> np.ndarray:
    """Encode each pixel's distance from visible ink, capped to a fixed radius."""
    mask = ink > threshold
    if not mask.any():
        return np.ones_like(ink, dtype=np.float32)
    return np.minimum(distance_transform_edt(~mask), radius).astype(np.float32) / radius


def forward_splat(ink: np.ndarray, flow: np.ndarray, t: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Move ink along flow and return both the warped image and covered pixels."""
    height, width = ink.shape
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    tx, ty = xx + t * flow[0], yy + t * flow[1]
    x0, y0 = np.floor(tx).astype(np.int64), np.floor(ty).astype(np.int64)
    dx, dy = tx - x0, ty - y0
    accum = np.zeros((height, width), dtype=np.float32)
    norm = np.zeros((height, width), dtype=np.float32)
    for ox, oy, weight in (
        (0, 0, (1 - dx) * (1 - dy)),
        (1, 0, dx * (1 - dy)),
        (0, 1, (1 - dx) * dy),
        (1, 1, dx * dy),
    ):
        x, y = x0 + ox, y0 + oy
        keep = (x >= 0) & (x < width) & (y >= 0) & (y < height) & (weight > 0)
        np.add.at(accum, (y[keep], x[keep]), (weight * ink)[keep])
        np.add.at(norm, (y[keep], x[keep]), weight[keep])
    valid = norm > 1e-6
    return np.divide(accum, norm, out=np.zeros_like(accum), where=valid), valid.astype(np.float32)


def upsample_low(flow: np.ndarray, size: int = 256) -> np.ndarray:
    """Resize GMA's coarse flow and scale vectors back to image-pixel units."""
    flow = np.asarray(flow, dtype=np.float32)
    height, width = flow.shape[:2]
    yy = np.linspace(0, height - 1, size, dtype=np.float32)
    xx = np.linspace(0, width - 1, size, dtype=np.float32)
    y0, x0 = np.floor(yy).astype(int), np.floor(xx).astype(int)
    y1, x1 = np.minimum(y0 + 1, height - 1), np.minimum(x0 + 1, width - 1)
    wy = (yy - y0).astype(np.float32)[:, None, None]
    wx = (xx - x0).astype(np.float32)[None, :, None]
    top = (1 - wx) * flow[y0[:, None], x0[None, :]] + wx * flow[y0[:, None], x1[None, :]]
    bottom = (1 - wx) * flow[y1[:, None], x0[None, :]] + wx * flow[y1[:, None], x1[None, :]]
    return ((1 - wy) * top + wy * bottom) * 8.0


def features_from_low(start: np.ndarray, end: np.ndarray, low: np.ndarray) -> np.ndarray:
    """Combine endpoint ink, warped ink, distance, and coverage into model input."""
    forward = upsample_low(low[0], start.shape[0]).transpose(2, 0, 1)
    backward = upsample_low(low[1], start.shape[0]).transpose(2, 0, 1)
    warped_start, coverage_start = forward_splat(start, forward)
    warped_end, coverage_end = forward_splat(end, backward)
    features = np.stack(
        [start, end, warped_start, warped_end, distance_map(start), distance_map(end), coverage_start, coverage_end],
        axis=-1,
    ).astype(np.float32)
    if features.shape != (256, 256, 8):
        raise ValueError(f"Unexpected InterFrames feature tensor shape: {features.shape}")
    return features
