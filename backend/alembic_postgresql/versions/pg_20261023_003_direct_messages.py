from alembic import op
from app.apps.project_management.models import PMSDirectConversation, PMSDirectMessage
revision = "pg_20261023_003"
down_revision = "Ppg_20261023_003"
branch_labels = None
depends_on = None


def upgrade():
    PMSDirectConversation.__table__.create(bind=op.get_bind(), checkfirst=True)
    PMSDirectMessage.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    PMSDirectMessage.__table__.drop(bind=op.get_bind(), checkfirst=True)
    PMSDirectConversation.__table__.drop(bind=op.get_bind(), checkfirst=True)
