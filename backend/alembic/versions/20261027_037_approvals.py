"""Add approval metadata around existing requests, versions and Phase 3 runtime."""

from alembic import op
import sqlalchemy as sa

revision = "20261027_037_approvals"
down_revision = "20261027_036_integrations"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "power_approval_policies" not in existing:
        op.create_table(
            "power_approval_policies",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "resource_id",
                sa.Integer(),
                sa.ForeignKey("power_apps_resources.id"),
                nullable=False,
            ),
            sa.Column(
                "runtime_resource_id",
                sa.Integer(),
                sa.ForeignKey("power_apps_resources.id"),
                nullable=True,
            ),
            sa.Column(
                "published_version_id",
                sa.Integer(),
                sa.ForeignKey("power_apps_versions.id"),
                nullable=True,
            ),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.UniqueConstraint("resource_id", name=None),
        )
    if "power_approval_request_states" not in existing:
        op.create_table(
            "power_approval_request_states",
            sa.Column(
                "id",
                sa.Integer(),
                sa.ForeignKey("approval_requests.id"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "policy_id",
                sa.Integer(),
                sa.ForeignKey("power_approval_policies.id"),
                nullable=False,
            ),
            sa.Column(
                "version_id",
                sa.Integer(),
                sa.ForeignKey("power_apps_versions.id"),
                nullable=False,
            ),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("power_apps_executions.id"),
                nullable=True,
            ),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("cycle", sa.Integer(), nullable=False),
            sa.Column("fields", sa.JSON(), nullable=False),
            sa.Column(
                "active_step_id",
                sa.Integer(),
                sa.ForeignKey("power_automation_steps.id"),
                nullable=True,
            ),
            sa.Column("submission_key", sa.String(length=100), nullable=False),
            sa.Column("head_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.UniqueConstraint("run_id", name=None),
            sa.UniqueConstraint(
                "organization_id",
                "environment",
                "owner_user_id",
                "submission_key",
                name="uq_power_approval_submission",
            ),
        )
    if "power_approval_delegations" not in existing:
        op.create_table(
            "power_approval_delegations",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "alternate_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "policy_id",
                sa.Integer(),
                sa.ForeignKey("power_approval_policies.id"),
                nullable=True,
            ),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reason", sa.String(length=1000), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
        )
    if "power_approval_assignments" not in existing:
        op.create_table(
            "power_approval_assignments",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "request_id",
                sa.Integer(),
                sa.ForeignKey("approval_requests.id"),
                nullable=False,
            ),
            sa.Column(
                "step_id",
                sa.Integer(),
                sa.ForeignKey("power_automation_steps.id"),
                nullable=False,
            ),
            sa.Column("stage_name", sa.String(length=180), nullable=False),
            sa.Column("cycle", sa.Integer(), nullable=False),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "original_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=True
            ),
            sa.Column(
                "delegation_id",
                sa.Integer(),
                sa.ForeignKey("power_approval_delegations.id"),
                nullable=True,
            ),
            sa.Column("status", sa.String(length=24), nullable=False),
            sa.Column(
                "decision_actor_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column("decision_key", sa.String(length=100), nullable=True),
            sa.Column("decision_reason", sa.Text(), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.UniqueConstraint(
                "request_id",
                "step_id",
                "cycle",
                "original_user_id",
                name="uq_power_approval_assignment",
            ),
        )
    if "power_approval_attachments" not in existing:
        op.create_table(
            "power_approval_attachments",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "request_id",
                sa.Integer(),
                sa.ForeignKey("approval_requests.id"),
                nullable=False,
            ),
            sa.Column("request_revision", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("storage_path", sa.String(length=500), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
        )

    for name, table, columns in [
        (
            "ix_power_approval_state_scope",
            "power_approval_request_states",
            ["organization_id", "environment", "owner_user_id"],
        ),
        (
            "ix_power_approval_assignment_inbox",
            "power_approval_assignments",
            ["organization_id", "environment", "user_id", "status", "due_at"],
        ),
        (
            "ix_power_approval_delegation_period",
            "power_approval_delegations",
            ["organization_id", "environment", "owner_user_id", "ends_at"],
        ),
        (
            "ix_power_approval_attachment_request",
            "power_approval_attachments",
            ["request_id", "request_revision"],
        ),
    ]:
        if name not in {
            item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)
        }:
            op.create_index(name, table, columns)


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "power_approval_attachments" in existing:
        op.drop_table("power_approval_attachments")
    if "power_approval_assignments" in existing:
        op.drop_table("power_approval_assignments")
    if "power_approval_delegations" in existing:
        op.drop_table("power_approval_delegations")
    if "power_approval_request_states" in existing:
        op.drop_table("power_approval_request_states")
    if "power_approval_policies" in existing:
        op.drop_table("power_approval_policies")
