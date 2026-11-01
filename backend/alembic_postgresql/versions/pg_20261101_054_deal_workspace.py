"""Extend deals without replacing existing sales or commercial records."""
from alembic import op
import sqlalchemy as sa
revision = "pg_20261101_054_deal_workspace"
down_revision = "pg_20261101_053_deal_catalog"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("crm_services") and "currency" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("crm_services")}:
        op.add_column("crm_services", sa.Column("currency", sa.String(10), server_default="INR"))
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("crm_deals")}
    for name, kind, default in [("priority", sa.String(20), "Medium"), ("deal_type", sa.String(40), "New Business"), ("industry", sa.String(120), None), ("internal_reference", sa.String(180), None), ("planning", sa.JSON(), None), ("version", sa.Integer(), "1")]:
        if name not in columns:
            op.add_column("crm_deals", sa.Column(name, kind, server_default=default, nullable=name != "version"))
    stages = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("crm_pipeline_stages")}
    if "policy_json" not in stages:
        op.add_column("crm_pipeline_stages", sa.Column("policy_json", sa.JSON(), nullable=True))
    if not sa.inspect(op.get_bind()).has_table("crm_deal_collaborators"):
        op.create_table("crm_deal_collaborators", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer(), nullable=False), sa.Column("deal_id", sa.Integer(), sa.ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(80), nullable=False), sa.Column("watching", sa.Boolean(), nullable=False), sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("deal_id", "user_id", name="uq_crm_deal_collaborator"))
        for name in ("organization_id", "deal_id", "user_id"):
            op.create_index(f"ix_crm_deal_collaborators_{name}", "crm_deal_collaborators", [name])
    inspector = sa.inspect(op.get_bind())
    if "last_activity_at" in columns:
        sources = []
        for table in ("crm_activities", "crm_tasks", "crm_notes", "crm_call_logs", "crm_email_logs", "crm_meetings"):
            if inspector.has_table(table) and {"deal_id", "organization_id", "created_at"} <= {c["name"] for c in inspector.get_columns(table)}:
                sources.append(f"SELECT deal_id, organization_id, created_at AS stamp FROM {table}")
        if sources:
            union = " UNION ALL ".join(sources)
            op.execute(sa.text(f"UPDATE crm_deals SET last_activity_at=(SELECT MAX(stamp) FROM ({union}) AS activity WHERE activity.deal_id=crm_deals.id AND activity.organization_id=crm_deals.organization_id) WHERE last_activity_at IS NULL"))
    indices = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("crm_deals")}
    for name in ("priority", "deal_type"):
        if f"ix_crm_deals_{name}" not in indices:
            op.create_index(f"ix_crm_deals_{name}", "crm_deals", [name])


def downgrade():
    if sa.inspect(op.get_bind()).has_table("crm_services"):
        op.drop_column("crm_services", "currency")
    op.drop_table("crm_deal_collaborators")
    op.drop_column("crm_pipeline_stages", "policy_json")
    for name in ("priority", "deal_type"):
        op.drop_index(f"ix_crm_deals_{name}", table_name="crm_deals")
    for name in ("version", "planning", "internal_reference", "industry", "deal_type", "priority"):
        op.drop_column("crm_deals", name)
