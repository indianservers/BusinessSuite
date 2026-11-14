"""Add branch-scoped salon and construction operational records."""
from alembic import op
revision = 'pg_20261114_100_industry'
down_revision = 'pg_20261114_099_media'
branch_labels = depends_on = None


def upgrade():
    from app.apps.srm.industry_models import IndustryRecord
    IndustryRecord.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    # Keep customer appointments, approvals and billing references on rollback.
    pass
