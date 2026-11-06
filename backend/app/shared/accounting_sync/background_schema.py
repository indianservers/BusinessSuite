"""Frozen background schedule and customer-link migration."""
import sqlalchemy as sa

def upgrade(op):
    for column in (
        sa.Column("auto_sync",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("interval_minutes",sa.Integer(),nullable=False,server_default="15"),
        sa.Column("next_sync_at",sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("schedule_error",sa.String(300))):
        op.add_column("accounting_sync_connections",column)
    op.create_index("ix_accounting_sync_connections_next_sync_at","accounting_sync_connections",["next_sync_at"])
    op.create_table("accounting_sync_customer_links",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("organization_id",sa.Integer(),nullable=False),
        sa.Column("branch_id",sa.Integer(),nullable=False),
        sa.Column("connection_id",sa.String(36),sa.ForeignKey("accounting_sync_connections.id",ondelete="CASCADE"),nullable=False),
        sa.Column("external_id",sa.String(160),nullable=False),
        sa.Column("crm_company_id",sa.Integer(),sa.ForeignKey("crm_companies.id",ondelete="CASCADE"),nullable=False),
        sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.UniqueConstraint("connection_id","external_id",name="uq_accounting_customer_link"))
    for field in ("organization_id","connection_id","crm_company_id"):
        op.create_index("ix_accounting_sync_customer_links_"+field,"accounting_sync_customer_links",[field])

def downgrade(op):
    op.drop_table("accounting_sync_customer_links")
    op.drop_index("ix_accounting_sync_connections_next_sync_at",table_name="accounting_sync_connections")
    with op.batch_alter_table("accounting_sync_connections") as batch:
        for field in ("schedule_error","consecutive_failures","next_sync_at","interval_minutes","auto_sync"):batch.drop_column(field)
