from alembic import op
from app.apps.project_management.models import PMSTaskType
revision = "pg_20261023_004"
down_revision = "pg_20261023_003"
branch_labels = None
depends_on = None


def upgrade():
    PMSTaskType.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    PMSTaskType.__table__.drop(bind=op.get_bind(), checkfirst=True)
