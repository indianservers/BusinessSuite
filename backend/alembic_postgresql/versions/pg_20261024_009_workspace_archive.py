"""Preserve workspace records during Admin reset."""

from alembic import op

revision = "pg_20261024_009"
down_revision = "pg_20261024_008"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive

    WorkspaceArchive.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass  # Preserve soft-delete and restore evidence.
