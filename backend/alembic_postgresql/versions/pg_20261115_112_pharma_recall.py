"""Private recall history and canonical quantity-free batch state revisions."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261115_112_pharma_recall'
down_revision='pg_20261115_111_accounts'
branch_labels=depends_on=None

_DDL = {'postgresql': [('business_pharma_batch_controls',
                 '\n'
                 'CREATE TABLE business_pharma_batch_controls (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbatch_id INTEGER NOT NULL, \n'
                 '\trevision INTEGER NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT uq_pharma_batch_control UNIQUE (batch_id), \n'
                 '\tCONSTRAINT ck_pharma_batch_control_revision CHECK (revision > 0), \n'
                 '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('business_pharma_recalls',
                 '\n'
                 'CREATE TABLE business_pharma_recalls (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tbatch_id INTEGER NOT NULL, \n'
                 '\tproduct_id INTEGER NOT NULL, \n'
                 '\twarehouse_id INTEGER NOT NULL, \n'
                 '\tbatch_number VARCHAR(120) NOT NULL, \n'
                 '\texpiry_date DATE NOT NULL, \n'
                 '\treason TEXT NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tstate VARCHAR(12) NOT NULL, \n'
                 '\trevision INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_pharma_recall_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_pharma_recall_scope UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 "\tCONSTRAINT ck_pharma_recall_state CHECK (state IN ('open','closed') AND revision > 0), \n"
                 '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [('ix_business_pharma_recalls_organization_id',
                   'CREATE INDEX ix_business_pharma_recalls_organization_id ON business_pharma_recalls '
                   '(organization_id)')]),
                ('business_pharma_recall_events',
                 '\n'
                 'CREATE TABLE business_pharma_recall_events (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\trecall_id INTEGER NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\trequest_key VARCHAR(36) NOT NULL, \n'
                 '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\taction VARCHAR(16) NOT NULL, \n'
                 '\treason TEXT NOT NULL, \n'
                 '\trevision INTEGER NOT NULL, \n'
                 '\tstate_after VARCHAR(12) NOT NULL, \n'
                 '\tbatch_status_before VARCHAR(40) NOT NULL, \n'
                 '\tbatch_status_after VARCHAR(40) NOT NULL, \n'
                 '\tbatch_revision_before INTEGER NOT NULL, \n'
                 '\tbatch_revision_after INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_pharma_recall_event_root FOREIGN KEY(recall_id, organization_id, '
                 'branch_id, pack_context_id) REFERENCES business_pharma_recalls (id, organization_id, '
                 'branch_id, pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_pharma_recall_request UNIQUE (organization_id, branch_id, pack_context_id, '
                 'request_key), \n'
                 '\tCONSTRAINT uq_pharma_recall_event_revision UNIQUE (recall_id, revision), \n'
                 '\tCONSTRAINT ck_pharma_recall_event_action CHECK (action IN '
                 "('quarantine','recall','close') AND state_after IN ('open','closed')), \n"
                 '\tCONSTRAINT ck_pharma_recall_event_revision CHECK (revision > 0 AND batch_revision_before '
                 '>= 0 AND batch_revision_after >= batch_revision_before), \n'
                 '\tCONSTRAINT ck_pharma_recall_event_request CHECK (length(request_key)=36 AND '
                 'length(request_sha256)=64), \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [('ix_business_pharma_recall_events_organization_id',
                   'CREATE INDEX ix_business_pharma_recall_events_organization_id ON '
                   'business_pharma_recall_events (organization_id)')])],
 'sqlite': [('business_pharma_batch_controls',
             '\n'
             'CREATE TABLE business_pharma_batch_controls (\n'
             '\tid INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbatch_id INTEGER NOT NULL, \n'
             '\trevision INTEGER NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT uq_pharma_batch_control UNIQUE (batch_id), \n'
             '\tCONSTRAINT ck_pharma_batch_control_revision CHECK (revision > 0), \n'
             '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('business_pharma_recalls',
             '\n'
             'CREATE TABLE business_pharma_recalls (\n'
             '\tid INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tbatch_id INTEGER NOT NULL, \n'
             '\tproduct_id INTEGER NOT NULL, \n'
             '\twarehouse_id INTEGER NOT NULL, \n'
             '\tbatch_number VARCHAR(120) NOT NULL, \n'
             '\texpiry_date DATE NOT NULL, \n'
             '\treason TEXT NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tstate VARCHAR(12) NOT NULL, \n'
             '\trevision INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_pharma_recall_context FOREIGN KEY(pack_context_id, organization_id, branch_id) '
             'REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_pharma_recall_scope UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             "\tCONSTRAINT ck_pharma_recall_state CHECK (state IN ('open','closed') AND revision > 0), \n"
             '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [('ix_business_pharma_recalls_organization_id',
               'CREATE INDEX ix_business_pharma_recalls_organization_id ON business_pharma_recalls '
               '(organization_id)')]),
            ('business_pharma_recall_events',
             '\n'
             'CREATE TABLE business_pharma_recall_events (\n'
             '\tid INTEGER NOT NULL, \n'
             '\trecall_id INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\trequest_key VARCHAR(36) NOT NULL, \n'
             '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\taction VARCHAR(16) NOT NULL, \n'
             '\treason TEXT NOT NULL, \n'
             '\trevision INTEGER NOT NULL, \n'
             '\tstate_after VARCHAR(12) NOT NULL, \n'
             '\tbatch_status_before VARCHAR(40) NOT NULL, \n'
             '\tbatch_status_after VARCHAR(40) NOT NULL, \n'
             '\tbatch_revision_before INTEGER NOT NULL, \n'
             '\tbatch_revision_after INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_pharma_recall_event_root FOREIGN KEY(recall_id, organization_id, branch_id, '
             'pack_context_id) REFERENCES business_pharma_recalls (id, organization_id, branch_id, '
             'pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_pharma_recall_request UNIQUE (organization_id, branch_id, pack_context_id, '
             'request_key), \n'
             '\tCONSTRAINT uq_pharma_recall_event_revision UNIQUE (recall_id, revision), \n'
             "\tCONSTRAINT ck_pharma_recall_event_action CHECK (action IN ('quarantine','recall','close') "
             "AND state_after IN ('open','closed')), \n"
             '\tCONSTRAINT ck_pharma_recall_event_revision CHECK (revision > 0 AND batch_revision_before >= '
             '0 AND batch_revision_after >= batch_revision_before), \n'
             '\tCONSTRAINT ck_pharma_recall_event_request CHECK (length(request_key)=36 AND '
             'length(request_sha256)=64), \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [('ix_business_pharma_recall_events_organization_id',
               'CREATE INDEX ix_business_pharma_recall_events_organization_id ON '
               'business_pharma_recall_events (organization_id)')])]}

def upgrade():
    connection=op.get_bind()
    dialect=connection.dialect.name
    if dialect not in _DDL:raise RuntimeError('Unsupported Pharma migration dialect')
    for name,ddl,indexes in _DDL[dialect]:
        if not sa.inspect(connection).has_table(name):connection.exec_driver_sql(ddl)
        installed={index['name'] for index in sa.inspect(connection).get_indexes(name)}
        for index,sql in indexes:
            if index not in installed:connection.exec_driver_sql(sql)
    if dialect=='postgresql':
        connection.exec_driver_sql('''
        CREATE OR REPLACE FUNCTION business_pharma_recall_event_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Pharma recall event history is immutable' USING ERRCODE='23514';
        END $$''')
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS business_pharma_recall_event_immutable ON business_pharma_recall_events')
        connection.exec_driver_sql('CREATE TRIGGER business_pharma_recall_event_immutable BEFORE UPDATE OR DELETE ON business_pharma_recall_events FOR EACH ROW EXECUTE FUNCTION business_pharma_recall_event_immutable()')
        connection.exec_driver_sql('''
        CREATE OR REPLACE FUNCTION business_pharma_recall_source_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'Pharma recall source history cannot be deleted' USING ERRCODE='23514';
            END IF;
            IF ROW(NEW.id,NEW.organization_id,NEW.branch_id,NEW.pack_context_id,NEW.batch_id,NEW.product_id,
                NEW.warehouse_id,NEW.batch_number,NEW.expiry_date,NEW.reason,NEW.created_by,NEW.created_at)
                IS DISTINCT FROM ROW(OLD.id,OLD.organization_id,OLD.branch_id,OLD.pack_context_id,OLD.batch_id,OLD.product_id,
                OLD.warehouse_id,OLD.batch_number,OLD.expiry_date,OLD.reason,OLD.created_by,OLD.created_at)
                OR OLD.state<>'open' OR NEW.state NOT IN ('open','closed') OR NEW.revision<>OLD.revision+1 THEN
                RAISE EXCEPTION 'Pharma recall source or revision is immutable' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$''')
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS business_pharma_recall_source_immutable ON business_pharma_recalls')
        connection.exec_driver_sql('CREATE TRIGGER business_pharma_recall_source_immutable BEFORE UPDATE OR DELETE ON business_pharma_recalls FOR EACH ROW EXECUTE FUNCTION business_pharma_recall_source_immutable()')


def downgrade():
    # Permanent native inventory provenance must not be removed automatically.
    pass
