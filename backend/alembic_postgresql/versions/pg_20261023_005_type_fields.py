from alembic import op
import sqlalchemy as sa
revision = "pg_20261023_005"
down_revision = "pg_20261023_004"
branch_labels = None
depends_on = None


def upgrade():
    for table, column, length in [("pms_task_types", "plural_name", 60), ("pms_custom_fields", "task_type", 40)]:
        if column not in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column(column, sa.String(length), nullable=False, server_default=""))


def downgrade():
    op.drop_column("pms_custom_fields", "task_type")
    op.drop_column("pms_task_types", "plural_name")
