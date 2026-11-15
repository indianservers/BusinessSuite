"""Add immutable Retail sale-stock and original-sale return sources; no ledger duplication."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261115_108_retail_returns'
down_revision='pg_20261115_107_pack_owner'
branch_labels=depends_on=None

_DDL = {'postgresql': [('business_retail_sale_stock_sources',
                 '\n'
                 'CREATE TABLE business_retail_sale_stock_sources (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tsales_order_line_id INTEGER NOT NULL, \n'
                 '\tmovement_id INTEGER NOT NULL, \n'
                 '\tproduct_id INTEGER NOT NULL, \n'
                 '\twarehouse_id INTEGER NOT NULL, \n'
                 '\tquantity NUMERIC(24, 10) NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_retail_sale_stock_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT ck_retail_sale_stock_quantity CHECK (pack_context_id > 0 AND quantity > 0), \n'
                 '\tUNIQUE (sales_order_line_id), \n'
                 '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tUNIQUE (movement_id), \n'
                 '\tFOREIGN KEY(movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('business_retail_returns',
                 '\n'
                 'CREATE TABLE business_retail_returns (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcheckout_id INTEGER NOT NULL, \n'
                 '\trequest_key VARCHAR(36) NOT NULL, \n'
                 '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tsales_order_id INTEGER NOT NULL, \n'
                 '\tinvoice_id INTEGER NOT NULL, \n'
                 '\tcollection_session_id INTEGER NOT NULL, \n'
                 '\tnative_return_id INTEGER, \n'
                 '\tcredit_voucher_id INTEGER, \n'
                 '\trefund_voucher_id INTEGER, \n'
                 '\tcash_movement_id INTEGER, \n'
                 '\trefund_method VARCHAR(12) NOT NULL, \n'
                 '\tpayment_reference VARCHAR(200) NOT NULL, \n'
                 '\tcurrency VARCHAR(3) NOT NULL, \n'
                 '\treason TEXT NOT NULL, \n'
                 '\tnet_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\trefund_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\tstate VARCHAR(12) NOT NULL, \n'
                 '\trevision INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tcommitted_at TIMESTAMP WITH TIME ZONE, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_retail_return_checkout_scope FOREIGN KEY(checkout_id, organization_id, '
                 'branch_id, pack_context_id) REFERENCES srm_pos_service_checkouts (id, organization_id, '
                 'branch_id, scope_context_key) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_retail_return_request UNIQUE (organization_id, branch_id, pack_context_id, '
                 'request_key), \n'
                 '\tCONSTRAINT uq_retail_return_scope UNIQUE (id, checkout_id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT ck_retail_return_scope CHECK (pack_context_id > 0 AND revision > 0), \n'
                 "\tCONSTRAINT ck_retail_return_state CHECK (state IN ('draft','committed')), \n"
                 '\tCONSTRAINT ck_retail_return_request CHECK (length(request_key)=36 AND '
                 'length(request_sha256)=64), \n'
                 "\tCONSTRAINT ck_retail_return_payment CHECK (refund_method IN ('cash','card') AND "
                 'length(currency)=3), \n'
                 '\tCONSTRAINT ck_retail_return_money CHECK (net_amount >= 0 AND tax_amount >= 0 AND '
                 'refund_amount > 0 AND net_amount+tax_amount=refund_amount), \n'
                 "\tCONSTRAINT ck_retail_return_committed CHECK (state != 'committed' OR (native_return_id "
                 'IS NOT NULL AND credit_voucher_id IS NOT NULL AND refund_voucher_id IS NOT NULL AND '
                 'committed_at IS NOT NULL)), \n'
                 "\tCONSTRAINT ck_retail_return_cash CHECK (refund_method != 'cash' OR state != 'committed' "
                 'OR cash_movement_id IS NOT NULL), \n'
                 '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(pack_context_id) REFERENCES business_pack_contexts (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(collection_session_id) REFERENCES srm_pos_sessions (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tUNIQUE (native_return_id), \n'
                 '\tFOREIGN KEY(native_return_id) REFERENCES srm_pos_returns (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (credit_voucher_id), \n'
                 '\tFOREIGN KEY(credit_voucher_id) REFERENCES fam_vouchers (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (refund_voucher_id), \n'
                 '\tFOREIGN KEY(refund_voucher_id) REFERENCES fam_vouchers (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (cash_movement_id), \n'
                 '\tFOREIGN KEY(cash_movement_id) REFERENCES srm_pos_cash_movements (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [('ix_business_retail_returns_organization_id',
                   'CREATE INDEX ix_business_retail_returns_organization_id ON business_retail_returns '
                   '(organization_id)')]),
                ('business_retail_return_lines',
                 '\n'
                 'CREATE TABLE business_retail_return_lines (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\treturn_id INTEGER NOT NULL, \n'
                 '\tcheckout_id INTEGER NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcheckout_line_id INTEGER NOT NULL, \n'
                 '\tproduct_id INTEGER NOT NULL, \n'
                 '\tsales_order_line_id INTEGER NOT NULL, \n'
                 '\tinvoice_line_id INTEGER NOT NULL, \n'
                 '\tnative_return_line_id INTEGER NOT NULL, \n'
                 '\tstock_movement_id INTEGER, \n'
                 '\tquantity NUMERIC(24, 10) NOT NULL, \n'
                 '\tnet_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\tgross_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\trestock BOOLEAN NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_retail_return_line_root FOREIGN KEY(return_id, checkout_id, '
                 'organization_id, branch_id, pack_context_id) REFERENCES business_retail_returns (id, '
                 'checkout_id, organization_id, branch_id, pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT fk_retail_return_line_source FOREIGN KEY(checkout_line_id, checkout_id, '
                 'organization_id, branch_id, pack_context_id, product_id) REFERENCES srm_pos_checkout_lines '
                 '(id, checkout_id, organization_id, branch_id, scope_context_key, product_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_retail_return_source_line UNIQUE (return_id, checkout_line_id), \n'
                 '\tCONSTRAINT ck_retail_return_line_money CHECK (quantity > 0 AND net_amount >= 0 AND '
                 'tax_amount >= 0 AND gross_amount >= 0 AND net_amount+tax_amount=gross_amount), \n'
                 '\tCONSTRAINT ck_retail_return_line_stock CHECK (restock = false OR stock_movement_id IS '
                 'NOT NULL), \n'
                 '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tFOREIGN KEY(invoice_line_id) REFERENCES srm_invoice_lines (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (native_return_line_id), \n'
                 '\tFOREIGN KEY(native_return_line_id) REFERENCES srm_pos_return_lines (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tUNIQUE (stock_movement_id), \n'
                 '\tFOREIGN KEY(stock_movement_id) REFERENCES srm_inventory_movements (id) ON DELETE '
                 'RESTRICT\n'
                 ')\n'
                 '\n',
                 [])],
 'sqlite': [('business_retail_sale_stock_sources',
             '\n'
             'CREATE TABLE business_retail_sale_stock_sources (\n'
             '\tid INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tsales_order_line_id INTEGER NOT NULL, \n'
             '\tmovement_id INTEGER NOT NULL, \n'
             '\tproduct_id INTEGER NOT NULL, \n'
             '\twarehouse_id INTEGER NOT NULL, \n'
             '\tquantity NUMERIC(24, 10) NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_retail_sale_stock_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT ck_retail_sale_stock_quantity CHECK (pack_context_id > 0 AND quantity > 0), \n'
             '\tUNIQUE (sales_order_line_id), \n'
             '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (movement_id), \n'
             '\tFOREIGN KEY(movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('business_retail_returns',
             '\n'
             'CREATE TABLE business_retail_returns (\n'
             '\tid INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcheckout_id INTEGER NOT NULL, \n'
             '\trequest_key VARCHAR(36) NOT NULL, \n'
             '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tsales_order_id INTEGER NOT NULL, \n'
             '\tinvoice_id INTEGER NOT NULL, \n'
             '\tcollection_session_id INTEGER NOT NULL, \n'
             '\tnative_return_id INTEGER, \n'
             '\tcredit_voucher_id INTEGER, \n'
             '\trefund_voucher_id INTEGER, \n'
             '\tcash_movement_id INTEGER, \n'
             '\trefund_method VARCHAR(12) NOT NULL, \n'
             '\tpayment_reference VARCHAR(200) NOT NULL, \n'
             '\tcurrency VARCHAR(3) NOT NULL, \n'
             '\treason TEXT NOT NULL, \n'
             '\tnet_amount NUMERIC(14, 2) NOT NULL, \n'
             '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
             '\trefund_amount NUMERIC(14, 2) NOT NULL, \n'
             '\tstate VARCHAR(12) NOT NULL, \n'
             '\trevision INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tcommitted_at DATETIME, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_retail_return_checkout_scope FOREIGN KEY(checkout_id, organization_id, '
             'branch_id, pack_context_id) REFERENCES srm_pos_service_checkouts (id, organization_id, '
             'branch_id, scope_context_key) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_retail_return_request UNIQUE (organization_id, branch_id, pack_context_id, '
             'request_key), \n'
             '\tCONSTRAINT uq_retail_return_scope UNIQUE (id, checkout_id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT ck_retail_return_scope CHECK (pack_context_id > 0 AND revision > 0), \n'
             "\tCONSTRAINT ck_retail_return_state CHECK (state IN ('draft','committed')), \n"
             '\tCONSTRAINT ck_retail_return_request CHECK (length(request_key)=36 AND '
             'length(request_sha256)=64), \n'
             "\tCONSTRAINT ck_retail_return_payment CHECK (refund_method IN ('cash','card') AND "
             'length(currency)=3), \n'
             '\tCONSTRAINT ck_retail_return_money CHECK (net_amount >= 0 AND tax_amount >= 0 AND '
             'refund_amount > 0 AND net_amount+tax_amount=refund_amount), \n'
             "\tCONSTRAINT ck_retail_return_committed CHECK (state != 'committed' OR (native_return_id IS "
             'NOT NULL AND credit_voucher_id IS NOT NULL AND refund_voucher_id IS NOT NULL AND committed_at '
             'IS NOT NULL)), \n'
             "\tCONSTRAINT ck_retail_return_cash CHECK (refund_method != 'cash' OR state != 'committed' OR "
             'cash_movement_id IS NOT NULL), \n'
             '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(pack_context_id) REFERENCES business_pack_contexts (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(collection_session_id) REFERENCES srm_pos_sessions (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (native_return_id), \n'
             '\tFOREIGN KEY(native_return_id) REFERENCES srm_pos_returns (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (credit_voucher_id), \n'
             '\tFOREIGN KEY(credit_voucher_id) REFERENCES fam_vouchers (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (refund_voucher_id), \n'
             '\tFOREIGN KEY(refund_voucher_id) REFERENCES fam_vouchers (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (cash_movement_id), \n'
             '\tFOREIGN KEY(cash_movement_id) REFERENCES srm_pos_cash_movements (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [('ix_business_retail_returns_organization_id',
               'CREATE INDEX ix_business_retail_returns_organization_id ON business_retail_returns '
               '(organization_id)')]),
            ('business_retail_return_lines',
             '\n'
             'CREATE TABLE business_retail_return_lines (\n'
             '\tid INTEGER NOT NULL, \n'
             '\treturn_id INTEGER NOT NULL, \n'
             '\tcheckout_id INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcheckout_line_id INTEGER NOT NULL, \n'
             '\tproduct_id INTEGER NOT NULL, \n'
             '\tsales_order_line_id INTEGER NOT NULL, \n'
             '\tinvoice_line_id INTEGER NOT NULL, \n'
             '\tnative_return_line_id INTEGER NOT NULL, \n'
             '\tstock_movement_id INTEGER, \n'
             '\tquantity NUMERIC(24, 10) NOT NULL, \n'
             '\tnet_amount NUMERIC(14, 2) NOT NULL, \n'
             '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
             '\tgross_amount NUMERIC(14, 2) NOT NULL, \n'
             '\trestock BOOLEAN NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_retail_return_line_root FOREIGN KEY(return_id, checkout_id, organization_id, '
             'branch_id, pack_context_id) REFERENCES business_retail_returns (id, checkout_id, '
             'organization_id, branch_id, pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT fk_retail_return_line_source FOREIGN KEY(checkout_line_id, checkout_id, '
             'organization_id, branch_id, pack_context_id, product_id) REFERENCES srm_pos_checkout_lines '
             '(id, checkout_id, organization_id, branch_id, scope_context_key, product_id) ON DELETE '
             'RESTRICT, \n'
             '\tCONSTRAINT uq_retail_return_source_line UNIQUE (return_id, checkout_line_id), \n'
             '\tCONSTRAINT ck_retail_return_line_money CHECK (quantity > 0 AND net_amount >= 0 AND '
             'tax_amount >= 0 AND gross_amount >= 0 AND net_amount+tax_amount=gross_amount), \n'
             '\tCONSTRAINT ck_retail_return_line_stock CHECK (restock = false OR stock_movement_id IS NOT '
             'NULL), \n'
             '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(invoice_line_id) REFERENCES srm_invoice_lines (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (native_return_line_id), \n'
             '\tFOREIGN KEY(native_return_line_id) REFERENCES srm_pos_return_lines (id) ON DELETE '
             'RESTRICT, \n'
             '\tUNIQUE (stock_movement_id), \n'
             '\tFOREIGN KEY(stock_movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [])]}

_ROOT_IMMUTABLE=('id','organization_id','branch_id','pack_context_id','checkout_id','request_key',
    'request_sha256','created_by','sales_order_id','invoice_id','collection_session_id','refund_method',
    'payment_reference','currency','reason','net_amount','tax_amount','refund_amount','created_at')
_BOUND_ONCE=('native_return_id','credit_voucher_id','refund_voucher_id','cash_movement_id','committed_at')


def _history_guards(connection):
    children=('business_retail_sale_stock_sources','business_retail_return_lines')
    if connection.dialect.name=='sqlite':
        for table in children:
            for action in ('UPDATE','DELETE'):
                connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Issued Retail source history is immutable'); END")
        table='business_retail_returns'
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'Issued Retail return history is immutable'); END")
        changed=' OR '.join(f'NEW.{name} IS NOT OLD.{name}' for name in _ROOT_IMMUTABLE)
        rebound=' OR '.join(f'(OLD.{name} IS NOT NULL AND NEW.{name} IS NOT OLD.{name})' for name in _BOUND_ONCE)
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {table}_update BEFORE UPDATE ON {table} WHEN OLD.state='committed' OR ({changed}) OR ({rebound}) OR NEW.revision<>OLD.revision+1 OR (NEW.state IS NOT OLD.state AND NOT (OLD.state='draft' AND NEW.state='committed')) BEGIN SELECT RAISE(ABORT,'Issued Retail source and charge identity is immutable'); END")
        for action in ('UPDATE','DELETE'):
            connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS retail_refund_cash_{action.lower()} BEFORE {action} ON srm_pos_cash_movements WHEN EXISTS(SELECT 1 FROM business_retail_returns WHERE cash_movement_id=OLD.id) BEGIN SELECT RAISE(ABORT,'Issued Retail cash refund history is immutable'); END")
    else:
        connection.exec_driver_sql("""CREATE OR REPLACE FUNCTION retail_immutable_source_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Issued Retail source history is immutable'; END $$""")
        for table in children:
            connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS retail_immutable_source ON {table}')
            connection.exec_driver_sql(f'CREATE TRIGGER retail_immutable_source BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION retail_immutable_source_history()')
        changed=' OR '.join(f'NEW.{name} IS DISTINCT FROM OLD.{name}' for name in _ROOT_IMMUTABLE)
        rebound=' OR '.join(f'(OLD.{name} IS NOT NULL AND NEW.{name} IS DISTINCT FROM OLD.{name})' for name in _BOUND_ONCE)
        connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION retail_immutable_return_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Issued Retail return history is immutable'; END IF;
            IF OLD.state='committed' OR ({changed}) OR ({rebound}) OR NEW.revision<>OLD.revision+1 OR (NEW.state IS DISTINCT FROM OLD.state AND NOT (OLD.state='draft' AND NEW.state='committed')) THEN
                RAISE EXCEPTION 'Issued Retail source and charge identity is immutable';
            END IF; RETURN NEW; END $$""")
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS retail_immutable_return ON business_retail_returns')
        connection.exec_driver_sql('CREATE TRIGGER retail_immutable_return BEFORE UPDATE OR DELETE ON business_retail_returns FOR EACH ROW EXECUTE FUNCTION retail_immutable_return_history()')
        connection.exec_driver_sql("""CREATE OR REPLACE FUNCTION retail_immutable_cash_refund() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF EXISTS(SELECT 1 FROM business_retail_returns WHERE cash_movement_id=OLD.id) THEN RAISE EXCEPTION 'Issued Retail cash refund history is immutable'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS retail_immutable_cash_refund ON srm_pos_cash_movements')
        connection.exec_driver_sql('CREATE TRIGGER retail_immutable_cash_refund BEFORE UPDATE OR DELETE ON srm_pos_cash_movements FOR EACH ROW EXECUTE FUNCTION retail_immutable_cash_refund()')


def upgrade():
    connection=op.get_bind()
    dialect=connection.dialect.name
    if dialect not in _DDL:raise RuntimeError('Unsupported Retail source migration dialect')
    for name,ddl,indexes in _DDL[dialect]:
        if not sa.inspect(connection).has_table(name):connection.exec_driver_sql(ddl)
        installed={index['name'] for index in sa.inspect(connection).get_indexes(name)}
        for index,sql in indexes:
            if index not in installed:connection.exec_driver_sql(sql)
    _history_guards(connection)


def downgrade():
    # Issued stock, credit-note and refund provenance is permanent history.
    pass
