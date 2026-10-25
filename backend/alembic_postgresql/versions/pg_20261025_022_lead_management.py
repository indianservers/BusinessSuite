"""Lead operating state and tenant workflow settings."""

from alembic import op
import sqlalchemy as sa

revision = "pg_20261025_022_leads"
down_revision = "pg_20261025_021_contact_codes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crm_lead_management_config",
        sa.Column("organization_id", sa.Integer(), primary_key=True),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_table(
        "crm_lead_operating_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("crm_leads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "organization_id", "lead_id", name="uq_crm_lead_operating_state"
        ),
    )


def downgrade():
    op.drop_table("crm_lead_operating_states")
    op.drop_table("crm_lead_management_config")
