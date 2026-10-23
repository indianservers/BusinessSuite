from alembic import op
from app.apps.project_management.models import PMSRunningTimer
revision = "pg_20261023_006"
down_revision = "Ppg_20261023_006"
branch_labels = None
depends_on = None


def upgrade():
    PMSRunningTimer.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    PMSRunningTimer.__table__.drop(bind=op.get_bind(), checkfirst=True)
