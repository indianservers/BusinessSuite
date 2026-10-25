"""Intern applications with approval-gated account provisioning."""
from alembic import op
revision = "20261025_016_intern_apps"
down_revision = "20261025_015_interns"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.interns_hub.models import InternApplication
    InternApplication.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    from app.apps.interns_hub.models import InternApplication
    InternApplication.__table__.drop(op.get_bind(), checkfirst=True)
