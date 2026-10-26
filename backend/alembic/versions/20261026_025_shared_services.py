"""Shared services for the SQLite migration tree."""

from alembic import op
import sqlalchemy as sa

revision = "20261026_025_shared"
down_revision = "20261026_024_control"
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
    with op.batch_alter_table("automation_workflows") as batch:
        batch.add_column(sa.Column("graph_json", sa.JSON()))
        batch.add_column(
            sa.Column("draft_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(sa.Column("published_version", sa.Integer()))
        batch.add_column(sa.Column("run_as_user_id", sa.Integer()))
        batch.create_foreign_key(
            "fk_automation_service_actor", "users", ["run_as_user_id"], ["id"]
        )
    with op.batch_alter_table("integration_credentials") as batch:
        batch.add_column(sa.Column("organization_id", sa.Integer()))
        batch.add_column(sa.Column("module_keys", sa.JSON()))
        batch.add_column(sa.Column("config_json", sa.JSON()))
        batch.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.alter_column("secret_ref", type_=sa.Text(), existing_type=sa.String(255))
        batch.create_foreign_key(
            "fk_integration_organization", "companies", ["organization_id"], ["id"]
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
        "CREATE TRIGGER suite_workflow_version_no_update BEFORE UPDATE ON suite_workflow_versions BEGIN SELECT RAISE(ABORT, 'Published workflow version is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER suite_workflow_version_no_delete BEFORE DELETE ON suite_workflow_versions BEGIN SELECT RAISE(ABORT, 'Published workflow version is immutable'); END"
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
    for table, columns in (
        (
            "automation_workflows",
            ("graph_json", "draft_version", "published_version", "run_as_user_id"),
        ),
        (
            "integration_credentials",
            ("organization_id", "module_keys", "config_json", "version"),
        ),
    ):
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.drop_column(column)
    for name in (
        "suite_service_documents",
        "suite_workflow_versions",
        "suite_service_events",
        "suite_service_policies",
    ):
        op.drop_table(name)
