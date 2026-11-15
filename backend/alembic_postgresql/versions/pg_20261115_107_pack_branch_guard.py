"""Keep native branch metadata subordinate to immutable private pack anchors."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261115_107_pack_owner'
down_revision='pg_20261114_106_pack_history'
branch_labels=depends_on=None


def upgrade():
    connection=op.get_bind();inspector=sa.inspect(connection)
    if not all(inspector.has_table(name) for name in ('business_pack_record_ownership','suite_branch_ownership')):
        raise RuntimeError('Pack and native branch ownership foundations must be installed first')
    if connection.dialect.name=='sqlite':
        statements=[
        '''CREATE TRIGGER IF NOT EXISTS suite_pack_branch_insert BEFORE INSERT ON suite_branch_ownership
        WHEN EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=NEW.resource_table AND p.resource_key=NEW.resource_key AND (p.company_id<>NEW.company_id OR p.branch_id<>NEW.branch_id))
        BEGIN SELECT RAISE(ABORT,'Pack-private branch identity is immutable'); END''',
        '''CREATE TRIGGER IF NOT EXISTS suite_pack_branch_update BEFORE UPDATE ON suite_branch_ownership
        WHEN EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=OLD.resource_table AND p.resource_key=OLD.resource_key)
        AND (NEW.resource_table<>OLD.resource_table OR NEW.resource_key<>OLD.resource_key OR NEW.company_id<>OLD.company_id OR NEW.branch_id<>OLD.branch_id)
        OR EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=NEW.resource_table AND p.resource_key=NEW.resource_key AND (p.company_id<>NEW.company_id OR p.branch_id<>NEW.branch_id))
        BEGIN SELECT RAISE(ABORT,'Pack-private branch identity is immutable'); END''',
        '''CREATE TRIGGER IF NOT EXISTS suite_pack_branch_delete BEFORE DELETE ON suite_branch_ownership
        WHEN EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=OLD.resource_table AND p.resource_key=OLD.resource_key)
        BEGIN SELECT RAISE(ABORT,'Pack-private branch ownership history must be retained'); END''']
    elif connection.dialect.name=='postgresql':
        statements=[
        '''CREATE OR REPLACE FUNCTION suite_pack_branch_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            IF EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=OLD.resource_table AND p.resource_key=OLD.resource_key) THEN
              RAISE EXCEPTION 'Pack-private branch ownership history must be retained' USING ERRCODE='23514';
            END IF;
            RETURN OLD;
          END IF;
          IF TG_OP='UPDATE' THEN
            IF EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=OLD.resource_table AND p.resource_key=OLD.resource_key)
            AND (NEW.resource_table,NEW.resource_key,NEW.company_id,NEW.branch_id) IS DISTINCT FROM (OLD.resource_table,OLD.resource_key,OLD.company_id,OLD.branch_id) THEN
              RAISE EXCEPTION 'Pack-private branch identity is immutable' USING ERRCODE='23514';
            END IF;
          END IF;
          IF EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=NEW.resource_table AND p.resource_key=NEW.resource_key AND (p.company_id<>NEW.company_id OR p.branch_id<>NEW.branch_id)) THEN
            RAISE EXCEPTION 'Pack-private branch identity is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$''',
        'DROP TRIGGER IF EXISTS suite_pack_branch_identity ON suite_branch_ownership',
        'CREATE TRIGGER suite_pack_branch_identity BEFORE INSERT OR UPDATE OR DELETE ON suite_branch_ownership FOR EACH ROW EXECUTE FUNCTION suite_pack_branch_identity_guard()']
    else:raise RuntimeError('Pack branch ownership guard requires PostgreSQL or SQLite')
    if inspector.has_table('suite_branch_record_shares'):
        if connection.dialect.name=='sqlite':
            for action in ('INSERT','UPDATE'):
                statements.append(f"""CREATE TRIGGER IF NOT EXISTS suite_pack_share_{action.lower()} BEFORE {action} ON suite_branch_record_shares
                WHEN EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=NEW.resource_table AND p.resource_key=NEW.resource_key AND (p.company_id<>NEW.company_id OR p.branch_id<>NEW.branch_id))
                BEGIN SELECT RAISE(ABORT,'Pack-private source cannot be shared to another branch'); END""")
        else:
            statements.extend([
            """CREATE OR REPLACE FUNCTION suite_pack_share_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF EXISTS(SELECT 1 FROM business_pack_record_ownership p WHERE p.resource_table=NEW.resource_table AND p.resource_key=NEW.resource_key AND (p.company_id<>NEW.company_id OR p.branch_id<>NEW.branch_id)) THEN
                RAISE EXCEPTION 'Pack-private source cannot be shared to another branch' USING ERRCODE='23514';
              END IF;
              RETURN NEW;
            END $$""",
            'DROP TRIGGER IF EXISTS suite_pack_share_identity ON suite_branch_record_shares',
            'CREATE TRIGGER suite_pack_share_identity BEFORE INSERT OR UPDATE ON suite_branch_record_shares FOR EACH ROW EXECUTE FUNCTION suite_pack_share_guard()'])
    for statement in statements:connection.exec_driver_sql(statement)


def downgrade():
    # Preserve durable source/branch history safeguards on application rollback.
    pass

