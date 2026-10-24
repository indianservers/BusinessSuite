"""Workspace recovery points, policies and durable edit history."""

from alembic import op

revision = "pg_20261024_008"
down_revision = "pg_20261024_007"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.project_management.recovery_models import (
        RecoveryChange,
        RecoveryPoint,
        RecoveryPolicy,
    )

    for model in (RecoveryChange, RecoveryPoint, RecoveryPolicy):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    # Recovery evidence is retained on rollback.
    pass
