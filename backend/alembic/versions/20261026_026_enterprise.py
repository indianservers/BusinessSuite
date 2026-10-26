"""Enterprise control plane extensions to existing services."""

from alembic import op
import sqlalchemy as sa

revision = "20261026_026_enterprise"
down_revision = "20261026_025_shared"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("tenant_subscription_plans", "tenant_subscriptions"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("config_json", sa.JSON()))
            batch.add_column(
                sa.Column("version", sa.Integer(), nullable=False, server_default="1")
            )
    with op.batch_alter_table("tenant_subscriptions") as batch:
        batch.add_column(sa.Column("company_id", sa.Integer()))
        batch.create_foreign_key(
            "fk_subscription_company", "companies", ["company_id"], ["id"]
        )
        batch.create_index(
            "ix_tenant_subscriptions_company_id", ["company_id"], unique=True
        )
    # Existing singleton subscriptions remain legacy; only the latest belongs to company 1.
    op.execute(
        sa.text(
            "UPDATE tenant_subscriptions SET company_id=1 WHERE id=(SELECT MAX(id) FROM tenant_subscriptions) AND EXISTS (SELECT 1 FROM companies WHERE id=1)"
        )
    )
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("organization_id", sa.Integer()))
        batch.create_index("ix_audit_logs_organization_id", ["organization_id"])
        batch.create_index(
            "ix_audit_company_time_status",
            ["organization_id", "created_at", "status_code"],
        )
    with op.batch_alter_table("helpdesk_tickets") as batch:
        batch.add_column(sa.Column("organization_id", sa.Integer()))
        batch.create_foreign_key(
            "fk_helpdesk_company", "companies", ["organization_id"], ["id"]
        )
        batch.create_index("ix_helpdesk_tickets_organization_id", ["organization_id"])
        batch.add_column(sa.Column("module_key", sa.String(80)))
        batch.create_index("ix_helpdesk_tickets_module_key", ["module_key"])
        batch.add_column(sa.Column("detail_json", sa.JSON()))
        batch.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.alter_column("employee_id", existing_type=sa.Integer(), nullable=True)
    op.execute(
        sa.text(
            "UPDATE helpdesk_tickets SET organization_id=(SELECT branches.company_id FROM employees JOIN branches ON branches.id=employees.branch_id WHERE employees.id=helpdesk_tickets.employee_id)"
        )
    )


def downgrade():
    # Employee-less central tickets cannot be represented in the previous schema.
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT COUNT(*) FROM helpdesk_tickets WHERE employee_id IS NULL")
        )
        .scalar()
    ):
        raise RuntimeError("Export/resolve central support tickets before downgrade")
    with op.batch_alter_table("helpdesk_tickets") as batch:
        batch.drop_index("ix_helpdesk_tickets_organization_id")
        batch.drop_index("ix_helpdesk_tickets_module_key")
        batch.drop_constraint("fk_helpdesk_company", type_="foreignkey")
        for name in ("organization_id", "module_key", "detail_json", "version"):
            batch.drop_column(name)
        batch.alter_column("employee_id", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_index("ix_audit_company_time_status")
        batch.drop_index("ix_audit_logs_organization_id")
        batch.drop_column("organization_id")
    with op.batch_alter_table("tenant_subscriptions") as batch:
        batch.drop_index("ix_tenant_subscriptions_company_id")
        batch.drop_constraint("fk_subscription_company", type_="foreignkey")
        batch.drop_column("company_id")
    for table in ("tenant_subscriptions", "tenant_subscription_plans"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("config_json")
            batch.drop_column("version")
