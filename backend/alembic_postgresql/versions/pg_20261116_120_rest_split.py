"""Immutable original-charge allocations for native Restaurant split invoices."""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261116_120_rest_split'
down_revision = 'pg_20261116_119_cash_intent'
branch_labels = depends_on = None


def _scope(alias):
    return f'{alias}.organization_id=NEW.organization_id AND {alias}.branch_id=NEW.branch_id AND {alias}.pack_context_id=NEW.pack_context_id'


def _proof(table, identity):
    return f"""EXISTS (SELECT 1 FROM suite_branch_ownership b JOIN business_pack_record_ownership p
        ON p.resource_table=b.resource_table AND p.resource_key=b.resource_key
        WHERE b.resource_table='{table}' AND b.resource_key=CAST({identity} AS VARCHAR)
        AND b.company_id=NEW.organization_id AND b.branch_id=NEW.branch_id
        AND p.company_id=NEW.organization_id AND p.branch_id=NEW.branch_id AND p.context_id=NEW.pack_context_id)"""


def _checks(dialect='postgresql'):
    qty = '(SELECT COALESCE(SUM(quantity),0) FROM business_restaurant_bill_lines WHERE snapshot_id=NEW.snapshot_id)'
    tax = '(SELECT COALESCE(SUM(tax_amount),0) FROM business_restaurant_bill_lines WHERE snapshot_id=NEW.snapshot_id)'
    gross = '(SELECT COALESCE(SUM(ROUND(quantity*unit_price,2)),0) FROM business_restaurant_bill_lines WHERE snapshot_id=NEW.snapshot_id)'
    group = f"""EXISTS (SELECT 1 FROM business_restaurant_service_orders o JOIN srm_sales_orders n ON n.id=o.sales_order_id
        JOIN crm_companies c ON c.id=n.customer_id WHERE o.id=NEW.service_order_id AND {_scope('o')}
        AND o.source_kind='unpaid_tab' AND o.checkout_id IS NULL AND o.state='open'
        AND n.organization_id=NEW.organization_id AND n.status='draft' AND n.deleted_at IS NULL
        AND c.organization_id=NEW.organization_id
        AND {_proof('business_restaurant_service_orders','o.id')} AND {_proof('srm_sales_orders','n.id')}
        AND NOT EXISTS (SELECT 1 FROM srm_pos_service_checkouts WHERE sales_order_id=n.id)
        AND NOT EXISTS (SELECT 1 FROM srm_invoices i WHERE i.sales_order_id=n.id AND NOT EXISTS
            (SELECT 1 FROM business_restaurant_bill_issues bi JOIN business_restaurant_bill_groups bg ON bg.id=bi.group_id
             WHERE bi.invoice_id=i.id AND bg.service_order_id=o.id)))"""
    line = f"""EXISTS (SELECT 1 FROM business_restaurant_tab_lines s JOIN business_restaurant_bill_groups g ON g.id=NEW.group_id
        JOIN srm_sales_order_lines n ON n.id=s.sales_order_line_id
        WHERE s.id=NEW.snapshot_id AND s.service_order_id=g.service_order_id AND {_scope('s')} AND {_scope('g')}
        AND NEW.created_by=g.created_by AND n.quantity=s.quantity AND n.unit_price=s.unit_price AND n.tax_amount=s.tax_amount AND n.line_total=s.line_total
        AND NEW.quantity>0 AND NEW.unit_price=s.unit_price AND NEW.tax_amount>=0
        AND NEW.quantity+{qty}<=s.quantity AND NEW.tax_amount+{tax}<=s.tax_amount
        AND NEW.tax_amount=ROUND(1.0*s.tax_amount*({qty}+NEW.quantity)/s.quantity,2)-{tax}
        AND NEW.line_total=ROUND(NEW.quantity*NEW.unit_price,2)+NEW.tax_amount
        AND {gross}+ROUND(NEW.quantity*NEW.unit_price,2)+ROUND((s.quantity-{qty}-NEW.quantity)*s.unit_price,2)=ROUND(s.quantity*s.unit_price,2)
        AND NOT EXISTS (SELECT 1 FROM business_restaurant_bill_issues WHERE group_id=g.id))"""
    issue = f"""EXISTS (SELECT 1 FROM business_restaurant_bill_groups g JOIN business_restaurant_service_orders o ON o.id=g.service_order_id
        JOIN srm_sales_orders n ON n.id=o.sales_order_id JOIN srm_invoices i ON i.id=NEW.invoice_id
        WHERE g.id=NEW.group_id AND {_scope('g')} AND {_scope('o')} AND NEW.created_by=g.created_by
        AND i.organization_id=NEW.organization_id AND i.sales_order_id=n.id AND i.engagement_id IS NULL
        AND i.customer_id=n.customer_id AND i.currency=n.currency AND i.created_by=g.created_by
        AND i.deleted_at IS NULL AND i.approved_at IS NOT NULL AND i.status IN ('approved','sent','partially_paid','paid')
        AND i.discount_amount=0 AND i.total_amount>0
        AND i.total_amount=(SELECT SUM(line_total) FROM business_restaurant_bill_lines WHERE group_id=g.id)
        AND i.tax_amount=(SELECT SUM(tax_amount) FROM business_restaurant_bill_lines WHERE group_id=g.id)
        AND i.subtotal=i.total_amount-i.tax_amount
        AND {_proof('srm_invoices','i.id')}
        AND (SELECT COUNT(*) FROM srm_invoice_lines WHERE invoice_id=i.id)=(SELECT COUNT(*) FROM business_restaurant_bill_lines WHERE group_id=g.id)
        AND NOT EXISTS (SELECT 1 FROM srm_invoice_lines il WHERE il.invoice_id=i.id AND NOT EXISTS
            (SELECT 1 FROM business_restaurant_bill_lines bl JOIN business_restaurant_tab_lines s ON s.id=bl.snapshot_id
             WHERE bl.group_id=g.id AND il.source_type='restaurant_bill_line' AND il.source_id=bl.id
             AND il.quantity=bl.quantity AND il.unit_price=bl.unit_price AND il.discount_amount=0
             AND il.tax_amount=bl.tax_amount AND il.line_total=bl.line_total AND il.description=s.item)))"""
    if dialect == 'sqlite':
        currency = """(s.metadata_json IS NULL OR json_type(s.metadata_json) IN ('object','null')) AND
            ((NEW.collection_currency IS NULL AND json_type(s.metadata_json,'$.cash_currency') IS NULL) OR
             (NEW.collection_currency IS NOT NULL AND json_type(s.metadata_json,'$.cash_currency')='text'
              AND json_extract(s.metadata_json,'$.cash_currency')=NEW.collection_currency
              AND NEW.collection_currency GLOB '[A-Z][A-Z][A-Z]'))"""
        cashier = '(s.cashier_user_id=NEW.collection_cashier_id OR (s.cashier_user_id IS NULL AND NEW.collection_cashier_id IS NULL))'
    else:
        currency = """(s.metadata_json IS NULL OR jsonb_typeof(s.metadata_json::jsonb) IN ('object','null')) AND
            ((NEW.collection_currency IS NULL AND (s.metadata_json IS NULL OR jsonb_typeof(s.metadata_json::jsonb)='null'
                OR NOT (s.metadata_json::jsonb ? 'cash_currency'))) OR
             (NEW.collection_currency IS NOT NULL AND jsonb_typeof(s.metadata_json::jsonb->'cash_currency')='string'
              AND s.metadata_json::jsonb->>'cash_currency'=NEW.collection_currency AND NEW.collection_currency ~ '^[A-Z]{3}$'))"""
        cashier = 's.cashier_user_id IS NOT DISTINCT FROM NEW.collection_cashier_id'
    receipt = f"""EXISTS (SELECT 1 FROM business_restaurant_bill_issues bi JOIN srm_invoices i ON i.id=bi.invoice_id
        JOIN srm_receipts r ON r.id=NEW.receipt_id JOIN srm_receipt_allocations a ON a.id=NEW.allocation_id
        JOIN srm_pos_sessions s ON s.id=NEW.collection_session_id
        WHERE bi.id=NEW.issue_id AND {_scope('bi')}
        AND r.organization_id=NEW.organization_id AND r.customer_id=i.customer_id AND r.currency=i.currency
        AND r.status='allocated' AND r.amount>0 AND r.unallocated_amount=0 AND r.created_by=NEW.created_by
        AND a.receipt_id=r.id AND a.invoice_id=i.id AND a.amount=r.amount AND a.request_id=NEW.payment_key
        AND a.allocated_by=NEW.created_by AND s.organization_id=NEW.organization_id AND s.status='open' AND s.deleted_at IS NULL
        AND i.status IN ('approved','sent','partially_paid','paid') AND i.deleted_at IS NULL
        AND ({cashier}) AND ({currency}) AND (r.payment_method<>'cash' OR r.currency=NEW.collection_currency)
        AND (s.cashier_user_id IS NULL OR s.cashier_user_id=NEW.created_by)
        AND {_proof('srm_receipts','r.id')} AND {_proof('srm_receipt_allocations','a.id')} AND {_proof('srm_pos_sessions','s.id')}
        AND (SELECT COUNT(*) FROM srm_receipt_allocations WHERE receipt_id=r.id)=1)"""
    context = "EXISTS (SELECT 1 FROM business_pack_contexts c WHERE c.id=NEW.pack_context_id AND c.company_id=NEW.organization_id AND c.branch_id=NEW.branch_id AND c.pack_key='restaurant')"
    return {name: f'({context}) AND ({check})' for name, check in (
        ('business_restaurant_bill_groups', group), ('business_restaurant_bill_lines', line),
        ('business_restaurant_bill_issues', issue), ('business_restaurant_bill_receipts', receipt))}


