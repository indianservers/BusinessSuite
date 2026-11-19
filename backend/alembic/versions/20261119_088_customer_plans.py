"""Add customer plan snapshots and usage audit; preserve existing catalog rows."""
revision='20261119_088_customer_plans'
down_revision='20261118_087_report_crud'
branch_labels=depends_on=None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table('catalog_customer_plans',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('offering_id',sa.Integer(),sa.ForeignKey('srm_products.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('customer_id',sa.Integer(),sa.ForeignKey('crm_companies.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('kind',sa.String(20),nullable=False),sa.Column('number',sa.String(80),nullable=False),
        sa.Column('source_key',sa.String(180),nullable=False),sa.Column('status',sa.String(30),nullable=False),
        sa.Column('start_date',sa.Date(),nullable=False),sa.Column('end_date',sa.Date()),
        sa.Column('configuration',sa.JSON(),nullable=False),sa.Column('beneficiaries',sa.JSON(),nullable=False),
        sa.Column('price_snapshot',sa.JSON(),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('organization_id','source_key',name='uq_customer_plan_source'),
        sa.CheckConstraint("kind IN ('membership','subscription')",name='ck_customer_plan_kind'),
        sa.CheckConstraint('end_date IS NULL OR end_date > start_date',name='ck_customer_plan_dates'))
    op.create_index('ix_customer_plan_renewal','catalog_customer_plans',['organization_id','status','end_date'])
    for column in ['organization_id','offering_id','customer_id']:
        op.create_index('ix_catalog_customer_plans_'+column,'catalog_customer_plans',[column])
    op.create_table('catalog_customer_entitlements',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('plan_id',sa.Integer(),sa.ForeignKey('catalog_customer_plans.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('benefit_key',sa.String(80),nullable=False),sa.Column('definition',sa.JSON(),nullable=False),
        sa.Column('remaining',sa.Numeric(18,4)),sa.Column('revision',sa.Integer(),nullable=False),
        sa.UniqueConstraint('plan_id','benefit_key',name='uq_plan_benefit'),
        sa.CheckConstraint('remaining IS NULL OR remaining >= 0',name='ck_entitlement_remaining'))
    op.create_table('catalog_usage_ledger',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('entitlement_id',sa.Integer(),sa.ForeignKey('catalog_customer_entitlements.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('request_key',sa.String(180),nullable=False),sa.Column('quantity',sa.Numeric(18,4),nullable=False),
        sa.Column('reference',sa.String(180),nullable=False),
        sa.Column('reverses_id',sa.Integer(),sa.ForeignKey('catalog_usage_ledger.id',ondelete='RESTRICT')),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('organization_id','request_key',name='uq_usage_request'),
        sa.UniqueConstraint('reverses_id',name='uq_usage_reversal'),sa.CheckConstraint('quantity != 0',name='ck_usage_nonzero'))
    op.create_table('catalog_plan_events',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('plan_id',sa.Integer(),sa.ForeignKey('catalog_customer_plans.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('request_key',sa.String(180),nullable=False),sa.Column('action',sa.String(30),nullable=False),
        sa.Column('before',sa.JSON(),nullable=False),sa.Column('after',sa.JSON(),nullable=False),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('organization_id','request_key',name='uq_plan_event_request'))
    for table,columns in [('catalog_customer_entitlements',['organization_id','plan_id']),('catalog_usage_ledger',['organization_id','entitlement_id']),('catalog_plan_events',['organization_id','plan_id'])]:
        for column in columns:op.create_index('ix_'+table+'_'+column,table,[column])

    dialect=op.get_bind().dialect.name
    if dialect=='postgresql':
        op.execute("CREATE FUNCTION catalog_reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Catalog plan history is append-only'; END $$")
        for table in ['catalog_usage_ledger','catalog_plan_events']:
            op.execute('CREATE TRIGGER '+table+'_immutable BEFORE UPDATE OR DELETE ON '+table+' FOR EACH ROW EXECUTE FUNCTION catalog_reject_history_mutation()')
    elif dialect=='sqlite':
        for table in ['catalog_usage_ledger','catalog_plan_events']:
            for action in ['UPDATE','DELETE']:
                op.execute('CREATE TRIGGER '+table+'_'+action.lower()+" BEFORE "+action+' ON '+table+" BEGIN SELECT RAISE(ABORT, 'Catalog plan history is append-only'); END")

def downgrade():
    # Financial and usage history must be explicitly archived before schema removal.
    bind=op.get_bind()
    for table in ['catalog_usage_ledger','catalog_plan_events','catalog_customer_entitlements','catalog_customer_plans']:
        if bind.execute(sa.text('SELECT COUNT(*) FROM '+table)).scalar():
            raise RuntimeError('Cannot downgrade populated customer plan tables; archive history first')
    for table in ['catalog_usage_ledger','catalog_plan_events','catalog_customer_entitlements','catalog_customer_plans']:
        op.drop_table(table)

    if op.get_bind().dialect.name=='postgresql':op.execute('DROP FUNCTION catalog_reject_history_mutation()')
