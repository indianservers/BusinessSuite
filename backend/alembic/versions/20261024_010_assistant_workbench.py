"""Persistent assistant workbench, policies, teaching and execution evidence."""
from alembic import op
revision = '20261024_010'
down_revision = '20261024_009'
branch_labels = None
depends_on = None


def upgrade():
    from app.ai_operator.workbench_models import AssistantArtifact, AssistantSignal
    for model in (AssistantArtifact, AssistantSignal):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass  # Keep private history and execution evidence on application rollback.
