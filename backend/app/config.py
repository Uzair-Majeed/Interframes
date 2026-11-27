"""Read runtime paths, limits, and model-service settings from the environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent


# Load root settings for local runs; Docker and shell values still take precedence.
load_dotenv(REPOSITORY_ROOT / ".env")


# Keep every model path configurable so the same app works locally and in Compose.
MODEL_DIR = Path(os.getenv("MODEL_DIR", REPOSITORY_ROOT / "models"))
MODERATION_DIR = Path(os.getenv("MODERATION_DIR", MODEL_DIR / "Moderation_Model"))
GMA_DIR = Path(os.getenv("GMA_DIR", BACKEND_DIR / "app" / "models" / "gma_config"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", BACKEND_DIR / "data" / "interframes.sqlite3"))
ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", BACKEND_DIR / "data" / "artifacts"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", "20000000"))
MAX_RENDER_DIMENSION = int(os.getenv("MAX_RENDER_DIMENSION", "2048"))


MODERATION_THRESHOLD = float(os.getenv("MODERATION_THRESHOLD", "0.5"))

# Including the threshold makes a policy change trigger moderation again.
MODERATION_POLICY_VERSION = f"falconsai-nsfw@7a365063:{MODERATION_THRESHOLD:.3f}"
LOCAL_OWNER_ID = "local-user"
MODEL_SHA256 = "8a5cde4b34ba5aa33fc407091665017cc42e7e54c58b8e2f2676243613045440"
MODEL_PATH = MODEL_DIR / "Interframes_Model" / "epoch14.keras"
PROTOCOL_PATH = BACKEND_DIR / "app" / "models" / "interframes_protocol.json"
GMA_CHECKPOINT_PATH = MODEL_DIR / "GMA_Model" / "gma.pth"
MODERATION_SERVICE_URL = os.getenv("MODERATION_SERVICE_URL", "")
GMA_SERVICE_URL = os.getenv("GMA_SERVICE_URL", "")
INTERFRAMES_SERVICE_URL = os.getenv("INTERFRAMES_SERVICE_URL", "")
MODEL_SERVICE_TOKEN = os.getenv("MODEL_SERVICE_TOKEN", "")

