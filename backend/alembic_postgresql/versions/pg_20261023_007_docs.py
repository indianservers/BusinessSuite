from alembic import op
from app.apps.project_management.models import PMSDocument, PMSDocumentRevision
revision = "pg_20261023_007"
down_revision = "Ppg_20261023_007"
branch_labels = None
depends_on = None


def upgrade():
    PMSDocument.__table__.create(bind=op.get_bind(), checkfirst=True)
    PMSDocumentRevision.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    PMSDocumentRevision.__table__.drop(bind=op.get_bind(), checkfirst=True)
    PMSDocument.__table__.drop(bind=op.get_bind(), checkfirst=True)
