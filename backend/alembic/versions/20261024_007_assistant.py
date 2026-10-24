"""Private PMS assistant conversations and expiring approvals."""

from alembic import op

revision = "20261024_007"
down_revision = "20261024_006"
branch_labels = None
depends_on = None


def upgrade():
    from app.ai_operator.assistant_models import AssistantConversation, AssistantMessage

    for model in [AssistantConversation, AssistantMessage]:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    # Preserve action evidence and historical references.
    pass
