"""Typed Pharma stock receipt/allocation provenance; no legacy lot adoption."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261115_109_pharma_stock'
down_revision='pg_20261115_108_retail_returns'
branch_labels=depends_on=None

_DDL = {'postgresql': [('business_pharma_batch_availability',
                 '\n'
                 'CREATE TABLE business_pharma_batch_availability (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tbatch_id INTEGER NOT NULL, \n'
                 '\tactive BOOLEAN NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_pharma_batch_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_pharma_batch_available UNIQUE (pack_context_id, batch_id), \n'
                 '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('business_pharma_batch_receipts',
                 '\n'
                 'CREATE TABLE business_pharma_batch_receipts (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\trequest_key VARCHAR(36) NOT NULL, \n'
                 '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tproduct_id INTEGER NOT NULL, \n'
                 '\twarehouse_id INTEGER NOT NULL, \n'
                 '\tbatch_id INTEGER NOT NULL, \n'
                 '\tmovement_id INTEGER, \n'
                 '\tquantity NUMERIC(14, 3) NOT NULL, \n'
                 '\tunit_cost NUMERIC(14, 4) NOT NULL, \n'
                 '\tbatch_number VARCHAR(120) NOT NULL, \n'
                 '\tmanufacture_date DATE, \n'
                 '\texpiry_date DATE NOT NULL, \n'
                 '\treceived_date DATE NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_pharma_receipt_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_pharma_receipt_request UNIQUE (organization_id, branch_id, '
                 'pack_context_id, request_key), \n'
                 '\tCONSTRAINT ck_pharma_receipt_quantity CHECK (quantity > 0 AND unit_cost >= 0), \n'
                 '\tCONSTRAINT ck_pharma_receipt_request CHECK (length(request_key)=36 AND '
                 'length(request_sha256)=64), \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (movement_id), \n'
                 '\tFOREIGN KEY(movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [('ix_business_pharma_batch_receipts_organization_id',
                   'CREATE INDEX ix_business_pharma_batch_receipts_organization_id ON '
                   'business_pharma_batch_receipts (organization_id)')]),
                ('business_pharma_batch_allocations',
                 '\n'
                 'CREATE TABLE business_pharma_batch_allocations (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tsales_order_line_id INTEGER NOT NULL, \n'
                 '\tbatch_id INTEGER NOT NULL, \n'
                 '\tmovement_id INTEGER NOT NULL, \n'
                 '\tproduct_id INTEGER NOT NULL, \n'
                 '\twarehouse_id INTEGER NOT NULL, \n'
                 '\tquantity NUMERIC(14, 3) NOT NULL, \n'
                 '\tbatch_number VARCHAR(120) NOT NULL, \n'
                 '\texpiry_date DATE NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_pharma_allocation_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_pharma_line_batch UNIQUE (sales_order_line_id, batch_id), \n'
                 '\tCONSTRAINT ck_pharma_allocation_quantity CHECK (quantity > 0), \n'
                 '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [('ix_business_pharma_batch_allocations_organization_id',
                   'CREATE INDEX ix_business_pharma_batch_allocations_organization_id ON '
                   'business_pharma_batch_allocations (organization_id)')])],
 'sqlite': [('business_pharma_batch_availability',
             '\n'
             'CREATE TABLE business_pharma_batch_availability (\n'
             '\tid INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tbatch_id INTEGER NOT NULL, \n'
             '\tactive BOOLEAN NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_pharma_batch_context FOREIGN KEY(pack_context_id, organization_id, branch_id) '
             'REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_pharma_batch_available UNIQUE (pack_context_id, batch_id), \n'
             '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('business_pharma_batch_receipts',
             '\n'
             'CREATE TABLE business_pharma_batch_receipts (\n'
             '\tid INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\trequest_key VARCHAR(36) NOT NULL, \n'
             '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tproduct_id INTEGER NOT NULL, \n'
             '\twarehouse_id INTEGER NOT NULL, \n'
             '\tbatch_id INTEGER NOT NULL, \n'
             '\tmovement_id INTEGER, \n'
             '\tquantity NUMERIC(14, 3) NOT NULL, \n'
             '\tunit_cost NUMERIC(14, 4) NOT NULL, \n'
             '\tbatch_number VARCHAR(120) NOT NULL, \n'
             '\tmanufacture_date DATE, \n'
             '\texpiry_date DATE NOT NULL, \n'
             '\treceived_date DATE NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_pharma_receipt_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_pharma_receipt_request UNIQUE (organization_id, branch_id, pack_context_id, '
             'request_key), \n'
             '\tCONSTRAINT ck_pharma_receipt_quantity CHECK (quantity > 0 AND unit_cost >= 0), \n'
             '\tCONSTRAINT ck_pharma_receipt_request CHECK (length(request_key)=36 AND '
             'length(request_sha256)=64), \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (movement_id), \n'
             '\tFOREIGN KEY(movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [('ix_business_pharma_batch_receipts_organization_id',
               'CREATE INDEX ix_business_pharma_batch_receipts_organization_id ON '
               'business_pharma_batch_receipts (organization_id)')]),
            ('business_pharma_batch_allocations',
             '\n'
             'CREATE TABLE business_pharma_batch_allocations (\n'
             '\tid INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tsales_order_line_id INTEGER NOT NULL, \n'
             '\tbatch_id INTEGER NOT NULL, \n'
             '\tmovement_id INTEGER NOT NULL, \n'
             '\tproduct_id INTEGER NOT NULL, \n'
             '\twarehouse_id INTEGER NOT NULL, \n'
             '\tquantity NUMERIC(14, 3) NOT NULL, \n'
             '\tbatch_number VARCHAR(120) NOT NULL, \n'
             '\texpiry_date DATE NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_pharma_allocation_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_pharma_line_batch UNIQUE (sales_order_line_id, batch_id), \n'
             '\tCONSTRAINT ck_pharma_allocation_quantity CHECK (quantity > 0), \n'
             '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [('ix_business_pharma_batch_allocations_organization_id',
               'CREATE INDEX ix_business_pharma_batch_allocations_organization_id ON '
               'business_pharma_batch_allocations (organization_id)')])]}

def upgrade():
    connection=op.get_bind()
    dialect=connection.dialect.name
    if dialect not in _DDL:raise RuntimeError('Unsupported Pharma migration dialect')
    for name,ddl,indexes in _DDL[dialect]:
        if not sa.inspect(connection).has_table(name):connection.exec_driver_sql(ddl)
        installed={index['name'] for index in sa.inspect(connection).get_indexes(name)}
        for index,sql in indexes:
            if index not in installed:connection.exec_driver_sql(sql)


def downgrade():
    # Permanent native inventory provenance must not be removed automatically.
    pass
