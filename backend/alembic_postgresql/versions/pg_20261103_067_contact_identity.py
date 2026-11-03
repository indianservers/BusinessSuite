"""Add explicit business contact links without publishing HR or login identities."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261103_067_contacts"
down_revision = "pg_20261103_066_wa_branch"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("suite_contact_identity_links"):
        return
    # A parallel migration path may already have created this same table.
    if sa.inspect(op.get_bind()).has_table("suite_contact_identity_links"):
        return
    op.create_table("suite_contact_identity_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("crm_contacts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("crm_leads.id", ondelete="RESTRICT"), unique=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), unique=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("common_people.id", ondelete="RESTRICT"), unique=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("crm_companies.id", ondelete="RESTRICT"), unique=True),
        sa.CheckConstraint("(CASE WHEN lead_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN account_id IS NOT NULL THEN 1 ELSE 0 END) = 1", name="ck_contact_identity_one_source"))
    op.create_index("ix_suite_contact_identity_links_organization_id", "suite_contact_identity_links", ["organization_id"])
    op.create_index("ix_suite_contact_identity_links_contact_id", "suite_contact_identity_links", ["contact_id"])
    # Historical business sources are linked by the bounded, permission-scoped
    # backfill endpoint, rather than assigning unverified historical ownership.


def downgrade():
    raise RuntimeError("Contact identity links preserve business history; use a reviewed restore")
