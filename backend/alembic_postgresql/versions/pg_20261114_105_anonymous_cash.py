"""Add explicit scoped anonymous counter ledger accounts; enables none."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261114_105_anonymous_cash'
down_revision='pg_20261114_104_collection'
branch_labels=depends_on=None
_DDL={'postgresql': ('\n'
                'CREATE TABLE srm_anonymous_cash_accounts (\n'
                '\tid SERIAL NOT NULL, \n'
                '\torganization_id INTEGER NOT NULL, \n'
                '\tbranch_id INTEGER NOT NULL, \n'
                '\tpack_context_id INTEGER, \n'
                '\tcustomer_id INTEGER NOT NULL, \n'
                "\tkind VARCHAR(32) DEFAULT 'anonymous_cash' NOT NULL, \n"
                '\tjurisdiction_country VARCHAR(2) NOT NULL, \n'
                '\taccount_label VARCHAR(180) NOT NULL, \n'
                "\tactive BOOLEAN DEFAULT 'true' NOT NULL, \n"
                "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                '\tcreated_by INTEGER NOT NULL, \n'
                '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                '\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                '\tPRIMARY KEY (id), \n'
                '\tFOREIGN KEY(pack_context_id, organization_id, branch_id) REFERENCES '
                'business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
                "\tCONSTRAINT ck_anonymous_cash_kind CHECK (kind='anonymous_cash'), \n"
                '\tCONSTRAINT ck_anonymous_cash_context CHECK (pack_context_id IS NULL OR '
                'pack_context_id>0), \n'
                '\tCONSTRAINT ck_anonymous_cash_revision CHECK (revision>0 AND '
                'length(jurisdiction_country)=2), \n'
                '\tFOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT, \n'
                '\tUNIQUE (customer_id), \n'
                '\tFOREIGN KEY(customer_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n'
                '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                ')\n'
                '\n',
                [('uq_anonymous_cash_legacy',
                  'CREATE UNIQUE INDEX uq_anonymous_cash_legacy ON srm_anonymous_cash_accounts '
                  '(organization_id, branch_id) WHERE pack_context_id IS NULL'),
                 ('uq_anonymous_cash_pack',
                  'CREATE UNIQUE INDEX uq_anonymous_cash_pack ON srm_anonymous_cash_accounts '
                  '(organization_id, branch_id, pack_context_id) WHERE pack_context_id IS NOT '
                  'NULL')]),
 'sqlite': ('\n'
            'CREATE TABLE srm_anonymous_cash_accounts (\n'
            '\tid INTEGER NOT NULL, \n'
            '\torganization_id INTEGER NOT NULL, \n'
            '\tbranch_id INTEGER NOT NULL, \n'
            '\tpack_context_id INTEGER, \n'
            '\tcustomer_id INTEGER NOT NULL, \n'
            "\tkind VARCHAR(32) DEFAULT 'anonymous_cash' NOT NULL, \n"
            '\tjurisdiction_country VARCHAR(2) NOT NULL, \n'
            '\taccount_label VARCHAR(180) NOT NULL, \n'
            "\tactive BOOLEAN DEFAULT 'true' NOT NULL, \n"
            "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
            '\tcreated_by INTEGER NOT NULL, \n'
            '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
            '\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
            '\tPRIMARY KEY (id), \n'
            '\tFOREIGN KEY(pack_context_id, organization_id, branch_id) REFERENCES '
            'business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
            "\tCONSTRAINT ck_anonymous_cash_kind CHECK (kind='anonymous_cash'), \n"
            '\tCONSTRAINT ck_anonymous_cash_context CHECK (pack_context_id IS NULL OR '
            'pack_context_id>0), \n'
            '\tCONSTRAINT ck_anonymous_cash_revision CHECK (revision>0 AND '
            'length(jurisdiction_country)=2), \n'
            '\tFOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE RESTRICT, \n'
            '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT, \n'
            '\tUNIQUE (customer_id), \n'
            '\tFOREIGN KEY(customer_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n'
            '\tCONSTRAINT ck_anonymous_cash_active CHECK (active IN (0, 1)), \n'
            '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
            ')\n'
            '\n',
            [('uq_anonymous_cash_legacy',
              'CREATE UNIQUE INDEX uq_anonymous_cash_legacy ON srm_anonymous_cash_accounts '
              '(organization_id, branch_id) WHERE pack_context_id IS NULL'),
             ('uq_anonymous_cash_pack',
              'CREATE UNIQUE INDEX uq_anonymous_cash_pack ON srm_anonymous_cash_accounts '
              '(organization_id, branch_id, pack_context_id) WHERE pack_context_id IS NOT NULL')])}

def upgrade():
    bind=op.get_bind()
    ddl,indexes=_DDL[bind.dialect.name]
    if not sa.inspect(bind).has_table('srm_anonymous_cash_accounts'):op.execute(sa.text(ddl))
    present={i['name'] for i in sa.inspect(bind).get_indexes('srm_anonymous_cash_accounts')}
    for name,sql in indexes:
        if name not in present:op.execute(sa.text(sql))

def downgrade():
    # Financial source identity is retained deliberately.
    pass

