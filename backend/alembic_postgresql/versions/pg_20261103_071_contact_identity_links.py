"""Persist the explicit contact identity links required by the contact model."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261103_071_contact_links'
down_revision = 'pg_20261103_070_followup_ctx'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('suite_contact_identity_links'):
        return
    op.create_table('suite_contact_identity_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('crm_contacts.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('crm_leads.id', ondelete='RESTRICT'), unique=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='RESTRICT'), unique=True),
        sa.Column('person_id', sa.Integer(), sa.ForeignKey('common_people.id', ondelete='RESTRICT'), unique=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('crm_companies.id', ondelete='RESTRICT'), unique=True),
        sa.CheckConstraint('(CASE WHEN lead_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN account_id IS NOT NULL THEN 1 ELSE 0 END) = 1', name='ck_contact_identity_one_source'))
    for name in ['organization_id', 'contact_id']:
        op.create_index('ix_suite_contact_identity_links_'+name, 'suite_contact_identity_links', [name])


def downgrade():
    raise RuntimeError('Retain explicit identity links; use a reviewed recovery.')
