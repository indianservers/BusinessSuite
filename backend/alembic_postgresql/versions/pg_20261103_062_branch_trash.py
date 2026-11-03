"""Recoverable branch lifecycle; no physical branch deletion."""
revision = "pg_20261103_062_branch_trash"
down_revision = "pg_20261102_061_branch_roles"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    from app.branches.models import BranchLifecycle
    BranchLifecycle.__table__.create(op.get_bind(), checkfirst=True)
    op.execute("""CREATE OR REPLACE FUNCTION suite_protect_branch_recovery() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Branches and recovery records cannot be permanently deleted; use branch Trash and Restore';
      END IF;
      IF NEW.deleted_at IS NOT NULL AND
        (NEW.retain_until IS NULL OR NEW.retain_until < NEW.deleted_at + interval '45 days'
         OR (NEW.protected_at IS NOT NULL AND NEW.retain_until < NEW.protected_at + interval '45 days')) THEN
        RAISE EXCEPTION 'Branch recovery retention must be at least 45 days';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql""")
    op.execute("CREATE TRIGGER suite_no_branch_hard_delete BEFORE DELETE ON branches FOR EACH ROW EXECUTE FUNCTION suite_protect_branch_recovery()")
    op.execute("CREATE TRIGGER suite_no_recovery_hard_delete BEFORE DELETE OR INSERT OR UPDATE ON suite_branch_lifecycle FOR EACH ROW EXECUTE FUNCTION suite_protect_branch_recovery()")


def downgrade():
    raise RuntimeError("Branch recovery history must be retained; use an audited backup restoration")
