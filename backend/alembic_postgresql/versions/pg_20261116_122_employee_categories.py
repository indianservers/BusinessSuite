"""Operational employee categories and service category selection."""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261116_122_emp_categories'
down_revision = 'pg_20261116_121_delivery_sources'
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    for table, name in [('employees', 'work_categories'), ('srm_service_booking_policies', 'employee_categories')]:
        inspector = sa.inspect(connection)
        if inspector.has_table(table) and name not in {column['name'] for column in inspector.get_columns(table)}:
            op.add_column(table, sa.Column(name, sa.JSON(), nullable=False, server_default='[]'))


def downgrade():
    for table, name in [('srm_service_booking_policies', 'employee_categories'), ('employees', 'work_categories')]:
        if sa.inspect(op.get_bind()).has_table(table):
            op.drop_column(table, name)
