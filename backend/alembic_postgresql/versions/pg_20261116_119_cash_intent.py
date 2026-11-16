"""Optional durable intent binding on the canonical native cash movement."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261116_119_cash_intent'
down_revision = 'pg_20261116_118_pharma_qty'
branch_labels = depends_on = None

TABLE = 'srm_pos_cash_movements'
CHECK = "(request_key IS NULL AND request_sha256 IS NULL AND request_currency IS NULL AND request_branch_id IS NULL AND request_context_id IS NULL) OR (request_key IS NOT NULL AND length(request_key)=36 AND organization_id IS NOT NULL AND created_by IS NOT NULL AND request_sha256 IS NOT NULL AND length(request_sha256)=64 AND request_currency IS NOT NULL AND length(request_currency)=3 AND request_currency=upper(request_currency) AND request_branch_id IS NOT NULL AND request_branch_id>0 AND (request_context_id IS NULL OR request_context_id>0) AND movement_type IN ('cash_in','cash_out') AND amount IS NOT NULL AND amount>0 AND amount<1000000000000)"
FIELDS = ('id', 'organization_id', 'session_id', 'movement_type', 'amount', 'reason', 'created_by', 'created_at',
          'request_key', 'request_sha256', 'request_currency', 'request_branch_id', 'request_context_id')


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(TABLE):
        raise RuntimeError('Native cash movement table must be installed before cash intents')
    if connection.dialect.name not in {'sqlite', 'postgresql'}:
        raise RuntimeError('Cash intents require PostgreSQL or SQLite')
    columns = {item['name'] for item in inspector.get_columns(TABLE)}
    if (connection.dialect.name == 'sqlite' and 'request_key' in columns
            and not any(item['name'] == 'ck_srm_cash_request_source' for item in inspector.get_check_constraints(TABLE))):
        raise RuntimeError('Partial SQLite cash intent schema requires CHECK reconciliation before activation')
    for name, kind in [('request_sha256', sa.String(64)), ('request_currency', sa.String(3)),
                       ('request_branch_id', sa.Integer()), ('request_context_id', sa.Integer())]:
        if name not in columns:
            op.add_column(TABLE, sa.Column(name, kind, nullable=True))
    if 'request_key' not in columns:
        op.add_column(TABLE, sa.Column('request_key', sa.String(36),
            sa.CheckConstraint(CHECK, name='ck_srm_cash_request_source'), nullable=True))
    inspector = sa.inspect(connection)
    if connection.execute(sa.text(f'SELECT id FROM {TABLE} WHERE NOT ({CHECK}) LIMIT 1')).first():
        raise RuntimeError('Existing cash intent provenance requires reconciliation')
    unique = {item['name']: item for item in inspector.get_unique_constraints(TABLE)}
    indexes = {item['name']: item for item in inspector.get_indexes(TABLE)}
    name = 'uq_srm_cash_company_request'
    existing = unique.get(name) or indexes.get(name)
    if existing is None:
        op.create_index(name, TABLE, ['organization_id', 'request_key'], unique=True)
    elif existing['column_names'] != ['organization_id', 'request_key'] or not existing.get('unique', True):
        raise RuntimeError('Cash intent uniqueness requires reconciliation')
    if connection.dialect.name == 'postgresql':
        if not any(item['name'] == 'ck_srm_cash_request_source' for item in inspector.get_check_constraints(TABLE)):
            op.create_check_constraint('ck_srm_cash_request_source', TABLE, CHECK)
        comparison = ' OR '.join(f'NEW.{name} IS DISTINCT FROM OLD.{name}' for name in FIELDS)
        connection.exec_driver_sql(f'''CREATE OR REPLACE FUNCTION suite_cash_intent_guard() RETURNS trigger AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            IF OLD.request_key IS NOT NULL THEN RAISE EXCEPTION 'Cash intent history must be retained' USING ERRCODE='23514'; END IF;
            RETURN OLD;
          END IF;
          IF (OLD.request_key IS NOT NULL OR NEW.request_key IS NOT NULL) AND ({comparison}) THEN
            RAISE EXCEPTION 'Cash intent source is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql''')
        connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS suite_cash_intent_immutable ON {TABLE}')
        connection.exec_driver_sql(f'CREATE TRIGGER suite_cash_intent_immutable BEFORE UPDATE OR DELETE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION suite_cash_intent_guard()')
    else:
        comparison = ' OR '.join(f'NEW.{name} IS NOT OLD.{name}' for name in FIELDS)
        connection.exec_driver_sql(f'''CREATE TRIGGER IF NOT EXISTS suite_cash_intent_immutable
            BEFORE UPDATE ON {TABLE} WHEN (OLD.request_key IS NOT NULL OR NEW.request_key IS NOT NULL)
            AND ({comparison}) BEGIN SELECT RAISE(ABORT,'Cash intent source is immutable'); END''')
        connection.exec_driver_sql(f'''CREATE TRIGGER IF NOT EXISTS suite_cash_intent_retained
            BEFORE DELETE ON {TABLE} WHEN OLD.request_key IS NOT NULL
            BEGIN SELECT RAISE(ABORT,'Cash intent history must be retained'); END''')
    _branch_history(connection)


def _branch_history(connection):
    """Native branch pointers cannot rewrite an existing bound cash source."""
    if not sa.inspect(connection).has_table('suite_branch_ownership'):
        return
    def linked(alias):
        return f"((({alias}.resource_table='srm_pos_cash_movements' AND CAST(c.id AS TEXT)={alias}.resource_key) OR ({alias}.resource_table='srm_pos_sessions' AND CAST(c.session_id AS TEXT)={alias}.resource_key)) AND c.request_key IS NOT NULL)"
    if connection.dialect.name == 'sqlite':
        differs = ' OR '.join(f'NEW.{name} IS NOT OLD.{name}' for name in ('company_id', 'branch_id', 'resource_table', 'resource_key'))
        connection.exec_driver_sql(f'''CREATE TRIGGER IF NOT EXISTS suite_cash_intent_branch_update
            BEFORE UPDATE ON suite_branch_ownership WHEN ({differs}) AND EXISTS(
                SELECT 1 FROM {TABLE} c WHERE {linked('OLD')})
            BEGIN SELECT RAISE(ABORT,'Cash intent branch history is immutable'); END''')
        connection.exec_driver_sql(f'''CREATE TRIGGER IF NOT EXISTS suite_cash_intent_branch_delete
            BEFORE DELETE ON suite_branch_ownership WHEN EXISTS(SELECT 1 FROM {TABLE} c WHERE {linked('OLD')})
            BEGIN SELECT RAISE(ABORT,'Cash intent branch history must be retained'); END''')
        connection.exec_driver_sql(f'''CREATE TRIGGER IF NOT EXISTS suite_cash_intent_branch_insert
            BEFORE INSERT ON suite_branch_ownership WHEN EXISTS(SELECT 1 FROM {TABLE} c WHERE {linked('NEW')}
                AND (c.organization_id<>NEW.company_id OR c.request_branch_id<>NEW.branch_id))
            BEGIN SELECT RAISE(ABORT,'Cash intent branch source differs'); END''')
    else:
        differs = ' OR '.join(f'NEW.{name} IS DISTINCT FROM OLD.{name}' for name in ('company_id', 'branch_id', 'resource_table', 'resource_key'))
        connection.exec_driver_sql(f'''CREATE OR REPLACE FUNCTION suite_cash_intent_branch_guard() RETURNS trigger AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            IF EXISTS(SELECT 1 FROM {TABLE} c WHERE {linked('OLD')}) THEN
              RAISE EXCEPTION 'Cash intent branch history must be retained' USING ERRCODE='23514';
            END IF;
            RETURN OLD;
          END IF;
          IF TG_OP='UPDATE' AND ({differs}) AND EXISTS(SELECT 1 FROM {TABLE} c WHERE {linked('OLD')}) THEN
            RAISE EXCEPTION 'Cash intent branch history is immutable' USING ERRCODE='23514';
          END IF;
          IF EXISTS(SELECT 1 FROM {TABLE} c WHERE {linked('NEW')}
              AND (c.organization_id<>NEW.company_id OR c.request_branch_id<>NEW.branch_id)) THEN
            RAISE EXCEPTION 'Cash intent branch source differs' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql''')
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS suite_cash_intent_branch_identity ON suite_branch_ownership')
        connection.exec_driver_sql('CREATE TRIGGER suite_cash_intent_branch_identity BEFORE INSERT OR UPDATE OR DELETE ON suite_branch_ownership FOR EACH ROW EXECUTE FUNCTION suite_cash_intent_branch_guard()')


def downgrade():
    pass  # Never erase request provenance or permit previously confirmed cash to be replayed.
