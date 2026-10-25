"""Separate calling codes without modifying or guessing legacy phone values."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261025_021_contact_codes'
down_revision='pg_20261025_020_upload_source'
branch_labels=None
depends_on=None
PHONE_COLUMNS={'common_people': ['phone_number'], 'companies': ['phone'], 'branches': ['phone'], 'employees': ['phone_number', 'alternate_phone', 'whatsapp_number', 'emergency_contact_number'], 'employee_family_members': ['phone_number'], 'candidates': ['phone'], 'mfa_methods': ['phone_number'], 'whatsapp_ess_configs': ['business_phone_number'], 'whatsapp_ess_sessions': ['phone_number'], 'whatsapp_ess_messages': ['phone_number'], 'whatsapp_ess_opt_ins': ['phone_number'], 'communication_consents': ['phone'], 'crm_companies': ['phone'], 'crm_accounts': ['phone'], 'crm_contacts': ['phone', 'alternate_phone'], 'crm_leads': ['phone', 'alternate_phone'], 'crm_call_logs': ['phone_number'], 'crm_owners': ['phone'], 'fam_parties': ['phone', 'mobile'], 'fam_party_contacts': ['phone'], 'fam_warehouses': ['phone'], 'pms_clients': ['phone']}

def upgrade():
    bind=op.get_bind()
    tables=set(sa.inspect(bind).get_table_names())
    for table,phones in PHONE_COLUMNS.items():
        if table not in tables:continue
        existing={column['name'] for column in sa.inspect(bind).get_columns(table)}
        for phone in phones:
            name=phone+'_country_code'
            if name not in existing:op.add_column(table,sa.Column(name,sa.String(5),nullable=True))
    if 'communication_consents' in tables:
        constraints=sa.inspect(bind).get_unique_constraints('communication_consents')
        constraint=next((item for item in constraints if item['name']=='uq_communication_consent_subject'),None)
        if constraint and 'phone_country_code' not in constraint['column_names']:
            with op.batch_alter_table('communication_consents') as batch:
                batch.drop_constraint('uq_communication_consent_subject',type_='unique')
                batch.create_unique_constraint('uq_communication_consent_subject',['email','phone','phone_country_code','record_type','record_id','consent_type'])
    if bind.dialect.name=='postgresql':
        for table,column,length in [('users','email',254),('employees','first_name',160),('employees','last_name',160)]:
            if table in tables:op.alter_column(table,column,type_=sa.String(length))

def downgrade():
    pass  # Keep contact information and avoid truncating names or emails.
