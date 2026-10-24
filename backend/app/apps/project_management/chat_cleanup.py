"""Bounded retention cleanup. Never deletes source project files."""

import os
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from app.core.config import settings
from app.core.storage import storage_key, s3_client, blob_session
from .chat_models import ChatAttachment, ChatMessage


def delete_chat_blob(path):
    target = Path(path).resolve()
    root = (Path(settings.UPLOAD_DIR) / "pms" / "chat").resolve()
    if not target.is_relative_to(root):
        raise ValueError("Refusing to delete outside chat storage")
    if settings.STORAGE_BACKEND == "s3":
        s3_client().delete_object(
            Bucket=settings.S3_BUCKET, Key=storage_key(str(target))
        )
    elif settings.STORAGE_BACKEND == "vercel_blob":
        from vercel.blob.sync import delete_blob

        with blob_session():
            delete_blob(storage_key(str(target)))
    target.unlink(missing_ok=True)


def cleanup_chat_uploads(db):
    now = datetime.utcnow()
    cutoff = now - timedelta(
        days=max(1, int(os.environ.get("PMS_CHAT_DELETED_FILE_RETENTION_DAYS", "30")))
    )
    deleted = db.query(ChatMessage.id).filter(ChatMessage.deleted_at < cutoff)
    rows = (
        db.query(ChatAttachment)
        .filter(
            or_(
                and_(
                    ChatAttachment.message_id.is_(None),
                    ChatAttachment.created_at < now - timedelta(hours=24),
                ),
                ChatAttachment.message_id.in_(deleted),
            )
        )
        .limit(200)
        .all()
    )
    removed = 0
    for row in rows:
        if not row.project_file_id:
            delete_chat_blob(row.path)
        db.delete(row)
        removed += 1
    db.commit()
    return {"removed": removed}
