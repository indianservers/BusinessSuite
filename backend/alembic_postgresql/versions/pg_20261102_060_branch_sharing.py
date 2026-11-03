"""Explicit sharing of customer profiles without sharing their transactions."""
revision = "pg_20261102_060_branch_sharing"
down_revision = "pg_20261102_059_branch_access"
branch_labels = None
depends_on = None
from alembic import op
from app.branches.models import BranchRecordShare

def upgrade():
    BranchRecordShare.__table__.create(op.get_bind(), checkfirst=True)

def downgrade():
    raise RuntimeError("Branch sharing is security-critical; use an audited restore")
