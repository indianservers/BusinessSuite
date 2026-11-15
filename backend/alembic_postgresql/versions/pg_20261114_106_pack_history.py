"""Separate durable activation history from draft security revisions.

Unknown pre-upgrade draft history is conservatively closed. Only a verified
draft creation plus a complete master-only revision audit chain proves that an
edited historical draft never entered operational use. No source is retagged.
"""
import json
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261114_106_pack_history'
down_revision = 'pg_20261114_105_anonymous_cash'
branch_labels = depends_on = None


def _object(value):
    if isinstance(value, str):
        try: value = json.loads(value)
        except (ValueError, TypeError): return {}
    return value if isinstance(value, dict) else {}


def _verified_draft(row, audits):
    identity = ('id', 'company_id', 'branch_id', 'activation_id', 'pack_key', 'pack_version')
    creations, changes = [], []
    for audit in audits:
        if audit['company_id'] != row['company_id'] or audit.get('outcome', 'success') != 'success': continue
        before, after = _object(audit['before_json']), _object(audit['after_json'])
        if audit['operation'] == 'settings.business-packs.context.drafted' and after.get('id') == row['id']:
            if after.get('state') != 'draft' or after.get('revision') != 1 or any(after.get(key) != row[key] for key in identity): return False
            creations.append(audit['id'])
        elif audit['operation'] == 'settings.business-packs.context.activated' and after.get('id') == row['id']:
            return False
        elif audit['operation'] in ('settings.business-packs.master.shared', 'settings.business-packs.master.unshared'):
            source = _object(after.get('availability'))
            if source.get('context_id') != row['id']: continue
            if (source.get('company_id'), source.get('branch_id')) != (row['company_id'], row['branch_id']): return False
            if source.get('resource_table') not in {'employees', 'crm_companies', 'srm_products', 'srm_warehouses'}: return False
            changes.append((audit['id'], before.get('context_revision'), after.get('context_revision')))
    if len(creations) != 1 or len(changes) != row['revision'] - 1: return False
    expected = 1
    for ident, before, after in sorted(changes):
        if ident <= creations[0] or type(before) is not int or type(after) is not int or (before, after) != (expected, expected + 1): return False
        expected = after
    return expected == row['revision']


def upgrade():
    connection = op.get_bind(); inspector = sa.inspect(connection)
    name = 'business_pack_contexts'
    if not inspector.has_table(name): raise RuntimeError('Business Pack foundation must be installed first')
    missing = 'ever_activated' not in {column['name'] for column in inspector.get_columns(name)}
    if missing:
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('ALTER TABLE business_pack_contexts ADD COLUMN ever_activated BOOLEAN NOT NULL DEFAULT 0 CHECK (ever_activated IN (0,1))')
        else:
            op.add_column(name, sa.Column('ever_activated', sa.Boolean(), nullable=False, server_default=sa.false()))
        metadata = sa.MetaData()
        contexts = sa.Table(name, metadata, autoload_with=connection)
        audits = []
        if inspector.has_table('suite_access_audit'):
            table = sa.Table('suite_access_audit', metadata, autoload_with=connection)
            audits = list(connection.execute(sa.select(table).where(table.c.operation.in_(
                ('settings.business-packs.context.drafted', 'settings.business-packs.context.activated',
                 'settings.business-packs.master.shared', 'settings.business-packs.master.unshared')))).mappings())
        anchors = set()
        if inspector.has_table('business_pack_record_ownership'):
            table = sa.Table('business_pack_record_ownership', metadata, autoload_with=connection)
            anchors = set(connection.execute(sa.select(table.c.context_id)).scalars())
        for row in connection.execute(sa.select(contexts)).mappings().all():
            used = row['state'] != 'draft' or row['id'] in anchors
            # Even revision-one drafts can have explicit activation audit proof.
            activated = any(a['company_id'] == row['company_id'] and a['operation'] == 'settings.business-packs.context.activated'
                and _object(a['after_json']).get('id') == row['id'] for a in audits)
            used |= activated or row['revision'] != 1 and not _verified_draft(row, audits)
            if used:
                connection.execute(contexts.update().where(contexts.c.id == row['id']).values(ever_activated=True))
    if connection.dialect.name == 'postgresql':
        connection.exec_driver_sql('''CREATE OR REPLACE FUNCTION suite_pack_activation_history() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'UPDATE' AND OLD.ever_activated AND NOT NEW.ever_activated THEN
            RAISE EXCEPTION 'Business Pack activation history cannot be cleared';
          END IF;
          IF NEW.state <> 'draft' THEN NEW.ever_activated := true; END IF;
          IF TG_OP = 'UPDATE' AND OLD.state <> 'draft' THEN NEW.ever_activated := true; END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql''')
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS suite_pack_history ON business_pack_contexts')
        connection.exec_driver_sql('CREATE TRIGGER suite_pack_history BEFORE INSERT OR UPDATE ON business_pack_contexts FOR EACH ROW EXECUTE FUNCTION suite_pack_activation_history()')
    elif connection.dialect.name == 'sqlite':
        connection.exec_driver_sql("CREATE TRIGGER IF NOT EXISTS suite_pack_history_no_clear BEFORE UPDATE ON business_pack_contexts WHEN OLD.ever_activated <> 0 AND NEW.ever_activated <> 1 BEGIN SELECT RAISE(ABORT, 'Business Pack activation history cannot be cleared'); END")
        connection.exec_driver_sql("CREATE TRIGGER IF NOT EXISTS suite_pack_history_insert AFTER INSERT ON business_pack_contexts WHEN NEW.state <> 'draft' AND NEW.ever_activated = 0 BEGIN UPDATE business_pack_contexts SET ever_activated=1 WHERE id=NEW.id; END")
        connection.exec_driver_sql("CREATE TRIGGER IF NOT EXISTS suite_pack_history_update AFTER UPDATE ON business_pack_contexts WHEN NEW.ever_activated=0 AND (OLD.state <> 'draft' OR NEW.state <> 'draft') BEGIN UPDATE business_pack_contexts SET ever_activated=1 WHERE id=NEW.id; END")


def downgrade():
    pass  # Activation history must never be erased by a downgrade.
