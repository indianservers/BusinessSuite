"""CRM visual templates."""
from alembic import op
from app.apps.crm.template_schema import upgrade as apply, downgrade as revert
revision = "pg_20261107_087_crm_templates"
down_revision = "pg_20261107_086_accounting_jobs"
branch_labels = depends_on = None

def upgrade(): apply(op)
def downgrade(): revert(op)
