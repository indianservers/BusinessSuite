"""Register enforced CRM feature keys without assigning roles or memberships."""
revision = "pg_20261103_063_crm_features"
down_revision = "pg_20261103_062_branch_trash"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    from app.access.feature_permissions import CRM_FEATURE_PERMISSIONS
    permissions = sa.table("permissions", sa.column("name", sa.String), sa.column("description", sa.String), sa.column("module", sa.String))
    existing = set(op.get_bind().execute(sa.select(permissions.c.name)).scalars())
    missing = [{"name":name,"description":description,"module":module} for name,description,module in CRM_FEATURE_PERMISSIONS if name not in existing]
    if missing:
        op.bulk_insert(permissions, missing)


def downgrade():
    raise RuntimeError("Feature permissions may be referenced by saved policies; do not remove them automatically")
