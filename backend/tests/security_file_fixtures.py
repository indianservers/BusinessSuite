"""Simulate a URL returned by an authorized upload service in metadata tests."""
from pathlib import Path
from app.core.config import settings
from app.core.storage import signed_file_url


def uploaded_reference(relative):
    return signed_file_url(str(Path(settings.UPLOAD_DIR)/relative.removeprefix('/uploads/')))
