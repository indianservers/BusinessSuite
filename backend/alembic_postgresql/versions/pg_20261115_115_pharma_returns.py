"""Immutable original-lot returns and quarantined native stock; activates nothing."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261115_115_pharma_returns'
down_revision='pg_20261115_114_return_precision'
branch_labels=depends_on=None

_DDL = {'postgresql': [('business_pharma_returns',
                 '\n'
                 'CREATE TABLE business_pharma_returns (\n'
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
                 '\tCONSTRAINT fk_pharma_return_checkout_scope FOREIGN KEY(checkout_id, organization_id, '
                 'branch_id, pack_context_id) REFERENCES srm_pos_service_checkouts (id, organization_id, '
                 'branch_id, scope_context_key) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_pharma_return_request UNIQUE (organization_id, branch_id, pack_context_id, '
                 'request_key), \n'
                 '\tCONSTRAINT uq_pharma_return_scope UNIQUE (id, checkout_id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT ck_pharma_return_scope CHECK (pack_context_id > 0 AND revision > 0), \n'
                 "\tCONSTRAINT ck_pharma_return_state CHECK (state IN ('draft','committed')), \n"
                 '\tCONSTRAINT ck_pharma_return_request CHECK (length(request_key)=36 AND '
                 'length(request_sha256)=64), \n'
                 "\tCONSTRAINT ck_pharma_return_payment CHECK (refund_method IN ('cash','card') AND "
                 'length(currency)=3), \n'
                 '\tCONSTRAINT ck_pharma_return_money CHECK (net_amount >= 0 AND tax_amount >= 0 AND '
                 'refund_amount > 0 AND round(net_amount+tax_amount,2)=refund_amount), \n'
                 "\tCONSTRAINT ck_pharma_return_committed CHECK (state != 'committed' OR (native_return_id IS NOT "
                 'NULL AND credit_voucher_id IS NOT NULL AND refund_voucher_id IS NOT NULL AND committed_at IS '
                 'NOT NULL)), \n'
                 "\tCONSTRAINT ck_pharma_return_cash CHECK (refund_method != 'cash' OR state != 'committed' OR "
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
                 [('ix_business_pharma_returns_organization_id',
                   'CREATE INDEX ix_business_pharma_returns_organization_id ON business_pharma_returns '
                   '(organization_id)')]),
                ('business_pharma_return_lines',
                 '\n'
                 'CREATE TABLE business_pharma_return_lines (\n'
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
                 '\tquantity NUMERIC(14, 3) NOT NULL, \n'
                 '\tnet_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\tgross_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_pharma_return_line_root FOREIGN KEY(return_id, checkout_id, organization_id, '
                 'branch_id, pack_context_id) REFERENCES business_pharma_returns (id, checkout_id, '
                 'organization_id, branch_id, pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT fk_pharma_return_line_source FOREIGN KEY(checkout_line_id, checkout_id, '
                 'organization_id, branch_id, pack_context_id, product_id) REFERENCES srm_pos_checkout_lines (id, '
                 'checkout_id, organization_id, branch_id, scope_context_key, product_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_pharma_return_source_line UNIQUE (return_id, checkout_line_id), \n'
                 '\tCONSTRAINT uq_pharma_return_line_scope UNIQUE (id, return_id, checkout_id, checkout_line_id, '
                 'organization_id, branch_id, pack_context_id, product_id, sales_order_line_id), \n'
                 '\tCONSTRAINT ck_pharma_return_line_money CHECK (quantity > 0 AND net_amount >= 0 AND tax_amount '
                 '>= 0 AND gross_amount >= 0 AND round(net_amount+tax_amount,2)=gross_amount), \n'
                 '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(invoice_line_id) REFERENCES srm_invoice_lines (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (native_return_line_id), \n'
                 '\tFOREIGN KEY(native_return_line_id) REFERENCES srm_pos_return_lines (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('business_pharma_return_lots',
                 '\n'
                 'CREATE TABLE business_pharma_return_lots (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\treturn_line_id INTEGER NOT NULL, \n'
                 '\treturn_id INTEGER NOT NULL, \n'
                 '\tcheckout_id INTEGER NOT NULL, \n'
                 '\tcheckout_line_id INTEGER NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tproduct_id INTEGER NOT NULL, \n'
                 '\tsales_order_line_id INTEGER NOT NULL, \n'
                 '\twarehouse_id INTEGER NOT NULL, \n'
                 '\tallocation_id INTEGER NOT NULL, \n'
                 '\toriginal_batch_id INTEGER NOT NULL, \n'
                 '\tquarantine_batch_id INTEGER NOT NULL, \n'
                 '\tstock_movement_id INTEGER, \n'
                 '\toriginal_batch_number VARCHAR(120) NOT NULL, \n'
                 '\toriginal_expiry_date DATE NOT NULL, \n'
                 '\tquantity NUMERIC(14, 3) NOT NULL, \n'
                 '\tdisposition VARCHAR(20) NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_pharma_return_lot_line FOREIGN KEY(return_line_id, return_id, checkout_id, '
                 'checkout_line_id, organization_id, branch_id, pack_context_id, product_id, sales_order_line_id) '
                 'REFERENCES business_pharma_return_lines (id, return_id, checkout_id, checkout_line_id, '
                 'organization_id, branch_id, pack_context_id, product_id, sales_order_line_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT fk_pharma_return_lot_allocation FOREIGN KEY(allocation_id, organization_id, '
                 'branch_id, pack_context_id, sales_order_line_id, product_id, warehouse_id, original_batch_id) '
                 'REFERENCES business_pharma_batch_allocations (id, organization_id, branch_id, pack_context_id, '
                 'sales_order_line_id, product_id, warehouse_id, batch_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_pharma_return_original_allocation UNIQUE (return_id, allocation_id), \n'
                 "\tCONSTRAINT ck_pharma_return_lot_quarantine CHECK (quantity > 0 AND disposition='quarantine' "
                 'AND original_batch_id != quarantine_batch_id), \n'
                 '\tUNIQUE (quarantine_batch_id), \n'
                 '\tFOREIGN KEY(quarantine_batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (stock_movement_id), \n'
                 '\tFOREIGN KEY(stock_movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [])],
 'sqlite': [('business_pharma_returns',
             '\n'
             'CREATE TABLE business_pharma_returns (\n'
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
             '\tCONSTRAINT fk_pharma_return_checkout_scope FOREIGN KEY(checkout_id, organization_id, branch_id, '
             'pack_context_id) REFERENCES srm_pos_service_checkouts (id, organization_id, branch_id, '
             'scope_context_key) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_pharma_return_request UNIQUE (organization_id, branch_id, pack_context_id, '
             'request_key), \n'
             '\tCONSTRAINT uq_pharma_return_scope UNIQUE (id, checkout_id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT ck_pharma_return_scope CHECK (pack_context_id > 0 AND revision > 0), \n'
             "\tCONSTRAINT ck_pharma_return_state CHECK (state IN ('draft','committed')), \n"
             '\tCONSTRAINT ck_pharma_return_request CHECK (length(request_key)=36 AND '
             'length(request_sha256)=64), \n'
             "\tCONSTRAINT ck_pharma_return_payment CHECK (refund_method IN ('cash','card') AND "
             'length(currency)=3), \n'
             '\tCONSTRAINT ck_pharma_return_money CHECK (net_amount >= 0 AND tax_amount >= 0 AND refund_amount > '
             '0 AND round(net_amount+tax_amount,2)=refund_amount), \n'
             "\tCONSTRAINT ck_pharma_return_committed CHECK (state != 'committed' OR (native_return_id IS NOT "
             'NULL AND credit_voucher_id IS NOT NULL AND refund_voucher_id IS NOT NULL AND committed_at IS NOT '
             'NULL)), \n'
             "\tCONSTRAINT ck_pharma_return_cash CHECK (refund_method != 'cash' OR state != 'committed' OR "
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
             [('ix_business_pharma_returns_organization_id',
               'CREATE INDEX ix_business_pharma_returns_organization_id ON business_pharma_returns '
               '(organization_id)')]),
            ('business_pharma_return_lines',
             '\n'
             'CREATE TABLE business_pharma_return_lines (\n'
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
             '\tquantity NUMERIC(14, 3) NOT NULL, \n'
             '\tnet_amount NUMERIC(14, 2) NOT NULL, \n'
             '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
             '\tgross_amount NUMERIC(14, 2) NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_pharma_return_line_root FOREIGN KEY(return_id, checkout_id, organization_id, '
             'branch_id, pack_context_id) REFERENCES business_pharma_returns (id, checkout_id, organization_id, '
             'branch_id, pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT fk_pharma_return_line_source FOREIGN KEY(checkout_line_id, checkout_id, '
             'organization_id, branch_id, pack_context_id, product_id) REFERENCES srm_pos_checkout_lines (id, '
             'checkout_id, organization_id, branch_id, scope_context_key, product_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_pharma_return_source_line UNIQUE (return_id, checkout_line_id), \n'
             '\tCONSTRAINT uq_pharma_return_line_scope UNIQUE (id, return_id, checkout_id, checkout_line_id, '
             'organization_id, branch_id, pack_context_id, product_id, sales_order_line_id), \n'
             '\tCONSTRAINT ck_pharma_return_line_money CHECK (quantity > 0 AND net_amount >= 0 AND tax_amount >= '
             '0 AND gross_amount >= 0 AND round(net_amount+tax_amount,2)=gross_amount), \n'
             '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(invoice_line_id) REFERENCES srm_invoice_lines (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (native_return_line_id), \n'
             '\tFOREIGN KEY(native_return_line_id) REFERENCES srm_pos_return_lines (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('business_pharma_return_lots',
             '\n'
             'CREATE TABLE business_pharma_return_lots (\n'
             '\tid INTEGER NOT NULL, \n'
             '\treturn_line_id INTEGER NOT NULL, \n'
             '\treturn_id INTEGER NOT NULL, \n'
             '\tcheckout_id INTEGER NOT NULL, \n'
             '\tcheckout_line_id INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tproduct_id INTEGER NOT NULL, \n'
             '\tsales_order_line_id INTEGER NOT NULL, \n'
             '\twarehouse_id INTEGER NOT NULL, \n'
             '\tallocation_id INTEGER NOT NULL, \n'
             '\toriginal_batch_id INTEGER NOT NULL, \n'
             '\tquarantine_batch_id INTEGER NOT NULL, \n'
             '\tstock_movement_id INTEGER, \n'
             '\toriginal_batch_number VARCHAR(120) NOT NULL, \n'
             '\toriginal_expiry_date DATE NOT NULL, \n'
             '\tquantity NUMERIC(14, 3) NOT NULL, \n'
             '\tdisposition VARCHAR(20) NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_pharma_return_lot_line FOREIGN KEY(return_line_id, return_id, checkout_id, '
             'checkout_line_id, organization_id, branch_id, pack_context_id, product_id, sales_order_line_id) '
             'REFERENCES business_pharma_return_lines (id, return_id, checkout_id, checkout_line_id, '
             'organization_id, branch_id, pack_context_id, product_id, sales_order_line_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT fk_pharma_return_lot_allocation FOREIGN KEY(allocation_id, organization_id, branch_id, '
             'pack_context_id, sales_order_line_id, product_id, warehouse_id, original_batch_id) REFERENCES '
             'business_pharma_batch_allocations (id, organization_id, branch_id, pack_context_id, '
             'sales_order_line_id, product_id, warehouse_id, batch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_pharma_return_original_allocation UNIQUE (return_id, allocation_id), \n'
             "\tCONSTRAINT ck_pharma_return_lot_quarantine CHECK (quantity > 0 AND disposition='quarantine' AND "
             'original_batch_id != quarantine_batch_id), \n'
             '\tUNIQUE (quarantine_batch_id), \n'
             '\tFOREIGN KEY(quarantine_batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (stock_movement_id), \n'
             '\tFOREIGN KEY(stock_movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [])]}

_SOURCE_INDEX = {'postgresql': 'CREATE UNIQUE INDEX uq_pharma_allocation_return_source ON business_pharma_batch_allocations (id, organization_id, branch_id, pack_context_id, sales_order_line_id, product_id, warehouse_id, batch_id)', 'sqlite': 'CREATE UNIQUE INDEX uq_pharma_allocation_return_source ON business_pharma_batch_allocations (id, organization_id, branch_id, pack_context_id, sales_order_line_id, product_id, warehouse_id, batch_id)'}


_ROOT_IMMUTABLE=('id','organization_id','branch_id','pack_context_id','checkout_id','request_key',
    'request_sha256','created_by','sales_order_id','invoice_id','collection_session_id','refund_method',
    'payment_reference','currency','reason','net_amount','tax_amount','refund_amount','created_at')
_BOUND_ONCE=('native_return_id','credit_voucher_id','refund_voucher_id','cash_movement_id','committed_at')


def _incomplete_sql(connection):
    different='IS NOT' if connection.dialect.name=='sqlite' else 'IS DISTINCT FROM'
    money=' OR '.join(f"(SELECT ROUND(COALESCE(SUM({field}),0),2) FROM business_pharma_return_lines WHERE return_id=NEW.id) {different} NEW.{target}"
        for field,target in (('net_amount','net_amount'),('tax_amount','tax_amount'),('gross_amount','refund_amount')))
    native=' OR '.join(f'n.{left} {different} l.{right}' for left,right in
        (('quantity','quantity'),('tax_amount','tax_amount'),('line_total','gross_amount'),
         ('sales_order_line_id','sales_order_line_id'),('product_id','product_id')))
    vouchers=' OR '.join(f"NOT EXISTS(SELECT 1 FROM fam_vouchers v JOIN fam_voucher_types t ON t.id=v.voucher_type_id WHERE v.id=NEW.{pointer} AND v.company_id=NEW.organization_id AND t.company_id=NEW.organization_id AND t.voucher_type_code='{code}' AND v.status='posted' AND v.source_module='srm' AND v.source_record_type='pharma_return' AND v.source_record_id=CAST(NEW.id AS TEXT) AND v.total_debit=NEW.refund_amount AND v.total_credit=NEW.refund_amount)"
        for pointer,code in (('credit_voucher_id','CN'),('refund_voucher_id','PV')))
    return f"""NOT EXISTS(SELECT 1 FROM business_pharma_return_lines WHERE return_id=NEW.id) OR ({money}) OR ({vouchers}) OR
        NOT EXISTS(SELECT 1 FROM srm_pos_returns r JOIN srm_pos_service_checkouts c ON c.id=NEW.checkout_id
          WHERE r.id=NEW.native_return_id AND r.organization_id=NEW.organization_id AND r.sales_order_id=NEW.sales_order_id
          AND r.customer_id=c.customer_id AND r.session_id=NEW.collection_session_id AND r.created_by=NEW.created_by
          AND r.refund_method=NEW.refund_method AND r.refund_status='refunded'
          AND r.subtotal=NEW.net_amount AND r.tax_amount=NEW.tax_amount AND r.refund_amount=NEW.refund_amount) OR
        EXISTS(SELECT 1 FROM business_pharma_return_lines l LEFT JOIN srm_pos_return_lines n ON n.id=l.native_return_line_id
          WHERE l.return_id=NEW.id AND (n.id IS NULL OR n.return_id {different} NEW.native_return_id OR ({native}) OR n.restock {different} false OR
          EXISTS(SELECT 1 FROM business_pharma_return_lots q WHERE q.return_line_id=l.id AND q.warehouse_id {different} n.warehouse_id) OR
          NOT EXISTS(SELECT 1 FROM business_pharma_return_lots q WHERE q.return_line_id=l.id) OR
          (SELECT ROUND(COALESCE(SUM(q.quantity),0),3) FROM business_pharma_return_lots q WHERE q.return_line_id=l.id) {different} l.quantity)) OR
        EXISTS(SELECT 1 FROM business_pharma_return_lots q LEFT JOIN srm_inventory_movements m ON m.id=q.stock_movement_id
          LEFT JOIN srm_inventory_batches b ON b.id=q.quarantine_batch_id WHERE q.return_id=NEW.id AND
          (m.id IS NULL OR b.id IS NULL OR m.organization_id {different} NEW.organization_id OR
           m.product_id {different} q.product_id OR m.warehouse_id {different} q.warehouse_id OR
           m.quantity_in {different} q.quantity OR m.quantity_out {different} 0 OR
           m.movement_type {different} 'pharma_return_quarantine' OR m.created_by {different} NEW.created_by OR
           b.organization_id {different} NEW.organization_id OR b.product_id {different} q.product_id OR
           b.warehouse_id {different} q.warehouse_id OR b.quantity {different} q.quantity OR
           b.available_quantity {different} 0 OR b.status {different} 'quarantined'))"""


def _history_guards(connection):
    children=('business_pharma_return_lines',)
    if connection.dialect.name=='sqlite':
        for table in children:
            for action in ('UPDATE','DELETE'):
                connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Issued Pharma source history is immutable'); END")
        table='business_pharma_returns'
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'Issued Pharma return history is immutable'); END")
        changed=' OR '.join(f'NEW.{name} IS NOT OLD.{name}' for name in _ROOT_IMMUTABLE)
        rebound=' OR '.join(f'(OLD.{name} IS NOT NULL AND NEW.{name} IS NOT OLD.{name})' for name in _BOUND_ONCE)
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {table}_update BEFORE UPDATE ON {table} WHEN OLD.state='committed' OR ({changed}) OR ({rebound}) OR NEW.revision<>OLD.revision+1 OR (NEW.state IS NOT OLD.state AND NOT (OLD.state='draft' AND NEW.state='committed')) BEGIN SELECT RAISE(ABORT,'Issued Pharma source and charge identity is immutable'); END")
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_return_complete BEFORE UPDATE ON {table} WHEN NEW.state='committed' AND ({_incomplete_sql(connection)}) BEGIN SELECT RAISE(ABORT,'Medicine return has incomplete native quarantine sources'); END")
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_return_no_committed_insert BEFORE INSERT ON {table} WHEN NEW.state='committed' BEGIN SELECT RAISE(ABORT,'Medicine return must start uncommitted'); END")
        for action in ('UPDATE','DELETE'):
            connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_refund_cash_{action.lower()} BEFORE {action} ON srm_pos_cash_movements WHEN EXISTS(SELECT 1 FROM business_pharma_returns WHERE cash_movement_id=OLD.id) BEGIN SELECT RAISE(ABORT,'Issued Pharma cash refund history is immutable'); END")
    else:
        connection.exec_driver_sql("""CREATE OR REPLACE FUNCTION pharma_immutable_source_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Issued Pharma source history is immutable'; END $$""")
        for table in children:
            connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS pharma_immutable_source ON {table}')
            connection.exec_driver_sql(f'CREATE TRIGGER pharma_immutable_source BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION pharma_immutable_source_history()')
        changed=' OR '.join(f'NEW.{name} IS DISTINCT FROM OLD.{name}' for name in _ROOT_IMMUTABLE)
        rebound=' OR '.join(f'(OLD.{name} IS NOT NULL AND NEW.{name} IS DISTINCT FROM OLD.{name})' for name in _BOUND_ONCE)
        connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION pharma_immutable_return_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Issued Pharma return history is immutable'; END IF;
            IF OLD.state='committed' OR ({changed}) OR ({rebound}) OR NEW.revision<>OLD.revision+1 OR (NEW.state IS DISTINCT FROM OLD.state AND NOT (OLD.state='draft' AND NEW.state='committed')) THEN
                RAISE EXCEPTION 'Issued Pharma source and charge identity is immutable';
            END IF; RETURN NEW; END $$""")
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS pharma_immutable_return ON business_pharma_returns')
        connection.exec_driver_sql('CREATE TRIGGER pharma_immutable_return BEFORE UPDATE OR DELETE ON business_pharma_returns FOR EACH ROW EXECUTE FUNCTION pharma_immutable_return_history()')
        connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION pharma_return_complete() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF NEW.state='committed' AND ({_incomplete_sql(connection)}) THEN RAISE EXCEPTION 'Medicine return has incomplete native quarantine sources'; END IF;
            RETURN NEW; END $$""")
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS pharma_return_complete ON business_pharma_returns')
        connection.exec_driver_sql('CREATE TRIGGER pharma_return_complete BEFORE INSERT OR UPDATE ON business_pharma_returns FOR EACH ROW EXECUTE FUNCTION pharma_return_complete()')
        connection.exec_driver_sql("""CREATE OR REPLACE FUNCTION pharma_immutable_cash_refund() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF EXISTS(SELECT 1 FROM business_pharma_returns WHERE cash_movement_id=OLD.id) THEN RAISE EXCEPTION 'Issued Pharma cash refund history is immutable'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS pharma_immutable_cash_refund ON srm_pos_cash_movements')
        connection.exec_driver_sql('CREATE TRIGGER pharma_immutable_cash_refund BEFORE UPDATE OR DELETE ON srm_pos_cash_movements FOR EACH ROW EXECUTE FUNCTION pharma_immutable_cash_refund()')


_LOT_IMMUTABLE=('id','return_line_id','return_id','checkout_id','checkout_line_id','organization_id',
    'branch_id','pack_context_id','product_id','sales_order_line_id','warehouse_id','allocation_id',
    'original_batch_id','quarantine_batch_id','original_batch_number','original_expiry_date',
    'quantity','disposition','created_at')


def _lot_guards(connection):
    table='business_pharma_return_lots'
    if connection.dialect.name=='sqlite':
        changed=' OR '.join(f'NEW.{name} IS NOT OLD.{name}' for name in _LOT_IMMUTABLE)
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_return_lot_update BEFORE UPDATE ON {table} WHEN ({changed}) OR OLD.stock_movement_id IS NOT NULL OR NEW.stock_movement_id IS NULL OR EXISTS(SELECT 1 FROM business_pharma_returns WHERE id=OLD.return_id AND state='committed') BEGIN SELECT RAISE(ABORT,'Original medicine return lot is immutable'); END")
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_return_lot_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'Original medicine return lot is immutable'); END")
        for native,column in (('srm_inventory_batches','quarantine_batch_id'),('srm_inventory_movements','stock_movement_id')):
            for action in ('UPDATE','DELETE'):
                connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_return_{native}_{action.lower()} BEFORE {action} ON {native} WHEN EXISTS(SELECT 1 FROM {table} WHERE {column}=OLD.id) BEGIN SELECT RAISE(ABORT,'Returned medicine stock provenance is immutable'); END")
    else:
        changed=' OR '.join(f'NEW.{name} IS DISTINCT FROM OLD.{name}' for name in _LOT_IMMUTABLE)
        connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION pharma_return_lot_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Original medicine return lot is immutable'; END IF;
            IF ({changed}) OR OLD.stock_movement_id IS NOT NULL OR NEW.stock_movement_id IS NULL OR EXISTS(SELECT 1 FROM business_pharma_returns WHERE id=OLD.return_id AND state='committed') THEN RAISE EXCEPTION 'Original medicine return lot is immutable'; END IF;
            RETURN NEW; END $$""")
        connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS pharma_return_lot_history ON {table}')
        connection.exec_driver_sql(f'CREATE TRIGGER pharma_return_lot_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION pharma_return_lot_history()')
        for native,column in (('srm_inventory_batches','quarantine_batch_id'),('srm_inventory_movements','stock_movement_id')):
            function='pharma_return_'+native
            connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                IF EXISTS(SELECT 1 FROM {table} WHERE {column}=OLD.id) THEN RAISE EXCEPTION 'Returned medicine stock provenance is immutable'; END IF;
                IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
            connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS {function} ON {native}')
            connection.exec_driver_sql(f'CREATE TRIGGER {function} BEFORE UPDATE OR DELETE ON {native} FOR EACH ROW EXECUTE FUNCTION {function}()')


