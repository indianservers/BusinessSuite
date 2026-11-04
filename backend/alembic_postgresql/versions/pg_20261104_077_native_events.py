"""Durable native provider deliveries."""
revision = "pg_20261104_077_native_events"
down_revision = "pg_20261103_076_fin_correction"
branch_labels = None
depends_on = None
from alembic import op
from app.apps.power_apps.integrations import native_schema

def upgrade(): native_schema.upgrade(op)
def downgrade(): native_schema.downgrade(op)
