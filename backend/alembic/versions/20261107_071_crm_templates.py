"""CRM visual templates."""
from alembic import op
from app.apps.crm.template_schema import upgrade as apply, downgrade as revert
revision = "20261107_071_crm_templates"
down_revision = "20261107_070_accounting_jobs"
branch_labels = depends_on = None

def upgrade(): apply(op)
def downgrade(): revert(op)
