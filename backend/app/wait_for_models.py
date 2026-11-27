"""Keep the API container from accepting jobs before model services are ready."""
import time
from urllib.request import Request, urlopen

from app.config import (
    GMA_SERVICE_URL,
    INTERFRAMES_SERVICE_URL,
    MODEL_SERVICE_TOKEN,
    MODERATION_SERVICE_URL,
)


def main() -> None:
    """Wait until each configured model container responds to its health check."""
    services = {
        "moderation": MODERATION_SERVICE_URL,
        "GMA": GMA_SERVICE_URL,
        "InterFrames": INTERFRAMES_SERVICE_URL,
    }
    services = {name: url for name, url in services.items() if url}
    deadline = time.monotonic() + 1800

    while services and time.monotonic() < deadline:
        unavailable = []
        for name, url in services.items():
            headers = {"Authorization": f"Bearer {MODEL_SERVICE_TOKEN}"} if MODEL_SERVICE_TOKEN else {}
            try:
                request = Request(f"{url.rstrip('/')}/health", headers=headers)
                with urlopen(request, timeout=5) as response:
                    if response.status != 200:
                        unavailable.append(name)
            except Exception:
                unavailable.append(name)
        if not unavailable:
            return
        # A model may need time to load its weights, so retry instead of exiting.
        time.sleep(5)

    if services:
        raise SystemExit("Model services did not become ready within 30 minutes.")


if __name__ == "__main__":
    main()
