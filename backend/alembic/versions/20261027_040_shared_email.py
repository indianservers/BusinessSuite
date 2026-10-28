from alembic import op
import sqlalchemy as sa

revision = "20261027_040_email"
down_revision = "20261027_039_intern_packs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("email_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_key", sa.String(180), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("module", sa.String(60), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=True),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_html", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("provider_message_id", sa.String(200), nullable=True),
        sa.Column("error", sa.String(240), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("event_key", name="uq_email_outbox_event_key"))
    op.create_index("ix_email_outbox_status_created", "email_outbox", ["status", "created_at"])


def downgrade():
    op.drop_table("email_outbox")
