"""Persist CRM task form details and deduplicate browser imports."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261102_056_crm_task_sync"
down_revision = "pg_20261101_055_service_currency"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("crm_tasks")}
    if "task_details" not in columns:
        op.add_column("crm_tasks", sa.Column("task_details", sa.JSON(), nullable=True))
    if "import_key" not in columns:
        op.add_column("crm_tasks", sa.Column("import_key", sa.String(100), nullable=True))
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("crm_tasks")}
    if "uq_crm_tasks_creator_import" not in indexes:
        op.create_index("uq_crm_tasks_creator_import", "crm_tasks", ["organization_id", "created_by_user_id", "import_key"], unique=True)


def downgrade():
    op.drop_index("uq_crm_tasks_creator_import", table_name="crm_tasks")
    op.drop_column("crm_tasks", "import_key")
    op.drop_column("crm_tasks", "task_details")