def _native_guards(connection):
    different='IS NOT' if connection.dialect.name=='sqlite' else 'IS DISTINCT FROM'
    fields=('id','organization_id','return_number','sales_order_id','session_id','customer_id','customer_name',
            'status','refund_method','subtotal','tax_amount','refund_amount','reason','created_by','created_at')
    changed=' OR '.join(f'NEW.{name} {different} OLD.{name}' for name in fields)
    changed+=f' OR CAST(NEW.metadata_json AS TEXT) {different} CAST(OLD.metadata_json AS TEXT)'
    owned="EXISTS(SELECT 1 FROM business_pharma_returns WHERE native_return_id=OLD.id)"
    committed="EXISTS(SELECT 1 FROM business_pharma_returns WHERE native_return_id=OLD.id AND state='committed')"
    status=f"NEW.refund_status {different} OLD.refund_status AND NOT (OLD.refund_status='pending' AND NEW.refund_status='refunded')"
    if connection.dialect.name=='sqlite':
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_native_return_update BEFORE UPDATE ON srm_pos_returns WHEN {owned} AND (({changed}) OR {committed} OR ({status})) BEGIN SELECT RAISE(ABORT,'Original medicine native return is immutable'); END")
        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_native_return_delete BEFORE DELETE ON srm_pos_returns WHEN {owned} BEGIN SELECT RAISE(ABORT,'Original medicine native return is immutable'); END")
        for action in ('UPDATE','DELETE'):
            connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS pharma_native_return_line_{action.lower()} BEFORE {action} ON srm_pos_return_lines WHEN EXISTS(SELECT 1 FROM business_pharma_return_lines WHERE native_return_line_id=OLD.id) BEGIN SELECT RAISE(ABORT,'Original medicine native return line is immutable'); END")
    else:
        connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION pharma_native_return_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF {owned} THEN
                IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Original medicine native return is immutable'; END IF;
                IF ({changed}) OR {committed} OR ({status}) THEN RAISE EXCEPTION 'Original medicine native return is immutable'; END IF;
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS pharma_native_return_history ON srm_pos_returns')
        connection.exec_driver_sql('CREATE TRIGGER pharma_native_return_history BEFORE UPDATE OR DELETE ON srm_pos_returns FOR EACH ROW EXECUTE FUNCTION pharma_native_return_history()')
        connection.exec_driver_sql("""CREATE OR REPLACE FUNCTION pharma_native_return_line_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF EXISTS(SELECT 1 FROM business_pharma_return_lines WHERE native_return_line_id=OLD.id) THEN RAISE EXCEPTION 'Original medicine native return line is immutable'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$""")
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS pharma_native_return_line_history ON srm_pos_return_lines')
        connection.exec_driver_sql('CREATE TRIGGER pharma_native_return_line_history BEFORE UPDATE OR DELETE ON srm_pos_return_lines FOR EACH ROW EXECUTE FUNCTION pharma_native_return_line_history()')


def upgrade():
    connection=op.get_bind()
    dialect=connection.dialect.name
    if dialect not in _DDL:raise RuntimeError('Unsupported Pharma return source migration dialect')
    inspector=sa.inspect(connection)
    if not inspector.has_table('business_pharma_batch_allocations'):
        raise RuntimeError('Original Pharma allocation sources must be installed first')
    if 'uq_pharma_allocation_return_source' not in {item['name'] for item in inspector.get_indexes('business_pharma_batch_allocations')}:
        connection.exec_driver_sql(_SOURCE_INDEX[dialect])
    for name,ddl,indexes in _DDL[dialect]:
        if not sa.inspect(connection).has_table(name):connection.exec_driver_sql(ddl)
        installed={index['name'] for index in sa.inspect(connection).get_indexes(name)}
        for index,statement in indexes:
            if index not in installed:connection.exec_driver_sql(statement)
    _history_guards(connection)
    _lot_guards(connection)
    _native_guards(connection)


def downgrade():
    # Never erase issued original-lot, quarantine or financial history.
    pass

