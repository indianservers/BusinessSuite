"""Unpaid native Restaurant tabs and canonical kitchen stock provenance."""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261115_113_restaurant_tabs'
down_revision = 'pg_20261115_112_pharma_recall'
branch_labels = depends_on = None

_DDL = {'postgresql': [('business_restaurant_tab_lines',
                 '\n'
                 'CREATE TABLE business_restaurant_tab_lines (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tservice_order_id INTEGER NOT NULL, \n'
                 '\tsales_order_line_id INTEGER NOT NULL, \n'
                 '\tproduct_id INTEGER NOT NULL, \n'
                 '\twarehouse_id INTEGER, \n'
                 '\tquantity NUMERIC(12, 2) NOT NULL, \n'
                 '\tunit_price NUMERIC(14, 2) NOT NULL, \n'
                 '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\tline_total NUMERIC(14, 2) NOT NULL, \n'
                 '\titem VARCHAR(500) NOT NULL, \n'
                 '\tcatalog_tax_snapshot JSON NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_restaurant_tab_line_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_restaurant_tab_line_source UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT fk_restaurant_tab_line_order FOREIGN KEY(service_order_id, organization_id, '
                 'branch_id, pack_context_id) REFERENCES business_restaurant_service_orders (id, '
                 'organization_id, branch_id, pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_restaurant_tab_native_line UNIQUE (sales_order_line_id), \n'
                 '\tCONSTRAINT ck_restaurant_tab_charge CHECK (quantity > 0 AND unit_price >= 0 AND '
                 'tax_amount >= 0 AND line_total >= 0), \n'
                 '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('business_restaurant_kitchen_issues',
                 '\n'
                 'CREATE TABLE business_restaurant_kitchen_issues (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tkitchen_line_id INTEGER NOT NULL, \n'
                 '\tmovement_id INTEGER NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_restaurant_kitchen_issue_context FOREIGN KEY(pack_context_id, '
                 'organization_id, branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) '
                 'ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_restaurant_kitchen_issue_source UNIQUE (id, organization_id, branch_id, '
                 'pack_context_id), \n'
                 '\tCONSTRAINT fk_restaurant_issue_line FOREIGN KEY(kitchen_line_id, organization_id, '
                 'branch_id, pack_context_id) REFERENCES business_restaurant_kitchen_lines (id, '
                 'organization_id, branch_id, pack_context_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_restaurant_kitchen_stock_once UNIQUE (kitchen_line_id), \n'
                 '\tCONSTRAINT uq_restaurant_kitchen_native_movement UNIQUE (movement_id), \n'
                 '\tFOREIGN KEY(movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [])],
 'sqlite': [('business_restaurant_tab_lines',
             '\n'
             'CREATE TABLE business_restaurant_tab_lines (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tservice_order_id INTEGER NOT NULL, \n'
             '\tsales_order_line_id INTEGER NOT NULL, \n'
             '\tproduct_id INTEGER NOT NULL, \n'
             '\twarehouse_id INTEGER, \n'
             '\tquantity NUMERIC(12, 2) NOT NULL, \n'
             '\tunit_price NUMERIC(14, 2) NOT NULL, \n'
             '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
             '\tline_total NUMERIC(14, 2) NOT NULL, \n'
             '\titem VARCHAR(500) NOT NULL, \n'
             '\tcatalog_tax_snapshot JSON NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_restaurant_tab_line_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_restaurant_tab_line_source UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT fk_restaurant_tab_line_order FOREIGN KEY(service_order_id, organization_id, '
             'branch_id, pack_context_id) REFERENCES business_restaurant_service_orders (id, '
             'organization_id, branch_id, pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_restaurant_tab_native_line UNIQUE (sales_order_line_id), \n'
             '\tCONSTRAINT ck_restaurant_tab_charge CHECK (quantity > 0 AND unit_price >= 0 AND tax_amount '
             '>= 0 AND line_total >= 0), \n'
             '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('business_restaurant_kitchen_issues',
             '\n'
             'CREATE TABLE business_restaurant_kitchen_issues (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tkitchen_line_id INTEGER NOT NULL, \n'
             '\tmovement_id INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_restaurant_kitchen_issue_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_restaurant_kitchen_issue_source UNIQUE (id, organization_id, branch_id, '
             'pack_context_id), \n'
             '\tCONSTRAINT fk_restaurant_issue_line FOREIGN KEY(kitchen_line_id, organization_id, branch_id, '
             'pack_context_id) REFERENCES business_restaurant_kitchen_lines (id, organization_id, branch_id, '
             'pack_context_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_restaurant_kitchen_stock_once UNIQUE (kitchen_line_id), \n'
             '\tCONSTRAINT uq_restaurant_kitchen_native_movement UNIQUE (movement_id), \n'
             '\tFOREIGN KEY(movement_id) REFERENCES srm_inventory_movements (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [])]}

def upgrade():
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in _DDL:
        raise RuntimeError('Unsupported Restaurant tab migration dialect')
    columns = {column['name']: column for column in sa.inspect(connection).get_columns('business_restaurant_service_orders')}
    if 'source_kind' not in columns:
        with op.batch_alter_table('business_restaurant_service_orders') as batch:
            batch.add_column(sa.Column('source_kind', sa.String(20), nullable=False, server_default='paid_pos'))
            batch.alter_column('checkout_id', existing_type=sa.Integer(), nullable=True)
            batch.create_check_constraint('ck_restaurant_order_kind', "(source_kind = 'paid_pos' AND checkout_id IS NOT NULL) OR (source_kind = 'unpaid_tab' AND checkout_id IS NULL)")
    for name, ddl, indexes in _DDL[dialect]:
        if not sa.inspect(connection).has_table(name):
            connection.exec_driver_sql(ddl)
        installed = {index['name'] for index in sa.inspect(connection).get_indexes(name)}
        for index, sql in indexes:
            if index not in installed:
                connection.exec_driver_sql(sql)


def downgrade():
    # Historical native fulfillment and charges must not be removed.
    pass
