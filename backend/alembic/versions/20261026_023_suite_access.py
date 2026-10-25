"""Central module grants, membership, roles, templates and append-only audit."""
from alembic import op
import sqlalchemy as sa
revision = '20261026_023_suite_access'
down_revision = '20261025_021_contact_codes'
branch_labels = None
depends_on = None
TABLES = ["suite_access_memberships", "suite_access_policies", "suite_access_roles", "suite_access_templates", "suite_access_audit"]
def upgrade():
    from app.access import models
    tables = models.Base.metadata.tables
    bind = op.get_bind()
    for name in TABLES:
        tables[name].create(bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        op.execute("CREATE OR REPLACE FUNCTION suite_access_audit_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Access audit is append-only'; END; $$ LANGUAGE plpgsql")
        op.execute("CREATE TRIGGER suite_access_audit_immutable BEFORE UPDATE OR DELETE ON suite_access_audit FOR EACH ROW EXECUTE FUNCTION suite_access_audit_immutable()")
    else:
        op.execute("CREATE TRIGGER IF NOT EXISTS suite_access_audit_no_update BEFORE UPDATE ON suite_access_audit BEGIN SELECT RAISE(ABORT, 'Access audit is append-only'); END")
        op.execute("CREATE TRIGGER IF NOT EXISTS suite_access_audit_no_delete BEFORE DELETE ON suite_access_audit BEGIN SELECT RAISE(ABORT, 'Access audit is append-only'); END")
def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS suite_access_audit_immutable ON suite_access_audit")
        op.execute("DROP FUNCTION IF EXISTS suite_access_audit_immutable()")
    for name in reversed(TABLES): op.drop_table(name)
