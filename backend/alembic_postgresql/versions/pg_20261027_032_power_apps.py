"""Standalone Power Apps draft platform; no execution worker is enabled."""
from alembic import op
import sqlalchemy as sa
revision = "pg_20261027_032_power_apps"
down_revision = "pg_20261027_031_communication"
branch_labels = None
depends_on = None

PERMISSIONS = ("view", "create", "edit", "delete", "publish", "execute", "manage_credentials", "manage_environment", "activity_view")

def org():
    return sa.Column("organization_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False)
def user(name):
    return sa.Column(name, sa.Integer(), sa.ForeignKey("users.id"), nullable=False)
def stamp(name="created_at"):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
def ident():
    return sa.Column("id", sa.Integer(), primary_key=True)
def env():
    return sa.Column("environment", sa.String(20), nullable=False)

def upgrade():
    op.create_table("power_apps_environments", ident(), org(), sa.Column("key", sa.String(20), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.UniqueConstraint("organization_id", "key", name="uq_power_environment"), sa.CheckConstraint("key IN ('development','testing','production')", name="ck_power_environment_key"))
    op.create_table("power_apps_resources", ident(), org(), env(), sa.Column("application_id", sa.String(40), nullable=False), sa.Column("name", sa.String(180), nullable=False), sa.Column("description", sa.Text(), nullable=False), user("owner_user_id"), sa.Column("status", sa.String(20), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("definition", sa.JSON(), nullable=False), stamp(), stamp("updated_at"), sa.CheckConstraint("status = 'draft'", name="ck_power_resource_draft_only"), sa.CheckConstraint("environment IN ('development','testing','production')", name="ck_power_resource_environment"))
    op.create_index("ix_power_resources_scope", "power_apps_resources", ["organization_id", "environment", "application_id"])
    op.create_table("power_apps_versions", ident(), org(), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("power_apps_resources.id", ondelete="CASCADE"), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("snapshot", sa.JSON(), nullable=False), user("owner_user_id"), user("created_by"), stamp(), sa.UniqueConstraint("resource_id", "version", name="uq_power_resource_version"))
    op.create_table("power_apps_activity", ident(), org(), env(), sa.Column("resource_id", sa.Integer()), user("owner_user_id"), user("actor_user_id"), sa.Column("action", sa.String(40), nullable=False), sa.Column("resource_name", sa.String(180), nullable=False), stamp())
    op.create_index("ix_power_activity_scope", "power_apps_activity", ["organization_id", "environment", "created_at"])
    op.create_table("power_apps_executions", ident(), org(), env(), sa.Column("resource_id", sa.Integer(), sa.ForeignKey("power_apps_resources.id"), nullable=False), user("owner_user_id"), sa.Column("workflow_version", sa.Integer(), nullable=False), user("actor_user_id"), sa.Column("idempotency_key", sa.String(180), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("attempt", sa.Integer(), nullable=False), stamp(), sa.UniqueConstraint("organization_id", "environment", "resource_id", "idempotency_key", name="uq_power_execution_idempotency"))
    op.create_index("ix_power_execution_scope", "power_apps_executions", ["organization_id", "environment", "status"])
    # Existing tenants get a development workspace only. Other environments require
    # an explicit environment administrator; no user/tenant copies are created.
    op.execute(sa.text("INSERT INTO power_apps_environments (organization_id, key, enabled) SELECT id, 'development', true FROM companies"))
    for action in PERMISSIONS:
        op.execute(sa.text("INSERT INTO permissions (name, description, module) SELECT :name, :description, 'power_apps' WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = :name)").bindparams(name="power_apps_" + action, description="Power Apps: " + action.replace("_", " ")))
    # Do not silently grant new powers to existing roles.

def downgrade():
    for table in ("power_apps_executions", "power_apps_activity", "power_apps_versions", "power_apps_resources", "power_apps_environments"):
        op.drop_table(table)
    # Permission grants are managed by the existing access center.