def install_guards(connection):
    dialect = connection.dialect.name
    for index, (name, check) in enumerate(_checks(dialect).items()):
        if dialect == 'sqlite':
            for action in ('UPDATE', 'DELETE'):
                connection.exec_driver_sql(f"CREATE TRIGGER rest_split_{index}_{action.lower()} BEFORE {action} ON {name} BEGIN SELECT RAISE(ABORT,'Restaurant split provenance is immutable'); END")
            connection.exec_driver_sql(f"CREATE TRIGGER rest_split_{index}_insert BEFORE INSERT ON {name} WHEN NOT ({check}) BEGIN SELECT RAISE(ABORT,'Restaurant split native source differs'); END")
        elif dialect == 'postgresql':
            lock = 'PERFORM pg_advisory_xact_lock(720120, NEW.snapshot_id);' if name.endswith('_lines') else ''
            connection.exec_driver_sql(f"""CREATE FUNCTION rest_split_{index}_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Restaurant split provenance is immutable' USING ERRCODE='23514'; END IF;
                {lock}
                IF NOT ({check}) THEN RAISE EXCEPTION 'Restaurant split native source differs' USING ERRCODE='23514'; END IF;
                RETURN NEW; END $$""")
            connection.exec_driver_sql(f'CREATE TRIGGER rest_split_{index}_source BEFORE INSERT OR UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION rest_split_{index}_guard()')
        else:
            raise RuntimeError('Unsupported Restaurant split migration dialect')
    if dialect == 'postgresql':
        # Deferred only until the outer transaction: pending provenance cannot
        # survive a commit without the exact immutable native issue command.
        receipt_check = _checks('postgresql')['business_restaurant_bill_receipts']
        connection.exec_driver_sql(f"""CREATE FUNCTION rest_split_commit_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE bill_id integer; source record; BEGIN
            IF TG_TABLE_NAME='business_restaurant_bill_groups' THEN bill_id:=NEW.id;
            ELSE SELECT group_id INTO bill_id FROM business_restaurant_bill_issues WHERE id=NEW.issue_id; END IF;
            SELECT g.*, bi.id AS issue_id, bi.invoice_id INTO source FROM business_restaurant_bill_groups g
              JOIN business_restaurant_bill_issues bi ON bi.group_id=g.id WHERE g.id=bill_id;
            IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM business_restaurant_commands c WHERE c.service_order_id=source.service_order_id
                AND c.action='tab.split_bill' AND c.request_key=source.request_key AND c.request_sha256=source.request_sha256
                AND c.organization_id=source.organization_id AND c.branch_id=source.branch_id AND c.pack_context_id=source.pack_context_id
                AND c.result->>'bill_id'=CAST(source.issue_id AS text) AND c.result->>'invoice_id'=CAST(source.invoice_id AS text)) THEN
                RAISE EXCEPTION 'Restaurant split requires its committed native command' USING ERRCODE='23514'; END IF;
            IF TG_TABLE_NAME='business_restaurant_bill_receipts' THEN
              IF NOT ({receipt_check}) THEN
                RAISE EXCEPTION 'Restaurant collection register/source changed before commit' USING ERRCODE='23514'; END IF;
              IF NOT EXISTS (SELECT 1 FROM business_restaurant_commands c
                WHERE c.service_order_id=source.service_order_id AND c.action='tab.split_payment'
                AND c.request_key=NEW.request_key AND c.request_sha256=NEW.request_sha256
                AND c.organization_id=NEW.organization_id AND c.branch_id=NEW.branch_id AND c.pack_context_id=NEW.pack_context_id
                AND c.result->>'bill_id'=CAST(NEW.issue_id AS text) AND c.result->>'receipt_id'=CAST(NEW.receipt_id AS text)
                AND c.result->>'allocation_id'=CAST(NEW.allocation_id AS text)) THEN
                RAISE EXCEPTION 'Restaurant collection requires its committed native command' USING ERRCODE='23514'; END IF;
            END IF;
            RETURN NULL; END $$""")
        for index, name in ((0, 'business_restaurant_bill_groups'), (3, 'business_restaurant_bill_receipts')):
            connection.exec_driver_sql(f'CREATE CONSTRAINT TRIGGER rest_split_{index}_commit AFTER INSERT ON {name} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION rest_split_commit_guard()')


