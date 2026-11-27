"""Store private upload files and clean up generated artifacts safely."""
import os
import logging
from pathlib import Path
from uuid import uuid4

from PIL import Image

from app.config import ARTIFACTS_DIR


logger = logging.getLogger("interframes.storage")


def save_upload(image: Image.Image) -> str:
    """Save a normalized PNG and atomically move it into the asset folder."""
    directory = ARTIFACTS_DIR / "assets"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid4().hex}.png"
    temporary = target.with_suffix(".part")
    image.save(temporary, format="PNG", optimize=True)
    os.replace(temporary, target)
    return str(target)


def remove_paths(paths: list[str]) -> None:
    """Remove files when possible and log cleanup failures for later inspection."""
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove private artifact %s: %s", path, exc)
            continue
