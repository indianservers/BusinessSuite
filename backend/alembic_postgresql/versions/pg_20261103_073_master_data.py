"""Shared communication channels, business relationships and partial birthdays."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261103_073_master_data"
down_revision = "pg_20261103_072_merge_contacts"
branch_labels = None
depends_on = None

def upgrade():
    if not sa.inspect(op.get_bind()).has_table('suite_contact_channels'):
        op.execute('\nCREATE TABLE suite_contact_channels (\n\tid SERIAL NOT NULL, \n\torganization_id INTEGER NOT NULL, \n\tcontact_id INTEGER, \n\taccount_id INTEGER, \n\tperson_id INTEGER, \n\tkind VARCHAR(10) NOT NULL, \n\tlabel VARCHAR(50) NOT NULL, \n\tvalue VARCHAR(254) NOT NULL, \n\tnormalized_value VARCHAR(254) NOT NULL, \n\tcountry_code VARCHAR(5), \n\tis_primary BOOLEAN NOT NULL, \n\twhatsapp BOOLEAN NOT NULL, \n\tverification_status VARCHAR(20) NOT NULL, \n\tnotes VARCHAR(500), \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_contact_channel_owner CHECK ((CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN account_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END) = 1), \n\tFOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(account_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(person_id) REFERENCES common_people (id) ON DELETE RESTRICT\n)\n\n')
        op.execute('CREATE INDEX ix_suite_contact_channels_account_id ON suite_contact_channels (account_id)')
        op.execute('CREATE INDEX ix_suite_contact_channels_contact_id ON suite_contact_channels (contact_id)')
        op.execute('CREATE INDEX ix_suite_contact_channels_normalized_value ON suite_contact_channels (normalized_value)')
        op.execute('CREATE INDEX ix_suite_contact_channels_organization_id ON suite_contact_channels (organization_id)')
        op.execute('CREATE INDEX ix_suite_contact_channels_person_id ON suite_contact_channels (person_id)')
    if not sa.inspect(op.get_bind()).has_table('suite_business_relationships'):
        op.execute('\nCREATE TABLE suite_business_relationships (\n\tid SERIAL NOT NULL, \n\torganization_id INTEGER NOT NULL, \n\tcontact_id INTEGER, \n\taccount_id INTEGER, \n\trole VARCHAR(30) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcategory VARCHAR(100), \n\tpayment_terms VARCHAR(250), \n\tcredit_limit NUMERIC(14, 2), \n\tfollow_up_at TIMESTAMP WITH TIME ZONE, \n\tnotes TEXT, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_business_relationship_owner CHECK ((CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN account_id IS NOT NULL THEN 1 ELSE 0 END) = 1), \n\tCONSTRAINT uq_contact_business_role UNIQUE (contact_id, role), \n\tCONSTRAINT uq_account_business_role UNIQUE (account_id, role), \n\tFOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(account_id) REFERENCES crm_companies (id) ON DELETE RESTRICT\n)\n\n')
        op.execute('CREATE INDEX ix_suite_business_relationships_account_id ON suite_business_relationships (account_id)')
        op.execute('CREATE INDEX ix_suite_business_relationships_contact_id ON suite_business_relationships (contact_id)')
        op.execute('CREATE INDEX ix_suite_business_relationships_organization_id ON suite_business_relationships (organization_id)')
        op.execute('CREATE INDEX ix_suite_business_relationships_role ON suite_business_relationships (role)')
    if not sa.inspect(op.get_bind()).has_table('suite_company_master_details'):
        op.execute('\nCREATE TABLE suite_company_master_details (\n\taccount_id INTEGER NOT NULL, \n\torganization_id INTEGER NOT NULL, \n\tlegal_name VARCHAR(180), \n\ttrade_name VARCHAR(180), \n\tbusiness_type VARCHAR(100), \n\taddresses JSON NOT NULL, \n\ttax_registrations JSON NOT NULL, \n\tprimary_contact_id INTEGER, \n\tversion INTEGER NOT NULL, \n\tPRIMARY KEY (account_id), \n\tFOREIGN KEY(account_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(primary_contact_id) REFERENCES crm_contacts (id) ON DELETE RESTRICT\n)\n\n')
        op.execute('CREATE INDEX ix_suite_company_master_details_organization_id ON suite_company_master_details (organization_id)')
    if not sa.inspect(op.get_bind()).has_table('suite_company_contact_links'):
        op.execute('\nCREATE TABLE suite_company_contact_links (\n\taccount_id INTEGER NOT NULL, \n\tcontact_id INTEGER NOT NULL, \n\torganization_id INTEGER NOT NULL, \n\trelationship VARCHAR(100), \n\tPRIMARY KEY (account_id, contact_id), \n\tFOREIGN KEY(account_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE RESTRICT\n)\n\n')
        op.execute('CREATE INDEX ix_suite_company_contact_links_organization_id ON suite_company_contact_links (organization_id)')
    if not sa.inspect(op.get_bind()).has_table('suite_contact_birthdays'):
        op.execute('\nCREATE TABLE suite_contact_birthdays (\n\tid SERIAL NOT NULL, \n\torganization_id INTEGER NOT NULL, \n\tcontact_id INTEGER, \n\tperson_id INTEGER, \n\temployee_id INTEGER, \n\tbirth_day INTEGER, \n\tbirth_month INTEGER, \n\tbirth_year INTEGER, \n\temail_opt_in BOOLEAN NOT NULL, \n\twhatsapp_opt_in BOOLEAN NOT NULL, \n\tsms_opt_in BOOLEAN NOT NULL, \n\treminders_enabled BOOLEAN NOT NULL, \n\tversion INTEGER NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_contact_birthday_owner CHECK ((CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END) = 1), \n\tCONSTRAINT ck_contact_birthday_parts CHECK ((birth_day IS NULL AND birth_month IS NULL AND birth_year IS NULL) OR (birth_day BETWEEN 1 AND 31 AND birth_month BETWEEN 1 AND 12 AND (birth_year IS NULL OR birth_year BETWEEN 1900 AND 9999))), \n\tUNIQUE (contact_id), \n\tFOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE RESTRICT, \n\tUNIQUE (person_id), \n\tFOREIGN KEY(person_id) REFERENCES common_people (id) ON DELETE RESTRICT, \n\tUNIQUE (employee_id), \n\tFOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT\n)\n\n')
        op.execute('CREATE INDEX ix_suite_contact_birthdays_organization_id ON suite_contact_birthdays (organization_id)')
    if not sa.inspect(op.get_bind()).has_table('suite_contact_greeting_reservations'):
        op.execute('\nCREATE TABLE suite_contact_greeting_reservations (\n\tid SERIAL NOT NULL, \n\torganization_id INTEGER NOT NULL, \n\tbirthday_id INTEGER NOT NULL, \n\tyear INTEGER NOT NULL, \n\tchannel VARCHAR(15) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_by_user_id INTEGER, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_contact_annual_greeting UNIQUE (birthday_id, year, channel), \n\tFOREIGN KEY(birthday_id) REFERENCES suite_contact_birthdays (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL\n)\n\n')
        op.execute('CREATE INDEX ix_suite_contact_greeting_reservations_organization_id ON suite_contact_greeting_reservations (organization_id)')

def downgrade():
    raise RuntimeError("Preserve contact communications, consent and identity links; use a reviewed restore")
