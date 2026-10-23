from alembic import op
from app.apps.project_management.models import PMSWorkspaceTeam
revision = "20261023_002"
down_revision = "P20261023_002"
branch_labels = None
depends_on = None


def upgrade():
    PMSWorkspaceTeam.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    PMSWorkspaceTeam.__table__.drop(bind=op.get_bind(), checkfirst=True)
