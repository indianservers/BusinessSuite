"""Immutable canonical Accounts engagement creation commands; no duplicate clients."""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261115_116_accounts_birth'
down_revision = 'pg_20261115_115_pharma_returns'
branch_labels = depends_on = None

_DDL = {'postgresql': '\n'
               'CREATE TABLE business_accounts_engagement_commands (\n'
               '\tid SERIAL NOT NULL, \n'
               '\tengagement_id INTEGER NOT NULL, \n'
               '\tclient_id INTEGER NOT NULL, \n'
               '\trequest_key VARCHAR(36) NOT NULL, \n'
               '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
               '\tsource_sha256 VARCHAR(64) NOT NULL, \n'
               '\taction VARCHAR(30) NOT NULL, \n'
               '\tsource_snapshot JSON NOT NULL, \n'
               '\tresult JSON NOT NULL, \n'
               '\torganization_id INTEGER NOT NULL, \n'
               '\tbranch_id INTEGER NOT NULL, \n'
               '\tpack_context_id INTEGER NOT NULL, \n'
               '\tcreated_by INTEGER NOT NULL, \n'
               '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
               '\tPRIMARY KEY (id), \n'
               '\tCONSTRAINT fk_accounts_engagement_command_context FOREIGN KEY(pack_context_id, '
               'organization_id, branch_id) REFERENCES business_pack_contexts (id, company_id, '
               'branch_id) ON DELETE RESTRICT, \n'
               '\tCONSTRAINT uq_accounts_engagement_command_source UNIQUE (id, organization_id, '
               'branch_id, pack_context_id), \n'
               '\tCONSTRAINT uq_accounts_engagement_command_request UNIQUE (organization_id, '
               'branch_id, pack_context_id, request_key), \n'
               '\tCONSTRAINT uq_accounts_engagement_command_native UNIQUE (engagement_id), \n'
               '\tCONSTRAINT ck_accounts_engagement_command_values CHECK (action = '
               "'engagement.create' AND length(request_key)=36 AND length(request_sha256)=64 AND "
               'length(source_sha256)=64), \n'
               '\tFOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE RESTRICT, \n'
               '\tFOREIGN KEY(client_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n'
               '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
               ')\n'
               '\n',
 'sqlite': '\n'
           'CREATE TABLE business_accounts_engagement_commands (\n'
           '\tid INTEGER NOT NULL, \n'
           '\tengagement_id INTEGER NOT NULL, \n'
           '\tclient_id INTEGER NOT NULL, \n'
           '\trequest_key VARCHAR(36) NOT NULL, \n'
           '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
           '\tsource_sha256 VARCHAR(64) NOT NULL, \n'
           '\taction VARCHAR(30) NOT NULL, \n'
           '\tsource_snapshot JSON NOT NULL, \n'
           '\tresult JSON NOT NULL, \n'
           '\torganization_id INTEGER NOT NULL, \n'
           '\tbranch_id INTEGER NOT NULL, \n'
           '\tpack_context_id INTEGER NOT NULL, \n'
           '\tcreated_by INTEGER NOT NULL, \n'
           '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
           '\tPRIMARY KEY (id), \n'
           '\tCONSTRAINT fk_accounts_engagement_command_context FOREIGN KEY(pack_context_id, '
           'organization_id, branch_id) REFERENCES business_pack_contexts (id, company_id, '
           'branch_id) ON DELETE RESTRICT, \n'
           '\tCONSTRAINT uq_accounts_engagement_command_source UNIQUE (id, organization_id, '
           'branch_id, pack_context_id), \n'
           '\tCONSTRAINT uq_accounts_engagement_command_request UNIQUE (organization_id, '
           'branch_id, pack_context_id, request_key), \n'
           '\tCONSTRAINT uq_accounts_engagement_command_native UNIQUE (engagement_id), \n'
           "\tCONSTRAINT ck_accounts_engagement_command_values CHECK (action = 'engagement.create' "
           'AND length(request_key)=36 AND length(request_sha256)=64 AND '
           'length(source_sha256)=64), \n'
           '\tFOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE RESTRICT, \n'
           '\tFOREIGN KEY(client_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n'
           '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
           ')\n'
           '\n'}

def upgrade():
    connection=op.get_bind()
    if connection.dialect.name not in _DDL:
        raise RuntimeError('Unsupported Accounts engagement migration dialect')
    if not sa.inspect(connection).has_table('business_accounts_engagement_commands'):
        connection.exec_driver_sql(_DDL[connection.dialect.name])

def downgrade():
    # Durable native source identity and creation idempotency must survive.
    pass
