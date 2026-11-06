"""Frozen schema used by both migration tracks."""
import sqlalchemy as sa

def upgrade(op):
    op.create_table("accounting_sync_connections",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("organization_id",sa.Integer(),nullable=False),
        sa.Column("branch_id",sa.Integer(),nullable=False),
        sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("provider",sa.String(20),nullable=False),
        sa.Column("account_id",sa.String(120),nullable=False),
        sa.Column("source_connection_id",sa.String(36)),
        sa.Column("sandbox",sa.Boolean(),nullable=False),
        sa.Column("enabled",sa.Boolean(),nullable=False),
        sa.Column("last_success_at",sa.DateTime(timezone=True)),
        sa.Column("lease_until",sa.DateTime(timezone=True)),
        sa.Column("active_token",sa.String(36)),
        sa.Column("bridge_secret",sa.Text()),
        sa.UniqueConstraint("organization_id","branch_id","provider","account_id",name="uq_accounting_sync_account"))
    op.create_index("ix_accounting_sync_connections_organization_id","accounting_sync_connections",["organization_id"])
    op.create_table("accounting_sync_records",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("connection_id",sa.String(36),sa.ForeignKey("accounting_sync_connections.id",ondelete="CASCADE"),nullable=False),
        sa.Column("entity",sa.String(20),nullable=False),
        sa.Column("external_id",sa.String(160),nullable=False),
        sa.Column("data",sa.JSON(),nullable=False),
        sa.Column("fingerprint",sa.String(64),nullable=False),
        sa.Column("present",sa.Boolean(),nullable=False),
        sa.Column("seen_run_id",sa.String(36),nullable=False),
        sa.UniqueConstraint("connection_id","entity","external_id",name="uq_accounting_sync_record"))
    op.create_index("ix_accounting_sync_records_connection_id","accounting_sync_records",["connection_id"])
    op.create_table("accounting_sync_runs",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("connection_id",sa.String(36),sa.ForeignKey("accounting_sync_connections.id",ondelete="CASCADE"),nullable=False),
        sa.Column("status",sa.String(20),nullable=False),
        sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("completed_at",sa.DateTime(timezone=True)),
        sa.Column("counts",sa.JSON(),nullable=False),
        sa.Column("error",sa.String(300)))
    op.create_index("ix_accounting_sync_runs_connection_id","accounting_sync_runs",["connection_id"])

def downgrade(op):
    for table in ("accounting_sync_runs","accounting_sync_records","accounting_sync_connections"): op.drop_table(table)
