"""Additive migration. Never assign historical records to an arbitrary branch."""
from app.branches.models import BranchPolicy, BranchGrant, AccountingBranchMap, BranchOwnership, BranchAudit


def upgrade(op):
    connection = op.get_bind()
    for model in (BranchPolicy, BranchGrant, AccountingBranchMap, BranchOwnership, BranchAudit):
        model.__table__.create(connection, checkfirst=True)


def downgrade():
    raise RuntimeError("Branch ownership is security-critical; restore an audited backup instead of dropping it")
