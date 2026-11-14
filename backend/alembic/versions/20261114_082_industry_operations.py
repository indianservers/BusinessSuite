"""Add branch-scoped salon and construction operational records."""
from alembic import op
revision = '20261114_082_industry'
down_revision = '20261112_081_event_delivery'
branch_labels = depends_on = None


def upgrade():
    from app.apps.srm.industry_models import IndustryRecord
    IndustryRecord.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    # Keep customer appointments, approvals and billing references on rollback.
    pass
