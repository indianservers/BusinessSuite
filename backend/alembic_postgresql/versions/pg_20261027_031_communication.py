"""Add shared collaboration metadata without changing existing chat records."""
from alembic import op
import sqlalchemy as sa
revision = "pg_20261027_031_communication"
down_revision = "pg_20261027_030_security"
branch_labels = None
depends_on = None


def workspace():
    return sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("pms_workspaces.id"), nullable=False)


def stamp():
    return sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False)


def message(primary=False):
    return sa.Column("message_id", sa.Integer(), sa.ForeignKey("pms_chat_messages.id", ondelete="CASCADE"), primary_key=primary, nullable=False)


def user(primary=False):
    return sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=primary, nullable=False)


def upgrade():
    op.create_table("communication_chat_reactions", workspace(), message(True), user(True), sa.Column("emoji", sa.String(24), primary_key=True), stamp())
    op.create_table("communication_chat_pins", workspace(), message(True), user(), stamp())
    op.create_table("communication_chat_saved", workspace(), message(True), user(True), stamp())
    op.create_table("communication_chat_drafts", workspace(), sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), primary_key=True), user(True), sa.Column("thread_id", sa.Integer(), primary_key=True, server_default="0"), sa.Column("body", sa.Text(), nullable=False, server_default=""), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_table("communication_chat_revisions", sa.Column("id", sa.Integer(), primary_key=True), workspace(), message(), user(), sa.Column("body", sa.Text(), nullable=False), stamp())
    op.create_table("communication_chat_contexts", sa.Column("id", sa.Integer(), primary_key=True), workspace(), sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), nullable=False), sa.Column("module", sa.String(40), nullable=False), sa.Column("entity_type", sa.String(40), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), stamp(), sa.UniqueConstraint("workspace_id", "module", "entity_type", "entity_id", name="uq_communication_context"))
    op.create_table("communication_chat_followups", sa.Column("id", sa.Integer(), primary_key=True), workspace(), sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), nullable=False), message(), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("client_id", sa.String(80), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("title", sa.String(220), nullable=False), sa.Column("description", sa.Text(), nullable=False, server_default=""), sa.Column("priority", sa.String(12), nullable=False, server_default="Medium"), sa.Column("status", sa.String(20), nullable=False, server_default="Open"), sa.Column("due_at", sa.DateTime()), sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id")), sa.Column("reminded_at", sa.DateTime()), stamp(), sa.Column("updated_at", sa.DateTime()), sa.UniqueConstraint("conversation_id", "created_by", "client_id", name="uq_communication_followup_request"))
    op.create_table("communication_chat_preferences", workspace(), sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), primary_key=True), user(True), sa.Column("mode", sa.String(16), nullable=False, server_default="all"), sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("dnd_until", sa.DateTime()))
    op.create_table("communication_chat_presence", workspace(), sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), primary_key=True), user(True), sa.Column("seen_at", sa.DateTime(), nullable=False), sa.Column("typing_until", sa.DateTime()))
    op.create_table("communication_chat_events", sa.Column("id", sa.Integer(), primary_key=True), workspace(), sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("pms_chat_conversations.id", ondelete="CASCADE")), stamp())
    op.create_table("communication_chat_meetings", sa.Column("id", sa.Integer(), primary_key=True), workspace(), sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("pms_chat_conversations.id", ondelete="CASCADE"), nullable=False), sa.Column("event_id", sa.Integer(), sa.ForeignKey("pms_calendar_events.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("client_id", sa.String(80), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False), stamp(), sa.UniqueConstraint("conversation_id", "created_by", "client_id", name="uq_communication_meeting_request"))
    tables = {"meetings": ["conversation_id"], "events": ["conversation_id"], "preferences": [], "presence": [], "reactions": [], "pins": [], "saved": [], "drafts": [], "revisions": ["message_id"], "contexts": ["conversation_id"], "followups": ["conversation_id", "message_id", "assignee_id", "task_id"]}
    for name, columns in tables.items():
        table = "communication_chat_" + name
        for column in ["workspace_id", *columns]:
            op.create_index("ix_" + table + "_" + column, table, [column])
    op.create_index("ix_communication_followup_due", "communication_chat_followups", ["status", "due_at"])


def downgrade():
    # Explicit downgrade only; deployment always upgrades additively.
    for suffix in ["meetings", "events", "presence", "preferences", "followups", "contexts", "revisions", "drafts", "saved", "pins", "reactions"]:
        op.drop_table("communication_chat_" + suffix)
