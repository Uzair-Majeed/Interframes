# Model service API

Each model container exposes `GET /health` and `POST /predict` on port 8001. Requests and responses are JSON; tensor data is base64 encoded.

| Service | Request fields | Response fields |
|---|---|---|
| Moderation | `image`: PNG bytes | `score`: NSFW probability, `blocked`: policy decision |
| GMA | `start`, `end`: PNG bytes | `flow`: float16 array shaped `[2,32,32,2]` |
| InterFrames | `start`, `end`: float32 ink arrays `[256,256]`; `flow`: float16 array `[2,32,32,2]` | `ink`: float32 array `[256,256]` |

Compose runs these three model services on its internal network. Kaggle mode exposes the same routes at `/moderation`, `/gma`, and `/interframes` through one authenticated gateway. Set `KAGGLE_MODEL_GATEWAY_URL` and `KAGGLE_MODEL_SERVICE_TOKEN` in `.env` for that mode.