def upgrade():
    connection = op.get_bind()
    for name, ddl, indexes in _DDL[connection.dialect.name]:
        connection.exec_driver_sql(ddl)
        for sql in indexes:
            connection.exec_driver_sql(sql)
    install_guards(connection)


def downgrade():
    connection = op.get_bind()
    names = [name for name, _, _ in _DDL[connection.dialect.name]]
    if any(connection.exec_driver_sql('SELECT 1 FROM ' + name + ' LIMIT 1').first() for name in names):
        raise RuntimeError('Restaurant split billing history cannot be erased by downgrade')
    for name in reversed(names):
        op.drop_table(name)
    if connection.dialect.name == 'postgresql':
        connection.exec_driver_sql('DROP FUNCTION rest_split_commit_guard()')
        for index in range(4):
            connection.exec_driver_sql(f'DROP FUNCTION rest_split_{index}_guard()')

_DDL = {'postgresql': [('business_restaurant_bill_groups',
                 '\n'
                 'CREATE TABLE business_restaurant_bill_groups (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tservice_order_id INTEGER NOT NULL, \n'
                 '\trequest_key VARCHAR(36) NOT NULL, \n'
                 '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_restaurant_bill_group_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_restaurant_bill_group_source UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT fk_restaurant_bill_group_order FOREIGN KEY(service_order_id, organization_id, '
                 'branch_id, pack_context_id) REFERENCES business_restaurant_service_orders (id, organization_id, '
                 'branch_id, pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_rest_bill_request UNIQUE (organization_id, branch_id, pack_context_id, '
                 'request_key), \n'
                 '\tCONSTRAINT ck_rest_bill_request CHECK (length(request_key)=36 AND '
                 'length(request_sha256)=64), \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 ['CREATE INDEX ix_rest_bill_order ON business_restaurant_bill_groups (service_order_id)']),
                ('business_restaurant_bill_lines',
                 '\n'
                 'CREATE TABLE business_restaurant_bill_lines (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tgroup_id INTEGER NOT NULL, \n'
                 '\tsnapshot_id INTEGER NOT NULL, \n'
                 '\tquantity NUMERIC(12, 2) NOT NULL, \n'
                 '\tunit_price NUMERIC(14, 2) NOT NULL, \n'
                 '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\tline_total NUMERIC(14, 2) NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_restaurant_bill_line_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_restaurant_bill_line_source UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT fk_restaurant_bill_line_group FOREIGN KEY(group_id, organization_id, branch_id, '
                 'pack_context_id) REFERENCES business_restaurant_bill_groups (id, organization_id, branch_id, '
                 'pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT fk_restaurant_bill_line_snapshot FOREIGN KEY(snapshot_id, organization_id, '
                 'branch_id, pack_context_id) REFERENCES business_restaurant_tab_lines (id, organization_id, '
                 'branch_id, pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_rest_bill_snapshot UNIQUE (group_id, snapshot_id), \n'
                 '\tCONSTRAINT ck_rest_bill_charge CHECK (quantity > 0 AND unit_price >= 0 AND tax_amount >= 0 '
                 'AND line_total >= 0), \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 ['CREATE INDEX ix_rest_bill_snapshot ON business_restaurant_bill_lines (snapshot_id)']),
                ('business_restaurant_bill_issues',
                 '\n'
                 'CREATE TABLE business_restaurant_bill_issues (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tgroup_id INTEGER NOT NULL, \n'
                 '\tinvoice_id INTEGER NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_restaurant_bill_issue_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_restaurant_bill_issue_source UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT fk_restaurant_bill_issue_group FOREIGN KEY(group_id, organization_id, branch_id, '
                 'pack_context_id) REFERENCES business_restaurant_bill_groups (id, organization_id, branch_id, '
                 'pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_rest_bill_issued_once UNIQUE (group_id), \n'
                 '\tUNIQUE (invoice_id), \n'
                 '\tFOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('business_restaurant_bill_receipts',
                 '\n'
                 'CREATE TABLE business_restaurant_bill_receipts (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tissue_id INTEGER NOT NULL, \n'
                 '\treceipt_id INTEGER NOT NULL, \n'
                 '\tallocation_id INTEGER NOT NULL, \n'
                 '\tcollection_session_id INTEGER NOT NULL, \n'
                 '\tcollection_cashier_id INTEGER, \n'
                 '\tcollection_currency VARCHAR(3), \n'
                 '\tpayment_key VARCHAR(36) NOT NULL, \n'
                 '\trequest_key VARCHAR(36) NOT NULL, \n'
                 '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_restaurant_bill_receipt_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_restaurant_bill_receipt_source UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT fk_restaurant_bill_receipt_issue FOREIGN KEY(issue_id, organization_id, branch_id, '
                 'pack_context_id) REFERENCES business_restaurant_bill_issues (id, organization_id, branch_id, '
                 'pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_rest_bill_payment UNIQUE (organization_id, branch_id, pack_context_id, '
                 'payment_key), \n'
                 '\tCONSTRAINT uq_rest_bill_receipt_request UNIQUE (organization_id, branch_id, pack_context_id, '
                 'request_key), \n'
                 '\tCONSTRAINT ck_rest_bill_payment CHECK (length(payment_key)=36 AND length(request_key)=36 AND '
                 'length(request_sha256)=64), \n'
                 '\tCONSTRAINT ck_rest_bill_collection_currency CHECK (collection_currency IS NULL OR '
                 '(length(collection_currency)=3 AND collection_currency=upper(collection_currency))), \n'
                 '\tUNIQUE (receipt_id), \n'
                 '\tFOREIGN KEY(receipt_id) REFERENCES srm_receipts (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (allocation_id), \n'
                 '\tFOREIGN KEY(allocation_id) REFERENCES srm_receipt_allocations (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(collection_session_id) REFERENCES srm_pos_sessions (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(collection_cashier_id) REFERENCES users (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 ['CREATE INDEX ix_rest_bill_register ON business_restaurant_bill_receipts '
                  '(collection_session_id)'])],
 'sqlite': [('business_restaurant_bill_groups',
             '\n'
             'CREATE TABLE business_restaurant_bill_groups (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tservice_order_id INTEGER NOT NULL, \n'
             '\trequest_key VARCHAR(36) NOT NULL, \n'
             '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_restaurant_bill_group_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_restaurant_bill_group_source UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT fk_restaurant_bill_group_order FOREIGN KEY(service_order_id, organization_id, '
             'branch_id, pack_context_id) REFERENCES business_restaurant_service_orders (id, organization_id, '
             'branch_id, pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_rest_bill_request UNIQUE (organization_id, branch_id, pack_context_id, '
             'request_key), \n'
             '\tCONSTRAINT ck_rest_bill_request CHECK (length(request_key)=36 AND length(request_sha256)=64), \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             ['CREATE INDEX ix_rest_bill_order ON business_restaurant_bill_groups (service_order_id)']),
            ('business_restaurant_bill_lines',
             '\n'
             'CREATE TABLE business_restaurant_bill_lines (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tgroup_id INTEGER NOT NULL, \n'
             '\tsnapshot_id INTEGER NOT NULL, \n'
             '\tquantity NUMERIC(12, 2) NOT NULL, \n'
             '\tunit_price NUMERIC(14, 2) NOT NULL, \n'
             '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
             '\tline_total NUMERIC(14, 2) NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_restaurant_bill_line_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_restaurant_bill_line_source UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT fk_restaurant_bill_line_group FOREIGN KEY(group_id, organization_id, branch_id, '
             'pack_context_id) REFERENCES business_restaurant_bill_groups (id, organization_id, branch_id, '
             'pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT fk_restaurant_bill_line_snapshot FOREIGN KEY(snapshot_id, organization_id, branch_id, '
             'pack_context_id) REFERENCES business_restaurant_tab_lines (id, organization_id, branch_id, '
             'pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_rest_bill_snapshot UNIQUE (group_id, snapshot_id), \n'
             '\tCONSTRAINT ck_rest_bill_charge CHECK (quantity > 0 AND unit_price >= 0 AND tax_amount >= 0 AND '
             'line_total >= 0), \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             ['CREATE INDEX ix_rest_bill_snapshot ON business_restaurant_bill_lines (snapshot_id)']),
            ('business_restaurant_bill_issues',
             '\n'
             'CREATE TABLE business_restaurant_bill_issues (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tgroup_id INTEGER NOT NULL, \n'
             '\tinvoice_id INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_restaurant_bill_issue_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_restaurant_bill_issue_source UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT fk_restaurant_bill_issue_group FOREIGN KEY(group_id, organization_id, branch_id, '
             'pack_context_id) REFERENCES business_restaurant_bill_groups (id, organization_id, branch_id, '
             'pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_rest_bill_issued_once UNIQUE (group_id), \n'
             '\tUNIQUE (invoice_id), \n'
             '\tFOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('business_restaurant_bill_receipts',
             '\n'
             'CREATE TABLE business_restaurant_bill_receipts (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tissue_id INTEGER NOT NULL, \n'
             '\treceipt_id INTEGER NOT NULL, \n'
             '\tallocation_id INTEGER NOT NULL, \n'
             '\tcollection_session_id INTEGER NOT NULL, \n'
             '\tcollection_cashier_id INTEGER, \n'
             '\tcollection_currency VARCHAR(3), \n'
             '\tpayment_key VARCHAR(36) NOT NULL, \n'
             '\trequest_key VARCHAR(36) NOT NULL, \n'
             '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_restaurant_bill_receipt_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_restaurant_bill_receipt_source UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT fk_restaurant_bill_receipt_issue FOREIGN KEY(issue_id, organization_id, branch_id, '
             'pack_context_id) REFERENCES business_restaurant_bill_issues (id, organization_id, branch_id, '
             'pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_rest_bill_payment UNIQUE (organization_id, branch_id, pack_context_id, '
             'payment_key), \n'
             '\tCONSTRAINT uq_rest_bill_receipt_request UNIQUE (organization_id, branch_id, pack_context_id, '
             'request_key), \n'
             '\tCONSTRAINT ck_rest_bill_payment CHECK (length(payment_key)=36 AND length(request_key)=36 AND '
             'length(request_sha256)=64), \n'
             '\tCONSTRAINT ck_rest_bill_collection_currency CHECK (collection_currency IS NULL OR '
             '(length(collection_currency)=3 AND collection_currency=upper(collection_currency))), \n'
             '\tUNIQUE (receipt_id), \n'
             '\tFOREIGN KEY(receipt_id) REFERENCES srm_receipts (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (allocation_id), \n'
             '\tFOREIGN KEY(allocation_id) REFERENCES srm_receipt_allocations (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(collection_session_id) REFERENCES srm_pos_sessions (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(collection_cashier_id) REFERENCES users (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             ['CREATE INDEX ix_rest_bill_register ON business_restaurant_bill_receipts (collection_session_id)'])]}
