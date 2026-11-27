"""Create, monitor, export, and remove local generation jobs."""
import json
import base64
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import (
    ARTIFACTS_DIR,
    LOCAL_OWNER_ID,
    MODERATION_POLICY_VERSION,
)
from app.database import repositories
from app.models.moderation import ModerationUnavailable, moderator
from app.schemas import ExportInput, GenerationInput, InsertFrameInput
from app.services.inference import interpolate_pair
from app.services.render import build_export
from app.services.storage import remove_paths


router = APIRouter(prefix="/generations", tags=["generations"])


def _not_found() -> HTTPException:
    return HTTPException(404, detail={"code": "GENERATION_NOT_FOUND", "detail": "Generation was not found."})


def _public_generation(row) -> dict:
    """Convert a database row into the smaller shape consumed by the web app."""
    req = json.loads(row["request_json"]) if row["request_json"] else {}
    result = json.loads(row["result_json"]) if row["result_json"] else None
    frames = result["frames"] if result else []
    return {
        "id": row["id"],
        "status": row["status"],
        "stage": row["stage"],
        "completed": row["progress"],
        "total": row["total"],
        "created_at": row["created_at"],
        "frame_models": result.get("frame_models", []) if result else [],
        "warnings": result.get("warnings", []) if result else [],
        "frames": [
            {"index": frame["index"], "url": f"/api/v1/generations/{row['id']}/frames/{frame['index']}"}
            for frame in frames
        ],
        "error": {"code": row["error_code"], "detail": row["error_detail"]} if row["error_code"] else None,
        "start_asset_id": req.get("start_asset_id"),
        "end_asset_id": req.get("end_asset_id"),
    }


def _check_asset_approval(asset_id: str):
    """Make sure an old upload still passes the active moderation policy."""
    asset = repositories.get_asset(LOCAL_OWNER_ID, asset_id)
    if asset is None:
        raise HTTPException(404, detail={"code": "ASSET_NOT_FOUND", "detail": "An endpoint asset was not found."})
    if asset["policy_version"] != MODERATION_POLICY_VERSION:
        try:
            from PIL import Image

            with Image.open(asset["path"]) as image:
                score, blocked = moderator.score(image.convert("RGB"))
        except ModerationUnavailable as exc:
            raise HTTPException(
                503, detail={"code": "MODERATION_UNAVAILABLE", "detail": str(exc)}
            ) from exc
        if blocked:
            raise HTTPException(
                422,
                detail={"code": "CONTENT_BLOCKED", "detail": "An endpoint is no longer approved under the current policy."},
            )
        repositories.update_asset_moderation(asset_id, LOCAL_OWNER_ID, MODERATION_POLICY_VERSION, score)
    return asset


