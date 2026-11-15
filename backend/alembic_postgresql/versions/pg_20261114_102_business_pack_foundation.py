"""Add isolated pack contexts, grants and native-record anchors; activates nothing."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261114_102_pack_foundation'
down_revision = 'pg_20261114_101_salary_ownership'
branch_labels = depends_on = None


def _tables():
    """Historical definitions are static and never import evolving runtime models."""
    metadata = sa.MetaData()
    for name in ('companies', 'branches', 'users'):
        sa.Table(name, metadata, sa.Column('id', sa.Integer, primary_key=True))
    def identity():
        return [sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id', ondelete='RESTRICT'), nullable=False)]
    def revision():
        return sa.Column('revision', sa.Integer, nullable=False, server_default='1')
    def created():
        return sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    def updated():
        return sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    def branch():
        return sa.Column('branch_id', sa.Integer, sa.ForeignKey('branches.id', ondelete='RESTRICT'), nullable=False)
    def context_fk(name):
        return sa.ForeignKeyConstraint(['context_id', 'company_id', 'branch_id'],
            ['business_pack_contexts.id', 'business_pack_contexts.company_id', 'business_pack_contexts.branch_id'], name=name, ondelete='RESTRICT')
    activation = sa.Table('business_pack_activations', metadata, *identity(),
        sa.Column('pack_key', sa.String(64), nullable=False),
        sa.Column('pack_version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('state', sa.String(20), nullable=False, server_default='draft'), revision(), created(), updated(),
        sa.UniqueConstraint('company_id', 'pack_key', 'pack_version', name='uq_pack_activation_version'),
        sa.UniqueConstraint('id', 'company_id', 'pack_key', 'pack_version', name='uq_pack_activation_identity'),
        sa.CheckConstraint("state IN ('draft','active','suspended','retired')", name='ck_pack_activation_state'),
        sa.CheckConstraint('pack_version > 0', name='ck_pack_activation_version'),
        sa.CheckConstraint('revision > 0', name='ck_pack_activation_revision'),
        sa.CheckConstraint('length(trim(pack_key)) BETWEEN 1 AND 64', name='ck_pack_activation_key'))
    context = sa.Table('business_pack_contexts', metadata, *identity(), branch(),
        sa.Column('activation_id', sa.Integer, nullable=False), sa.Column('pack_key', sa.String(64), nullable=False),
        sa.Column('pack_version', sa.Integer, nullable=False), sa.Column('state', sa.String(20), nullable=False, server_default='draft'), revision(), created(), updated(),
        sa.UniqueConstraint('activation_id', 'branch_id', name='uq_pack_context_activation_branch'),
        sa.UniqueConstraint('id', 'company_id', 'branch_id', name='uq_pack_context_identity'),
        sa.ForeignKeyConstraint(['activation_id', 'company_id', 'pack_key', 'pack_version'],
            ['business_pack_activations.id', 'business_pack_activations.company_id', 'business_pack_activations.pack_key', 'business_pack_activations.pack_version'], name='fk_pack_context_activation_identity', ondelete='RESTRICT'),
        sa.CheckConstraint("state IN ('draft','active','suspended','retired')", name='ck_pack_context_state'),
        sa.CheckConstraint('pack_version > 0', name='ck_pack_context_version'),
        sa.CheckConstraint('revision > 0', name='ck_pack_context_revision'),
        sa.CheckConstraint('length(trim(pack_key)) BETWEEN 1 AND 64', name='ck_pack_context_key'))
    grant = sa.Table('business_pack_user_grants', metadata, *identity(), branch(),
        sa.Column('context_id', sa.Integer, nullable=False), sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('role', sa.String(64), nullable=False), sa.Column('active', sa.Boolean(create_constraint=True, name='ck_pack_user_grant_active'), nullable=False, server_default='true'), revision(), created(), updated(),
        sa.UniqueConstraint('context_id', 'user_id', name='uq_pack_user_context'), context_fk('fk_pack_user_grant_context'),
        sa.CheckConstraint('revision > 0', name='ck_pack_user_grant_revision'),
        sa.CheckConstraint('length(trim(role)) BETWEEN 1 AND 64', name='ck_pack_user_grant_role'))
    ownership = sa.Table('business_pack_record_ownership', metadata, *identity(), branch(),
        sa.Column('context_id', sa.Integer, nullable=False), sa.Column('resource_table', sa.String(120), nullable=False),
        sa.Column('resource_key', sa.String(500), nullable=False), sa.Column('source', sa.String(80), nullable=False, server_default='created'), revision(), created(),
        sa.UniqueConstraint('resource_table', 'resource_key', name='uq_pack_native_record_anchor'), context_fk('fk_pack_record_context'),
        sa.CheckConstraint('revision > 0', name='ck_pack_record_revision'),
        sa.CheckConstraint('length(trim(resource_table)) BETWEEN 1 AND 120', name='ck_pack_record_table'),
        sa.CheckConstraint('length(trim(resource_key)) BETWEEN 1 AND 500', name='ck_pack_record_key'),
        sa.CheckConstraint('length(trim(source)) BETWEEN 1 AND 80', name='ck_pack_record_source'))
    availability = sa.Table('business_pack_master_availability', metadata, *identity(), branch(),
        sa.Column('context_id', sa.Integer, nullable=False), sa.Column('resource_table', sa.String(120), nullable=False), sa.Column('resource_key', sa.String(500), nullable=False),
        sa.Column('active', sa.Boolean(create_constraint=True, name='ck_pack_master_active'), nullable=False, server_default='true'), revision(), created(), updated(),
        sa.UniqueConstraint('context_id', 'resource_table', 'resource_key', name='uq_pack_master_context'), context_fk('fk_pack_master_context'),
        sa.CheckConstraint('revision > 0', name='ck_pack_master_revision'),
        sa.CheckConstraint('length(trim(resource_table)) BETWEEN 1 AND 120', name='ck_pack_master_table'),
        sa.CheckConstraint('length(trim(resource_key)) BETWEEN 1 AND 500', name='ck_pack_master_key'))
    return activation, context, grant, ownership, availability


def upgrade():
    bind = op.get_bind()
    if not {'companies', 'branches', 'users'} <= set(sa.inspect(bind).get_table_names()):
        raise RuntimeError('Business Pack foundation requires existing company, branch and user identities')
    for table in _tables():
        table.create(bind, checkfirst=True)


def downgrade():
    # Preserve contexts/grants/source anchors across rollback. This migration
    # creates no activation rows and never changes native business records.
    pass
