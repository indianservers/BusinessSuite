"""Shared service outbox, immutable versions and existing-engine extensions."""

from alembic import op
import sqlalchemy as sa

revision = "pg_20261026_025_shared"
down_revision = "pg_20261026_024_control"
branch_labels = None
depends_on = None


TENANT_TABLES = {
    "approval_requests": "requester_user_id",
    "workflow_definitions": "created_by",
    "workflow_instances": "requester_user_id",
    "workflow_delegations": "created_by",
    "communication_email_templates": "created_by",
    "communication_email_messages": "sent_by",
    "communication_timeline_events": "actor_user_id",
    "communication_delivery_logs": None,
}


def upgrade():
    from app.shared import models

    bind = op.get_bind()
    for name in (
        "suite_service_policies",
        "suite_service_events",
        "suite_workflow_versions",
        "suite_service_documents",
    ):
        models.Base.metadata.tables[name].create(bind, checkfirst=True)
    for column in (
        sa.Column("graph_json", sa.JSON()),
        sa.Column("draft_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_version", sa.Integer()),
        sa.Column("run_as_user_id", sa.Integer(), sa.ForeignKey("users.id")),
    ):
        op.add_column("automation_workflows", column)
    for column in (
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("companies.id")),
        sa.Column("module_keys", sa.JSON()),
        sa.Column("config_json", sa.JSON()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ):
        op.add_column("integration_credentials", column)
    op.alter_column(
        "integration_credentials",
        "secret_ref",
        type_=sa.Text(),
        existing_type=sa.String(255),
    )
    for table, author in TENANT_TABLES.items():
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("organization_id", sa.Integer()))
            batch.create_foreign_key(
                "fk_" + table + "_organization",
                "companies",
                ["organization_id"],
                ["id"],
            )
            batch.create_index("ix_" + table + "_organization_id", ["organization_id"])
        if author:
            op.execute(
                sa.text(
                    f"UPDATE {table} SET organization_id = COALESCE((SELECT organization_id FROM common_people WHERE user_id = {table}.{author}), 1)"
                )
            )
        else:
            op.execute(
                sa.text(
                    f"UPDATE {table} SET organization_id = COALESCE((SELECT organization_id FROM communication_email_messages WHERE id = {table}.related_message_id), 1)"
                )
            )
    op.create_index(
        "ix_integration_credentials_organization_id",
        "integration_credentials",
        ["organization_id"],
    )
    op.execute(
        sa.text(
            "UPDATE integration_credentials SET organization_id = COALESCE((SELECT organization_id FROM common_people WHERE user_id = integration_credentials.created_by), 1)"
        )
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION suite_workflow_version_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Published workflow version is immutable'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER suite_workflow_version_immutable BEFORE UPDATE OR DELETE ON suite_workflow_versions FOR EACH ROW EXECUTE FUNCTION suite_workflow_version_immutable()"
    )


def downgrade():
    for table in reversed(TENANT_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index("ix_" + table + "_organization_id")
            batch.drop_column("organization_id")
    op.drop_index(
        "ix_integration_credentials_organization_id",
        table_name="integration_credentials",
    )
    op.execute(
        "DROP TRIGGER IF EXISTS suite_workflow_version_immutable ON suite_workflow_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS suite_workflow_version_immutable()")
    for column in (
        "graph_json",
        "draft_version",
        "published_version",
        "run_as_user_id",
    ):
        op.drop_column("automation_workflows", column)
    for column in ("organization_id", "module_keys", "config_json", "version"):
        op.drop_column("integration_credentials", column)
    for name in (
        "suite_service_documents",
        "suite_workflow_versions",
        "suite_service_events",
        "suite_service_policies",
    ):
        op.drop_table(name)
