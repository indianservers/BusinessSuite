"""Store customer services offered and B2B/B2C/B2G market types."""
from alembic import op
import sqlalchemy as sa

revision = '20261110_076_crm_business_profile'
down_revision = '20261110_075_asset_lifecycle'
branch_labels = depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table in ("crm_leads", "crm_contacts", "crm_companies"):
        columns = {c["name"] for c in inspector.get_columns(table)}
        for field in ("services_offered", "business_types"):
            if field not in columns:
                op.add_column(table, sa.Column(field, sa.JSON(), nullable=True))


def downgrade():
    for table in ("crm_leads", "crm_contacts", "crm_companies"):
        for field in ("business_types", "services_offered"):
            op.drop_column(table, field)
