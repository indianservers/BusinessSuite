"""Retained private native delivery provenance; no historical source inference."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261116_121_delivery_sources'
down_revision='pg_20261116_120_rest_split'
branch_labels=depends_on=None
DDL={'postgresql': '\nCREATE TABLE business_pack_delivery_sources (\n\tid SERIAL NOT NULL, \n\temail_outbox_id INTEGER, \n\tnotification_id INTEGER, \n\tcompany_id INTEGER NOT NULL, \n\tbranch_id INTEGER NOT NULL, \n\tcontext_id INTEGER NOT NULL, \n\tpack_key VARCHAR(60) NOT NULL, \n\tpack_version INTEGER NOT NULL, \n\tsource_table VARCHAR(120) NOT NULL, \n\tsource_key VARCHAR(500) NOT NULL, \n\tsource_kind VARCHAR(40) NOT NULL, \n\tmodule VARCHAR(60) NOT NULL, \n\tactor_user_id INTEGER NOT NULL, \n\trecipient_user_id INTEGER, \n\trecipient_email VARCHAR(254), \n\tpayload_sha256 VARCHAR(64) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT fk_pack_delivery_context FOREIGN KEY(context_id, company_id, branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_pack_delivery_email UNIQUE (email_outbox_id), \n\tCONSTRAINT uq_pack_delivery_notification UNIQUE (notification_id), \n\tCONSTRAINT ck_pack_delivery_target CHECK ((email_outbox_id IS NOT NULL AND notification_id IS NULL) OR (email_outbox_id IS NULL AND notification_id IS NOT NULL)), \n\tCONSTRAINT ck_pack_delivery_scope CHECK (company_id > 0 AND branch_id > 0 AND context_id > 0 AND pack_version > 0 AND actor_user_id > 0), \n\tCONSTRAINT ck_pack_delivery_payload CHECK (length(payload_sha256)=64 AND length(source_key)>0), \n\tFOREIGN KEY(email_outbox_id) REFERENCES email_outbox (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(notification_id) REFERENCES notifications (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)\n\n', 'sqlite': '\nCREATE TABLE business_pack_delivery_sources (\n\tid INTEGER NOT NULL, \n\temail_outbox_id INTEGER, \n\tnotification_id INTEGER, \n\tcompany_id INTEGER NOT NULL, \n\tbranch_id INTEGER NOT NULL, \n\tcontext_id INTEGER NOT NULL, \n\tpack_key VARCHAR(60) NOT NULL, \n\tpack_version INTEGER NOT NULL, \n\tsource_table VARCHAR(120) NOT NULL, \n\tsource_key VARCHAR(500) NOT NULL, \n\tsource_kind VARCHAR(40) NOT NULL, \n\tmodule VARCHAR(60) NOT NULL, \n\tactor_user_id INTEGER NOT NULL, \n\trecipient_user_id INTEGER, \n\trecipient_email VARCHAR(254), \n\tpayload_sha256 VARCHAR(64) NOT NULL, \n\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT fk_pack_delivery_context FOREIGN KEY(context_id, company_id, branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_pack_delivery_email UNIQUE (email_outbox_id), \n\tCONSTRAINT uq_pack_delivery_notification UNIQUE (notification_id), \n\tCONSTRAINT ck_pack_delivery_target CHECK ((email_outbox_id IS NOT NULL AND notification_id IS NULL) OR (email_outbox_id IS NULL AND notification_id IS NOT NULL)), \n\tCONSTRAINT ck_pack_delivery_scope CHECK (company_id > 0 AND branch_id > 0 AND context_id > 0 AND pack_version > 0 AND actor_user_id > 0), \n\tCONSTRAINT ck_pack_delivery_payload CHECK (length(payload_sha256)=64 AND length(source_key)>0), \n\tFOREIGN KEY(email_outbox_id) REFERENCES email_outbox (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(notification_id) REFERENCES notifications (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)\n\n'}
TABLE='business_pack_delivery_sources'
COLUMNS=('id', 'email_outbox_id', 'notification_id', 'company_id', 'branch_id', 'context_id', 'pack_key', 'pack_version', 'source_table', 'source_key', 'source_kind', 'module', 'actor_user_id', 'recipient_user_id', 'recipient_email', 'payload_sha256', 'created_at')


def upgrade():
    connection=op.get_bind();inspector=sa.inspect(connection)
    if not inspector.has_table('business_pack_record_ownership'):raise RuntimeError('Install immutable Pack record ownership before delivery provenance')
    if not inspector.has_table(TABLE):connection.exec_driver_sql(DDL[connection.dialect.name])
    elif not set(COLUMNS)<={column['name'] for column in inspector.get_columns(TABLE)}:raise RuntimeError('Private delivery schema is incomplete')
    install_delivery_guards(connection)


def downgrade():
    connection=op.get_bind()
    if connection.scalar(sa.text('SELECT COUNT(*) FROM '+TABLE)) or connection.scalar(sa.text('SELECT COUNT(*) FROM business_pack_record_ownership')):raise RuntimeError('Retained private origin history cannot be discarded')
    for table,prefix,_,_,_ in SPECS:
        if connection.dialect.name=='sqlite':
            for suffix in ('immutable','retained'):connection.exec_driver_sql('DROP TRIGGER IF EXISTS '+prefix+'_'+suffix)
        else:
            for suffix in ('identity','truncate'):connection.exec_driver_sql('DROP TRIGGER IF EXISTS '+prefix+'_'+suffix+' ON '+table)
            connection.exec_driver_sql('DROP FUNCTION IF EXISTS '+prefix+'_guard()')
    op.drop_table(TABLE)

OWNERSHIP = ('id', 'company_id', 'branch_id', 'context_id', 'resource_table',
    'resource_key', 'source', 'revision', 'created_at')
CERTIFICATE = ('id', 'email_outbox_id', 'notification_id', 'company_id', 'branch_id',
    'context_id', 'pack_key', 'pack_version', 'source_table', 'source_key',
    'source_kind', 'module', 'actor_user_id', 'recipient_user_id', 'recipient_email', 'payload_sha256', 'created_at')
EMAIL = ('id', 'event_key', 'organization_id', 'module', 'recipient_user_id', 'recipient',
    'subject', 'body', 'is_html', 'created_at')
EMAIL_MUTABLE = ('status', 'provider_message_id', 'error', 'attempts', 'accepted_at')
NOTIFICATION = ('id', 'company_id', 'user_id', 'title', 'message', 'module', 'event_type',
    'related_entity_type', 'related_entity_id', 'action_url', 'priority', 'channels', 'created_at')
NOTIFICATION_MUTABLE = ('is_read', 'read_at')
SPECS = (
    ('business_pack_record_ownership', 'suite_pack_anchor', OWNERSHIP, (), None),
    ('business_pack_delivery_sources', 'suite_pack_delivery', CERTIFICATE, (), None),
    ('email_outbox', 'suite_private_email', EMAIL, EMAIL_MUTABLE, 'email_outbox_id'),
    ('notifications', 'suite_private_notice', NOTIFICATION, NOTIFICATION_MUTABLE, 'notification_id'),
)


def install_delivery_guards(connection):
    """Retain origin anchors and freeze certified native delivery payloads only."""
    dialect = connection.dialect.name
    if dialect not in {'sqlite', 'postgresql'}:
        raise RuntimeError('Private delivery guards require SQLite or PostgreSQL')
    inspector = sa.inspect(connection)
    for table, _, frozen, mutable, _ in SPECS:
        if not inspector.has_table(table):
            raise RuntimeError('Private delivery guard prerequisite table is missing: ' + table)
        actual = {column['name'] for column in inspector.get_columns(table)}
        if actual != set(frozen + mutable):
            raise RuntimeError('Private delivery guard fields require reconciliation: ' + table)
    # Every identifier and predicate comes from the fixed schema above.
    for table, name, frozen, _, target in SPECS:
        predicate = ('TRUE' if target is None else
            f'EXISTS(SELECT 1 FROM business_pack_delivery_sources d WHERE d.{target}=OLD.id)')
        any_rows = ('TRUE' if target is None else
            f'EXISTS(SELECT 1 FROM business_pack_delivery_sources d WHERE d.{target} IS NOT NULL)')
        if dialect == 'sqlite':
            changed = ' OR '.join(f'NEW.{column} IS NOT OLD.{column}' for column in frozen)
            connection.exec_driver_sql(f'''CREATE TRIGGER IF NOT EXISTS {name}_immutable
                BEFORE UPDATE ON {table} WHEN ({predicate}) AND ({changed})
                BEGIN SELECT RAISE(ABORT,'Private delivery source and payload are immutable'); END''')
            connection.exec_driver_sql(f'''CREATE TRIGGER IF NOT EXISTS {name}_retained
                BEFORE DELETE ON {table} WHEN ({predicate})
                BEGIN SELECT RAISE(ABORT,'Private delivery source and payload must be retained'); END''')
        else:
            # Native channels is JSON (not JSONB); JSON has no equality operator.
            def value(prefix, column):
                item = f'{prefix}.{column}'
                return f'CAST({item} AS TEXT)' if column == 'channels' else item
            changed = ' OR '.join(f'{value("NEW", column)} IS DISTINCT FROM {value("OLD", column)}' for column in frozen)
            connection.exec_driver_sql(f'''CREATE OR REPLACE FUNCTION {name}_guard() RETURNS trigger AS $$
            BEGIN
              IF TG_OP='TRUNCATE' THEN
                IF EXISTS(SELECT 1 FROM {table} WHERE {any_rows} LIMIT 1) THEN
                  RAISE EXCEPTION 'Private delivery history must be retained' USING ERRCODE='23514';
                END IF;
                RETURN NULL;
              END IF;
              IF TG_OP='DELETE' THEN
                IF {predicate} THEN
                  RAISE EXCEPTION 'Private delivery history must be retained' USING ERRCODE='23514';
                END IF;
                RETURN OLD;
              END IF;
              IF ({predicate}) AND ({changed}) THEN
                RAISE EXCEPTION 'Private delivery source and payload are immutable' USING ERRCODE='23514';
              END IF;
              RETURN NEW;
            END; $$ LANGUAGE plpgsql''')
            connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS {name}_identity ON {table}')
            connection.exec_driver_sql(f'CREATE TRIGGER {name}_identity BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {name}_guard()')
            connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS {name}_truncate ON {table}')
            connection.exec_driver_sql(f'CREATE TRIGGER {name}_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {name}_guard()')
