# Model artifacts

Only three model files are required for local inference:

- `models/Interframes_Model/epoch14.keras` ? the only in-between generator.
- `models/GMA_Model/gma.pth` ? motion guidance used by InterFrames.
- `models/Moderation_Model/moderation.safetensors` ? upload moderation.

The epoch-14 checkpoint SHA-256 is `8a5cde4b34ba5aa33fc407091665017cc42e7e54c58b8e2f2676243613045440`. Its Stage 10 protocol is stored in `backend/app/models/interframes_protocol.json`.

The adapter uses the eight-channel feature contract from Stage 1. At inference, GMA estimates bidirectional flow, then epoch14 predicts each midpoint. Requests for 3 or 7 frames recursively split the interval and use epoch14 for every prediction.

From the repository root, verify local model files with:

```powershell
python scripts/run_setup.py --check
bash scripts/run_setup.sh
```

To download the pinned GMA and moderation artifacts, run `python scripts/run_setup.py --download`. Install the ML runtime with `python -m pip install -r backend/requirements-ml.txt`. Run `bash scripts/run_smoke.sh` to exercise moderation, GMA, and InterFrames on the sample frame.

The Kaggle setup check is `bash scripts/run_setup_kaggle.sh`. The service notebook needs the same three model files plus the source bundle. See the root README for startup commands.

The moderation threshold defaults to `0.5` and can be changed with `MODERATION_THRESHOLD` in `.env`.

## Release identities

| Artifact | Revision / identity |
|---|---|
| InterFrames | Epoch 14, SHA-256 `8a5cde4b34ba5aa33fc407091665017cc42e7e54c58b8e2f2676243613045440` |
| GMA source | `2f1fd29468a86a354d44dd25d107930b3f175043` |
| AnimeRun GMA weights | SHA-256 `4a9faacbec5d095e019fcbba9e19871c9df9c097854f6617c7e376928c338149` |
| Explicit-image classifier | Falconsai revision `7a365063de11be8a4b975ebe63733c112a819887` |
| Classifier weights | SHA-256 `97b2ce64ec146884b37f98ee7944ca4891aa72f6827dc0cb10684a1cbecd5830` |
