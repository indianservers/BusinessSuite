"""Private accounting-service periods and immutable review commands."""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261115_111_accounts'
down_revision = 'pg_20261115_110_restaurant'
branch_labels = depends_on = None

_DDL = {'postgresql': [('business_accounts_periods',
                 '\n'
                 'CREATE TABLE business_accounts_periods (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tengagement_id INTEGER NOT NULL, \n'
                 '\tclient_id INTEGER NOT NULL, \n'
                 '\tstarts_on DATE NOT NULL, \n'
                 '\tends_on DATE NOT NULL, \n'
                 '\tdue_on DATE NOT NULL, \n'
                 '\ttitle VARCHAR(200) NOT NULL, \n'
                 '\tpreparer_employee_id INTEGER NOT NULL, \n'
                 '\treviewer_employee_id INTEGER NOT NULL, \n'
                 '\tstate VARCHAR(20) NOT NULL, \n'
                 '\trevision INTEGER NOT NULL, \n'
                 '\twork_revision INTEGER NOT NULL, \n'
                 '\twork_summary TEXT NOT NULL, \n'
                 '\treview_reason TEXT NOT NULL, \n'
                 '\tprepared_by_user_id INTEGER, \n'
                 '\tsubmitted_work_revision INTEGER, \n'
                 '\tapproved_work_revision INTEGER, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_accounts_period_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_accounts_period_source UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT uq_accounts_engagement_period UNIQUE (pack_context_id, engagement_id, '
                 'starts_on, ends_on), \n'
                 '\tCONSTRAINT ck_accounts_period_dates CHECK (starts_on <= ends_on AND due_on >= '
                 'starts_on), \n'
                 '\tCONSTRAINT ck_accounts_independent_staff CHECK (preparer_employee_id != '
                 'reviewer_employee_id), \n'
                 '\tCONSTRAINT ck_accounts_period_state CHECK (state IN '
                 "('draft','submitted','returned','approved') AND revision > 0 AND work_revision >= 0), \n"
                 '\tCONSTRAINT ck_accounts_preparation_author CHECK ((work_revision = 0 AND '
                 'prepared_by_user_id IS NULL) OR (work_revision > 0 AND prepared_by_user_id IS NOT '
                 'NULL)), \n'
                 "\tCONSTRAINT ck_accounts_submitted_revision CHECK (state NOT IN ('submitted','approved') "
                 'OR (work_revision > 0 AND submitted_work_revision IS NOT NULL AND submitted_work_revision '
                 '= work_revision)), \n'
                 "\tCONSTRAINT ck_accounts_approval_revision CHECK ((state = 'approved' AND "
                 'approved_work_revision IS NOT NULL AND approved_work_revision = work_revision) OR (state '
                 "!= 'approved' AND approved_work_revision IS NULL)), \n"
                 '\tFOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(client_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(preparer_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(reviewer_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(prepared_by_user_id) REFERENCES users (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('business_accounts_commands',
                 '\n'
                 'CREATE TABLE business_accounts_commands (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tperiod_id INTEGER NOT NULL, \n'
                 '\trequest_key VARCHAR(36) NOT NULL, \n'
                 '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
                 '\taction VARCHAR(30) NOT NULL, \n'
                 '\treason TEXT NOT NULL, \n'
                 '\tresult JSON NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_accounts_command_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_accounts_command_source UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT fk_accounts_command_period FOREIGN KEY(period_id, organization_id, branch_id, '
                 'pack_context_id) REFERENCES business_accounts_periods (id, organization_id, branch_id, '
                 'pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_accounts_command_request UNIQUE (organization_id, branch_id, '
                 'pack_context_id, request_key), \n'
                 '\tCONSTRAINT ck_accounts_command_request CHECK (length(request_key)=36 AND '
                 'length(request_sha256)=64), \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [])],
 'sqlite': [('business_accounts_periods',
             '\n'
             'CREATE TABLE business_accounts_periods (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tengagement_id INTEGER NOT NULL, \n'
             '\tclient_id INTEGER NOT NULL, \n'
             '\tstarts_on DATE NOT NULL, \n'
             '\tends_on DATE NOT NULL, \n'
             '\tdue_on DATE NOT NULL, \n'
             '\ttitle VARCHAR(200) NOT NULL, \n'
             '\tpreparer_employee_id INTEGER NOT NULL, \n'
             '\treviewer_employee_id INTEGER NOT NULL, \n'
             '\tstate VARCHAR(20) NOT NULL, \n'
             '\trevision INTEGER NOT NULL, \n'
             '\twork_revision INTEGER NOT NULL, \n'
             '\twork_summary TEXT NOT NULL, \n'
             '\treview_reason TEXT NOT NULL, \n'
             '\tprepared_by_user_id INTEGER, \n'
             '\tsubmitted_work_revision INTEGER, \n'
             '\tapproved_work_revision INTEGER, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_accounts_period_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_accounts_period_source UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT uq_accounts_engagement_period UNIQUE (pack_context_id, engagement_id, starts_on, '
             'ends_on), \n'
             '\tCONSTRAINT ck_accounts_period_dates CHECK (starts_on <= ends_on AND due_on >= starts_on), \n'
             '\tCONSTRAINT ck_accounts_independent_staff CHECK (preparer_employee_id != '
             'reviewer_employee_id), \n'
             '\tCONSTRAINT ck_accounts_period_state CHECK (state IN '
             "('draft','submitted','returned','approved') AND revision > 0 AND work_revision >= 0), \n"
             '\tCONSTRAINT ck_accounts_preparation_author CHECK ((work_revision = 0 AND prepared_by_user_id '
             'IS NULL) OR (work_revision > 0 AND prepared_by_user_id IS NOT NULL)), \n'
             "\tCONSTRAINT ck_accounts_submitted_revision CHECK (state NOT IN ('submitted','approved') OR "
             '(work_revision > 0 AND submitted_work_revision IS NOT NULL AND submitted_work_revision = '
             'work_revision)), \n'
             "\tCONSTRAINT ck_accounts_approval_revision CHECK ((state = 'approved' AND "
             'approved_work_revision IS NOT NULL AND approved_work_revision = work_revision) OR (state != '
             "'approved' AND approved_work_revision IS NULL)), \n"
             '\tFOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(client_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(preparer_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(reviewer_employee_id) REFERENCES employees (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(prepared_by_user_id) REFERENCES users (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('business_accounts_commands',
             '\n'
             'CREATE TABLE business_accounts_commands (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tperiod_id INTEGER NOT NULL, \n'
             '\trequest_key VARCHAR(36) NOT NULL, \n'
             '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
             '\taction VARCHAR(30) NOT NULL, \n'
             '\treason TEXT NOT NULL, \n'
             '\tresult JSON NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_accounts_command_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_accounts_command_source UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT fk_accounts_command_period FOREIGN KEY(period_id, organization_id, branch_id, '
             'pack_context_id) REFERENCES business_accounts_periods (id, organization_id, branch_id, '
             'pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_accounts_command_request UNIQUE (organization_id, branch_id, pack_context_id, '
             'request_key), \n'
             '\tCONSTRAINT ck_accounts_command_request CHECK (length(request_key)=36 AND '
             'length(request_sha256)=64), \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [])]}

def upgrade():
    connection=op.get_bind()
    dialect=connection.dialect.name
    if dialect not in _DDL:
        raise RuntimeError('Unsupported Accounts migration dialect')
    for name,ddl,indexes in _DDL[dialect]:
        if not sa.inspect(connection).has_table(name):
            connection.exec_driver_sql(ddl)
        installed={index['name'] for index in sa.inspect(connection).get_indexes(name)}
        for index,sql in indexes:
            if index not in installed:
                connection.exec_driver_sql(sql)

def downgrade():
    # Retain service periods and immutable review authorship.
    pass
