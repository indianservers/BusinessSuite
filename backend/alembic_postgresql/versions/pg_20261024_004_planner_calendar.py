"""Personal planner preferences and calendar events."""
from alembic import op
import sqlalchemy as sa
revision = "pg_20261024_004"
down_revision = "pg_20261024_003"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.project_management.models import PMSPlannerPreference, PMSCalendarEvent
    for model in [PMSPlannerPreference, PMSCalendarEvent]:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    pass  # Preserve personal schedules and preferences during application rollback.
