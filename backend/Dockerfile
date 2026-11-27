FROM python:3.12-slim
WORKDIR /workspace
COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN pip install --no-cache-dir -r /workspace/backend/requirements.txt
COPY backend /workspace/backend
ENV PYTHONPATH=/workspace/backend
ENV DATABASE_PATH=/data/interframes.sqlite3
ENV ARTIFACTS_DIR=/data/artifacts
EXPOSE 8000
CMD ["sh", "-c", "python -m app.wait_for_models && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
