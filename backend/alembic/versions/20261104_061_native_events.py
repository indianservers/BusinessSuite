"""Durable native provider deliveries."""
revision = "20261104_061_native_events"
down_revision = "20261102_060_branch_roles"
branch_labels = None
depends_on = None
from alembic import op
from app.apps.power_apps.integrations import native_schema

def upgrade(): native_schema.upgrade(op)
def downgrade(): native_schema.downgrade(op)