@router.post("")
def create_generation(
    payload: GenerationInput,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Validate approved inputs and return the idempotent queued job."""
    # The same key and request return the same job instead of duplicating work.
    if not idempotency_key or len(idempotency_key) > 200:
        raise HTTPException(
            400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "detail": "Send an Idempotency-Key header."}
        )
    start = _check_asset_approval(payload.start_asset_id)
    end = _check_asset_approval(payload.end_asset_id)
    request = payload.model_dump()
    try:
        generation_id, created = repositories.create_generation(LOCAL_OWNER_ID, idempotency_key, request)
    except ValueError as exc:
        raise HTTPException(409, detail={"code": "IDEMPOTENCY_CONFLICT", "detail": "This key was already used with a different request."}) from exc
    row = repositories.get_generation(LOCAL_OWNER_ID, generation_id)
    response = _public_generation(row)
    return response


@router.get("")
def list_generations(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
):
    """Return one page of the local user's newest generations."""
    # The cursor stores the last row's sort values for stable page boundaries.
    before = None
    if cursor:
        try:
            created_at, generation_id = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
            before = (str(created_at), str(generation_id))
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(400, detail={"code": "INVALID_CURSOR", "detail": "History cursor is invalid."}) from exc
    rows = repositories.list_generations(LOCAL_OWNER_ID, limit, before)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        token = json.dumps([last["created_at"], last["id"]], separators=(",", ":")).encode("utf-8")
        next_cursor = base64.urlsafe_b64encode(token).decode("ascii")
    return {"items": [_public_generation(row) for row in rows], "next_cursor": next_cursor}


@router.get("/{generation_id}")
def get_generation(generation_id: str):
    """Return current progress or the saved result for a generation."""
    row = repositories.get_generation(LOCAL_OWNER_ID, generation_id)
    if row is None:
        raise _not_found()
    return _public_generation(row)


@router.get("/{generation_id}/frames/{frame_index}")
def get_frame(generation_id: str, frame_index: int):
    """Serve one saved frame after confirming the generation is ready."""
    row = repositories.get_generation(LOCAL_OWNER_ID, generation_id)
    if row is None or row["status"] != "ready" or not row["result_json"]:
        raise _not_found()
    result = json.loads(row["result_json"])
    frame = next((item for item in result["frames"] if item["index"] == frame_index), None)
    if frame is None or not Path(frame["path"]).is_file():
        raise HTTPException(404, detail={"code": "FRAME_NOT_FOUND", "detail": "Frame was not found."})
    return FileResponse(frame["path"], media_type="image/png")


@router.post("/{generation_id}/cancel")
def cancel_generation(generation_id: str):
    """Request cancellation and return the job's latest state."""
    if not repositories.request_cancel(LOCAL_OWNER_ID, generation_id):
        row = repositories.get_generation(LOCAL_OWNER_ID, generation_id)
        if row is None:
            raise _not_found()
        return _public_generation(row)
    return _public_generation(repositories.get_generation(LOCAL_OWNER_ID, generation_id))


@router.delete("/{generation_id}")
def delete_generation(generation_id: str):
    """Remove a history row and its stored frames and exports."""
    row = repositories.get_generation(LOCAL_OWNER_ID, generation_id)
    if row is None:
        raise _not_found()
    export_files = repositories.export_paths(LOCAL_OWNER_ID, generation_id)
    result = repositories.remove_generation(LOCAL_OWNER_ID, generation_id)
    remove_paths([item["path"] for item in (result or {}).get("frames", [])] + export_files)
    return {"deleted": True}


@router.post("/{generation_id}/frames/insert")
def insert_frame(generation_id: str, payload: InsertFrameInput):
    """Generate one new in-between frame between two existing frames."""
    row = repositories.get_generation(LOCAL_OWNER_ID, generation_id)
    if row is None or row["status"] != "ready" or not row["result_json"]:
        raise _not_found()
    result = json.loads(row["result_json"])
    frames = result.get("frames", [])
    by_index = {item["index"]: item for item in frames}
    left = by_index.get(payload.left_index)
    right = by_index.get(payload.right_index)
    if left is None or right is None:
        raise HTTPException(404, detail={"code": "FRAME_NOT_FOUND", "detail": "Source frames were not found."})
    new_index = max((item["index"] for item in frames), default=-1) + 1
    target = ARTIFACTS_DIR / "generations" / generation_id / f"frame-{new_index:02d}.png"
    interpolate_pair(left["path"], right["path"], target)
    frames.append({"index": new_index, "path": str(target), "model": "GMA + InterFrames epoch 14"})
    result["frames"] = frames
    repositories.update_generation(generation_id, result_json=json.dumps(result))
    return {"index": new_index, "url": f"/api/v1/generations/{generation_id}/frames/{new_index}"}


@router.post("/{generation_id}/exports", status_code=202)
def request_export(generation_id: str, payload: ExportInput):
    """Render a ready generation with the selected palette and file format."""
    row = repositories.get_generation(LOCAL_OWNER_ID, generation_id)
    if row is None:
        raise _not_found()
    if row["status"] != "ready" or not row["result_json"]:
        raise HTTPException(409, detail={"code": "GENERATION_NOT_READY", "detail": "Wait for generation to finish before exporting."})
    if payload.width > 2048 or payload.height > 2048:
        raise HTTPException(422, detail={"code": "INVALID_DIMENSIONS", "detail": "Maximum output size is 2048x2048."})
    settings = payload.model_dump()
    # Keep original grayscale frames; apply palette and cutoff only to this export.
    export_id = repositories.create_export(LOCAL_OWNER_ID, generation_id, payload.format, settings)
    result = json.loads(row["result_json"])
    extension = "gif" if payload.format == "gif" else "zip"
    target = ARTIFACTS_DIR / "exports" / f"{export_id}.{extension}"
    frame_map = {item["index"]: item["path"] for item in result["frames"]}
    if payload.frame_indices:
        frame_paths = [frame_map[idx] for idx in payload.frame_indices if idx in frame_map]
    else:
        frame_paths = [item["path"] for item in result["frames"]]
    try:
        build_export(frame_paths, settings, target)
        repositories.update_export(export_id, "ready", str(target))
    except Exception as exc:
        repositories.update_export(export_id, "failed", error=str(exc))
        raise HTTPException(500, detail={"code": "EXPORT_FAILED", "detail": str(exc)}) from exc
    return {
        "id": export_id,
        "status": "ready",
        "download_url": f"/api/v1/generations/{generation_id}/exports/{export_id}/download",
    }


@router.get("/{generation_id}/exports/{export_id}")
def get_export(generation_id: str, export_id: str):
    """Return export status and expose its download path when ready."""
    entry = repositories.get_export(LOCAL_OWNER_ID, generation_id, export_id)
    if entry is None:
        raise HTTPException(404, detail={"code": "EXPORT_NOT_FOUND", "detail": "Export was not found."})
    return {
        "id": entry["id"],
        "status": entry["status"],
        "download_url": f"/api/v1/generations/{generation_id}/exports/{export_id}/download"
        if entry["status"] == "ready"
        else None,
        "error": entry["error_detail"],
    }


@router.get("/{generation_id}/exports/{export_id}/download")
def download_export(generation_id: str, export_id: str):
    """Download a completed export owned by this local workspace."""
    entry = repositories.get_export(LOCAL_OWNER_ID, generation_id, export_id)
    if entry is None or entry["status"] != "ready" or not entry["path"] or not Path(entry["path"]).is_file():
        raise HTTPException(404, detail={"code": "EXPORT_NOT_FOUND", "detail": "Export is not ready or was not found."})
    media_type = "image/gif" if entry["format"] == "gif" else "application/zip"
    return FileResponse(entry["path"], media_type=media_type, filename=Path(entry["path"]).name)
