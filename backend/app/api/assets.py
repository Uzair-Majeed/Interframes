"""Upload approved endpoint drawings."""
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import LOCAL_OWNER_ID, MODERATION_POLICY_VERSION
from app.database import repositories
from app.models.moderation import ModerationUnavailable, moderator
from app.schemas import AssetResponse
from app.services.guardrails import decode_upload
from app.services.storage import save_upload


router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("", response_model=AssetResponse)
async def upload_asset(file: UploadFile = File(...)):
    """Validate, moderate, and persist one endpoint drawing."""
    # Decode and sanitize before moderation so the saved asset matches what was checked.
    image, digest = await decode_upload(file)
    try:
        score, blocked = moderator.score(image)
    except ModerationUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODERATION_UNAVAILABLE", "detail": str(exc)},
        ) from exc
    if blocked:
        raise HTTPException(
            status_code=422,
            detail={"code": "CONTENT_BLOCKED", "detail": "This image cannot be accepted under the current moderation policy."},
        )
    path = save_upload(image)
    try:
        asset_id = repositories.create_asset(
            LOCAL_OWNER_ID, digest, path, image.width, image.height, MODERATION_POLICY_VERSION, score
        )
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return AssetResponse(
        id=asset_id,
        preview_url=f"/api/v1/assets/{asset_id}/preview",
        width=image.width,
        height=image.height,
        sha256=digest,
    )


@router.get("/{asset_id}/preview")
def asset_preview(asset_id: str):
    """Return a preview only when the asset belongs to this local workspace."""
    asset = repositories.get_asset(LOCAL_OWNER_ID, asset_id)
    if asset is None:
        raise HTTPException(404, detail={"code": "ASSET_NOT_FOUND", "detail": "Asset was not found."})
    return FileResponse(asset["path"], media_type="image/png")


