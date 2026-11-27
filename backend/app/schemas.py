"""Request and response shapes shared by the HTTP API."""
from typing import Literal

from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    id: str
    preview_url: str
    width: int
    height: int
    sha256: str


class GenerationInput(BaseModel):
    """A pair of approved images and the requested number of in-between frames."""
    start_asset_id: str
    end_asset_id: str
    inbetween_count: Literal[1, 3, 7] = 1


class FrameExportStyle(BaseModel):
    """Optional palette overrides for one frame in an exported sequence."""
    ink_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    cutoff: float | None = Field(ge=0, le=1)
    cutoff_mode: Literal["raw", "threshold", "crisp"] | None = None


class ExportInput(BaseModel):
    """Palette, playback speed, and size options for a rendered download."""
    format: Literal["gif", "png_zip"] = "gif"
    width: int = Field(default=512, ge=16, le=2048)
    height: int = Field(default=512, ge=16, le=2048)
    fps: int = Field(default=12, ge=1, le=60)
    ink_color: str = Field(default="#111111", pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    cutoff: float | None = Field(default=None, ge=0, le=1)
    cutoff_mode: Literal["raw", "threshold", "crisp"] | None = None
    frame_styles: dict[int, FrameExportStyle] = Field(default_factory=dict)
    frame_indices: list[int] | None = None


class InsertFrameInput(BaseModel):
    """Two existing frame indices to interpolate a new frame between."""
    left_index: int
    right_index: int


class ErrorResponse(BaseModel):
    code: str
    detail: str

