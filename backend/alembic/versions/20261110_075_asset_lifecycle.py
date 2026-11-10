"""Extend existing asset records; documents, approvals and audit stay shared."""
from alembic import op
import sqlalchemy as sa

revision = '20261110_075_asset_lifecycle'
down_revision = '20261108_074_employee_bgv'
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("assets")}
    if "details" not in existing:
        op.add_column("assets", sa.Column("details", sa.JSON(), nullable=False, server_default="{}"))
    columns = [
        sa.Column("expected_return_date", sa.Date()),
        sa.Column("handover_group", sa.String(80)),
        sa.Column("accessories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("return_details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("inspection_status", sa.String(30), nullable=False, server_default="Not Required"),
        sa.Column("inspection_approval_id", sa.Integer()),
        sa.Column("recovery_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("recovery_status", sa.String(30), nullable=False, server_default="None"),
        sa.Column("recovery_approval_id", sa.Integer()),
    ]
    existing = {c["name"] for c in sa.inspect(bind).get_columns("asset_assignments")}
    for column in columns:
        if column.name not in existing:
            op.add_column("asset_assignments", column)
    # Never silently discard historical duplicate custody. Stop for reconciliation.
    duplicates = bind.execute(sa.text("SELECT asset_id FROM asset_assignments WHERE is_active = true GROUP BY asset_id HAVING count(*) > 1")).first()
    if duplicates:
        raise RuntimeError("Reconcile duplicate active asset custody before upgrading (asset %s)" % duplicates[0])
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("asset_assignments")}
    if "uq_asset_active_custody" not in indexes:
        op.create_index("uq_asset_active_custody", "asset_assignments", ["asset_id"], unique=True,
                        postgresql_where=sa.text("is_active = true"), sqlite_where=sa.text("is_active = 1"))
    if "ix_asset_custody_due" not in indexes:
        op.create_index("ix_asset_custody_due", "asset_assignments", ["is_active", "expected_return_date"])
    if "ix_asset_assignments_handover_group" not in indexes:
        op.create_index("ix_asset_assignments_handover_group", "asset_assignments", ["handover_group"])
    if bind.dialect.name == "postgresql":
        names = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys("asset_assignments")}
        for field in ("inspection_approval_id", "recovery_approval_id"):
            name = "fk_asset_assignment_" + field
            if name not in names and not any(field in fk["constrained_columns"] for fk in sa.inspect(bind).get_foreign_keys("asset_assignments")):
                op.create_foreign_key(name, "asset_assignments", "approval_requests", [field], ["id"], ondelete="RESTRICT")


def downgrade():
    raise RuntimeError("Asset custody and inspection evidence must be retained; restore a pre-migration backup for rollback")
