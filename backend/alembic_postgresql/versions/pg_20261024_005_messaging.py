"""Additive collaboration messaging. Preserve legacy history and identifiers."""

from alembic import op

revision = "pg_20261024_005"
down_revision = "pg_20261024_004"
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
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_pms_chat_search ON pms_chat_messages USING gin(to_tsvector('simple', body))"
        )


def downgrade():
    pass  # Retain message history during application rollback.
