"""Additive collaboration messaging. Preserve legacy history and identifiers."""

from alembic import op

revision = "20261024_005"
down_revision = "20261024_004"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.project_management.chat_models import (
        ChatConversation,
        ChatMember,
        ChatMessage,
        ChatAttachment,
    )

    for model in [ChatConversation, ChatMember, ChatMessage, ChatAttachment]:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass  # Retain message history during application rollback.
