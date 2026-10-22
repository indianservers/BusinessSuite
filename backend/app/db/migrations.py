"""Shared migration entry point for CLI provisioning and development startup."""
from pathlib import Path
from alembic import command
from alembic.config import Config


def upgrade_schema():
    backend = Path(__file__).resolve().parents[2]
    command.upgrade(Config(str(backend / "alembic.ini")), "head")
