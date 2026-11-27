"""Poll the local job table and run one generation at a time in the background."""
import json
import logging
import threading
import time

from app.config import LOCAL_OWNER_ID
from app.database import repositories
from app.models.gma import GMAUnavailable
from app.models.interframes import ModelUnavailable
from app.services.inference import GenerationCancelled, generate
from app.services.storage import remove_paths


logger = logging.getLogger("interframes.worker")
_stop = threading.Event()
_thread = None


def _run_generation(generation_id: str) -> None:
    """Load job inputs, run inference, and save a terminal status."""
    entry = repositories.generation_request(generation_id)
    if entry is None:
        return
    request, owner_id, _ = entry

    def asset_path(asset_id: str) -> str:
        # Resolve assets through the owner-scoped query before reading their files.
        asset = repositories.get_asset(owner_id, asset_id)
        if asset is None:
            raise ValueError("An endpoint asset is missing or no longer authorized.")
        return asset["path"]

    def cancelled() -> bool:
        # Inference checks this between model calls and before each saved frame.
        current = repositories.generation_request(generation_id)
        return current is None or current[2]

    result = None
    try:
        repositories.update_generation(generation_id, stage="checking uploads")
        for key in ("start_asset_id", "end_asset_id"):
            asset = repositories.get_asset(owner_id, request[key])
            if asset is None:
                raise ValueError("An endpoint asset is missing or no longer authorized.")
        result = generate(
            generation_id,
            request,
            (asset_path(request["start_asset_id"]), asset_path(request["end_asset_id"])),
            lambda stage, progress, total: repositories.update_generation(
                generation_id, stage=stage, progress=progress, total=total
            ),
            cancelled,
        )
        if cancelled():
            remove_paths([frame["path"] for frame in result["frames"]])
            raise GenerationCancelled()
        repositories.update_generation(
            generation_id, status="ready", stage="ready", progress=request["inbetween_count"],
            result_json=json.dumps(result),
        )
    except GenerationCancelled:
        if result is not None:
            remove_paths([frame["path"] for frame in result["frames"]])
        repositories.update_generation(generation_id, status="cancelled", stage="cancelled", error_code="CANCELLED")
    except (GMAUnavailable, ModelUnavailable) as exc:
        repositories.update_generation(
            generation_id, status="failed", stage="failed", error_code="MODEL_UNAVAILABLE", error_detail=str(exc)
        )
        logger.warning("Model unavailable for job %s: %s", generation_id, exc)
    except Exception as exc:
        repositories.update_generation(
            generation_id, status="failed", stage="failed", error_code="GENERATION_FAILED", error_detail=str(exc)
        )
        logger.exception("Generation job %s failed", generation_id)


def _serve() -> None:
    """Keep polling after individual job or database errors."""
    while not _stop.is_set():
        try:
            generation_id = repositories.claim_generation()
            if generation_id:
                _run_generation(generation_id)
            else:
                _stop.wait(0.75)
        except Exception:
            logger.exception("Worker loop failed while claiming a job")
            _stop.wait(1.0)


def start_worker() -> None:
    """Start a single daemon worker for this local API process."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_serve, name="interframes-worker", daemon=True)
    _thread.start()


def stop_worker() -> None:
    """Ask the worker to stop and wait briefly for its current step to finish."""
    _stop.set()
    if _thread:
        _thread.join(timeout=10)
