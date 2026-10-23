from alembic import op
from app.apps.project_management.models import PMSCustomField, PMSCustomFieldValue
revision = "20261023_001"
down_revision = "20261022_002"
branch_labels = None
depends_on = None


def upgrade():
    PMSCustomField.__table__.create(bind=op.get_bind(), checkfirst=True)
    PMSCustomFieldValue.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    PMSCustomFieldValue.__table__.drop(bind=op.get_bind(), checkfirst=True)
    PMSCustomField.__table__.drop(bind=op.get_bind(), checkfirst=True)
