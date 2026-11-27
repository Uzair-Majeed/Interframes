"""Keep SQL queries and database updates out of HTTP handlers."""
import json
from datetime import datetime, timezone
from uuid import uuid4

from app.database.session import connect


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_asset(owner_id: str, digest: str, path: str, width: int, height: int, policy: str, score: float) -> str:
    """Record the saved file and the moderation decision for its pixels."""
    asset_id = uuid4().hex
    with connect() as db:
        db.execute(
            "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (asset_id, owner_id, digest, path, width, height, policy, score, now()),
        )
    return asset_id


def get_asset(owner_id: str, asset_id: str):
    with connect() as db:
        return db.execute("SELECT * FROM assets WHERE id=? AND owner_id=?", (asset_id, owner_id)).fetchone()


def create_generation(owner_id: str, idempotency_key: str, request: dict) -> tuple[str, bool]:
    """Create a queued job or return the matching job for a repeated request."""
    generation_id = uuid4().hex
    timestamp = now()
    with connect() as db:
        try:
            db.execute(
                "INSERT INTO generations "
                "(id, owner_id, idempotency_key, request_json, status, stage, total, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'queued', 'queued', ?, ?, ?)",
                (generation_id, owner_id, idempotency_key, json.dumps(request), request["inbetween_count"], timestamp, timestamp),
            )
            return generation_id, True
        except Exception as exc:
            existing = db.execute(
                "SELECT id, request_json FROM generations WHERE owner_id=? AND idempotency_key=?",
                (owner_id, idempotency_key),
            ).fetchone()
            if existing is None:
                raise exc
            if json.loads(existing["request_json"]) != request:
                raise ValueError("IDEMPOTENCY_CONFLICT") from exc
            return existing["id"], False


def get_generation(owner_id: str, generation_id: str):
    with connect() as db:
        return db.execute("SELECT * FROM generations WHERE id=? AND owner_id=?", (generation_id, owner_id)).fetchone()


def list_generations(owner_id: str, limit: int = 50, before: tuple[str, str] | None = None):
    """Return one page in newest-first order, using the ID to break date ties."""
    query = "SELECT * FROM generations WHERE owner_id=?"
    parameters: list = [owner_id]
    if before:
        query += " AND (created_at < ? OR (created_at = ? AND id < ?))"
        parameters.extend((before[0], before[0], before[1]))
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    parameters.append(min(limit, 100) + 1)
    with connect() as db:
        return db.execute(query, parameters).fetchall()


def claim_generation():
    """Atomically move the oldest queued job to running so only one worker claims it."""
    with connect() as db:
        row = db.execute(
            "SELECT id FROM generations WHERE status='queued' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        updated = db.execute(
            "UPDATE generations SET status='running', stage='checking uploads', updated_at=? WHERE id=? AND status='queued'",
            (now(), row["id"]),
        )
        return row["id"] if updated.rowcount else None


def update_generation(generation_id: str, **fields):
    """Update job progress or its final result and refresh the update time."""
    fields["updated_at"] = now()
    assignments = ", ".join(f"{key}=?" for key in fields)
    with connect() as db:
        db.execute(
            f"UPDATE generations SET {assignments} WHERE id=?",
            (*fields.values(), generation_id),
        )


def generation_request(generation_id: str):
    """Return the request, owner, and cancellation flag used by the worker."""
    with connect() as db:
        row = db.execute("SELECT request_json, owner_id, cancel_requested FROM generations WHERE id=?", (generation_id,)).fetchone()
    if row is None:
        return None
    return json.loads(row["request_json"]), row["owner_id"], bool(row["cancel_requested"])


def request_cancel(owner_id: str, generation_id: str) -> bool:
    """Mark active work for cancellation; queued jobs can stop immediately."""
    with connect() as db:
        result = db.execute(
            "UPDATE generations SET cancel_requested=1, "
            "status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END, "
            "stage=CASE WHEN status='queued' THEN 'cancelled' ELSE stage END, updated_at=? "
            "WHERE id=? AND owner_id=? AND status IN ('queued','running')",
            (now(), generation_id, owner_id),
        )
        return result.rowcount > 0


def update_asset_moderation(asset_id: str, owner_id: str, policy_version: str, score: float) -> None:
    with connect() as db:
        db.execute(
            "UPDATE assets SET policy_version=?, nsfw_score=? WHERE id=? AND owner_id=?",
            (policy_version, score, asset_id, owner_id),
        )


def export_paths(owner_id: str, generation_id: str) -> list[str]:
    with connect() as db:
        rows = db.execute(
            "SELECT path FROM exports WHERE generation_id=? AND owner_id=? AND path IS NOT NULL",
            (generation_id, owner_id),
        ).fetchall()
    return [row["path"] for row in rows]


def remove_generation(owner_id: str, generation_id: str):
    """Delete a job and its export records, returning frame paths for cleanup."""
    with connect() as db:
        row = db.execute(
            "SELECT result_json FROM generations WHERE id=? AND owner_id=?",
            (generation_id, owner_id),
        ).fetchone()
        if row is None:
            return None
        db.execute("DELETE FROM exports WHERE generation_id=? AND owner_id=?", (generation_id, owner_id))
        db.execute("DELETE FROM generations WHERE id=? AND owner_id=?", (generation_id, owner_id))
        return json.loads(row["result_json"]) if row["result_json"] else None


def create_export(owner_id: str, generation_id: str, export_format: str, settings: dict) -> str:
    """Create an export record before building the download file."""
    export_id = uuid4().hex
    with connect() as db:
        db.execute(
            "INSERT INTO exports VALUES (?, ?, ?, 'queued', ?, ?, NULL, NULL, ?)",
            (export_id, owner_id, generation_id, export_format, json.dumps(settings), now()),
        )
    return export_id


def get_export(owner_id: str, generation_id: str, export_id: str):
    with connect() as db:
        return db.execute(
            "SELECT * FROM exports WHERE id=? AND generation_id=? AND owner_id=?",
            (export_id, generation_id, owner_id),
        ).fetchone()


def update_export(export_id: str, status: str, path: str | None = None, error: str | None = None):
    with connect() as db:
        db.execute(
            "UPDATE exports SET status=?, path=?, error_detail=? WHERE id=?",
            (status, path, error, export_id),
        )
