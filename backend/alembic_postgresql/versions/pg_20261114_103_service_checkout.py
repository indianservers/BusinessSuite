"""Add typed service checkout sources; no API activation or ledger duplication.

Frozen dialect DDL deliberately imports no evolving application definitions.
"""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261114_103_service_checkout'
down_revision = 'pg_20261114_102_pack_foundation'
branch_labels = depends_on = None

_DDL = {'sqlite': [('srm_service_booking_policies',
             '\n'
             'CREATE TABLE srm_service_booking_policies (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tservice_product_id INTEGER NOT NULL, \n'
             "\tbooking_required BOOLEAN DEFAULT 'true' NOT NULL, \n"
             '\tdefault_duration_minutes INTEGER NOT NULL, \n'
             '\tmin_duration_minutes INTEGER NOT NULL, \n'
             '\tmax_duration_minutes INTEGER NOT NULL, \n'
             "\tallow_duration_override BOOLEAN DEFAULT 'false' NOT NULL, \n"
             "\tactive BOOLEAN DEFAULT 'true' NOT NULL, \n"
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER, \n'
             '\tscope_context_key INTEGER NOT NULL GENERATED ALWAYS AS (coalesce(pack_context_id, 0)) '
             'STORED, \n'
             "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_service_policy_pack_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT ck_service_policy_pack_context CHECK (pack_context_id IS NULL OR pack_context_id '
             '> 0), \n'
             '\tCONSTRAINT uq_service_policy_source UNIQUE (id, organization_id, branch_id, '
             'scope_context_key, service_product_id), \n'
             '\tCONSTRAINT ck_service_policy_duration CHECK (min_duration_minutes >= 5 AND '
             'max_duration_minutes <= 720 AND min_duration_minutes <= default_duration_minutes AND '
             'default_duration_minutes <= max_duration_minutes), \n'
             '\tCONSTRAINT ck_service_policy_revision CHECK (revision > 0), \n'
             '\tFOREIGN KEY(service_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT ck_service_policy_required CHECK (booking_required IN (0, 1)), \n'
             '\tCONSTRAINT ck_service_policy_override CHECK (allow_duration_override IN (0, 1)), \n'
             '\tCONSTRAINT ck_service_policy_active CHECK (active IN (0, 1)), \n'
             '\tFOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [('uq_service_policy_legacy',
               'CREATE UNIQUE INDEX uq_service_policy_legacy ON srm_service_booking_policies '
               '(organization_id, branch_id, service_product_id) WHERE pack_context_id IS NULL'),
              ('uq_service_policy_pack',
               'CREATE UNIQUE INDEX uq_service_policy_pack ON srm_service_booking_policies (organization_id, '
               'branch_id, pack_context_id, service_product_id) WHERE pack_context_id IS NOT NULL')]),
            ('srm_service_specialist_eligibility',
             '\n'
             'CREATE TABLE srm_service_specialist_eligibility (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tbooking_policy_id INTEGER NOT NULL, \n'
             '\tservice_product_id INTEGER NOT NULL, \n'
             '\tprovider_resource_id INTEGER NOT NULL, \n'
             '\teffective_from DATETIME, \n'
             '\teffective_until DATETIME, \n'
             "\tactive BOOLEAN DEFAULT 'true' NOT NULL, \n"
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER, \n'
             '\tscope_context_key INTEGER NOT NULL GENERATED ALWAYS AS (coalesce(pack_context_id, 0)) '
             'STORED, \n'
             "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_service_eligibility_pack_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT ck_service_eligibility_pack_context CHECK (pack_context_id IS NULL OR '
             'pack_context_id > 0), \n'
             '\tCONSTRAINT fk_service_eligibility_policy FOREIGN KEY(booking_policy_id, organization_id, '
             'branch_id, scope_context_key, service_product_id) REFERENCES srm_service_booking_policies (id, '
             'organization_id, branch_id, scope_context_key, service_product_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_service_eligibility_source UNIQUE (id, booking_policy_id, organization_id, '
             'branch_id, scope_context_key, service_product_id, provider_resource_id), \n'
             '\tCONSTRAINT ck_service_eligibility_interval CHECK (effective_until IS NULL OR effective_from '
             'IS NULL OR effective_until > effective_from), \n'
             '\tCONSTRAINT ck_service_eligibility_revision CHECK (revision > 0), \n'
             '\tFOREIGN KEY(service_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(provider_resource_id) REFERENCES srm_industry_records (id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT ck_service_eligibility_active CHECK (active IN (0, 1)), \n'
             '\tFOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [('uq_service_eligibility_legacy',
               'CREATE UNIQUE INDEX uq_service_eligibility_legacy ON srm_service_specialist_eligibility '
               '(organization_id, branch_id, service_product_id, provider_resource_id) WHERE pack_context_id '
               'IS NULL'),
              ('uq_service_eligibility_pack',
               'CREATE UNIQUE INDEX uq_service_eligibility_pack ON srm_service_specialist_eligibility '
               '(organization_id, branch_id, pack_context_id, service_product_id, provider_resource_id) '
               'WHERE pack_context_id IS NOT NULL')]),
            ('srm_pos_service_checkouts',
             '\n'
             'CREATE TABLE srm_pos_service_checkouts (\n'
             '\tid INTEGER NOT NULL, \n'
             '\trequest_id VARCHAR(36) NOT NULL, \n'
             '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
             '\tcreated_by INTEGER NOT NULL, \n'
             '\tcustomer_id INTEGER NOT NULL, \n'
             '\tcurrency VARCHAR(3) NOT NULL, \n'
             '\tpos_session_id INTEGER NOT NULL, \n'
             '\tsales_order_id INTEGER, \n'
             '\tinvoice_id INTEGER, \n'
             "\tstate VARCHAR(20) DEFAULT 'draft' NOT NULL, \n"
             '\tbilling_mode VARCHAR(30) NOT NULL, \n'
             '\tcommitted_at DATETIME, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tpack_context_id INTEGER, \n'
             '\tscope_context_key INTEGER NOT NULL GENERATED ALWAYS AS (coalesce(pack_context_id, 0)) '
             'STORED, \n'
             "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_service_checkout_pack_context FOREIGN KEY(pack_context_id, organization_id, '
             'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT ck_service_checkout_pack_context CHECK (pack_context_id IS NULL OR '
             'pack_context_id > 0), \n'
             '\tCONSTRAINT uq_service_checkout_source UNIQUE (id, organization_id, branch_id, '
             'scope_context_key), \n'
             "\tCONSTRAINT ck_service_checkout_state CHECK (state IN ('draft','committed','cancelled')), \n"
             '\tCONSTRAINT ck_service_checkout_billing_mode CHECK (billing_mode IN '
             "('invoice_at_checkout','advance_then_invoice')), \n"
             "\tCONSTRAINT ck_service_checkout_commit_sources CHECK (state != 'committed' OR (sales_order_id "
             "IS NOT NULL AND committed_at IS NOT NULL AND (billing_mode != 'invoice_at_checkout' OR "
             'invoice_id IS NOT NULL))), \n'
             '\tCONSTRAINT ck_service_checkout_request CHECK (length(request_id) = 36 AND '
             'length(request_sha256) = 64), \n'
             '\tCONSTRAINT ck_service_checkout_currency CHECK (length(currency) = 3 AND currency = '
             'upper(currency)), \n'
             '\tCONSTRAINT ck_service_checkout_revision CHECK (revision > 0), \n'
             '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(customer_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(pos_session_id) REFERENCES srm_pos_sessions (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (sales_order_id), \n'
             '\tFOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (invoice_id), \n'
             '\tFOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [('uq_service_checkout_request_legacy',
               'CREATE UNIQUE INDEX uq_service_checkout_request_legacy ON srm_pos_service_checkouts '
               '(organization_id, branch_id, request_id) WHERE pack_context_id IS NULL'),
              ('uq_service_checkout_request_pack',
               'CREATE UNIQUE INDEX uq_service_checkout_request_pack ON srm_pos_service_checkouts '
               '(organization_id, branch_id, pack_context_id, request_id) WHERE pack_context_id IS NOT '
               'NULL')]),
            ('srm_pos_checkout_lines',
             '\n'
             'CREATE TABLE srm_pos_checkout_lines (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tcheckout_id INTEGER NOT NULL, \n'
             '\tclient_line_key VARCHAR(36) NOT NULL, \n'
             '\tline_kind VARCHAR(30) NOT NULL, \n'
             '\tproduct_id INTEGER NOT NULL, \n'
             '\tsales_order_line_id INTEGER NOT NULL, \n'
             '\tinvoice_line_id INTEGER, \n'
             '\tquantity NUMERIC(24, 10) NOT NULL, \n'
             '\tunit_price NUMERIC(14, 2) NOT NULL, \n'
             '\tdiscount_amount NUMERIC(14, 2) NOT NULL, \n'
             '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
             '\tline_total NUMERIC(14, 2) NOT NULL, \n'
             '\tcatalog_tax_snapshot JSON NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tscope_context_key INTEGER NOT NULL, \n'
             "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_checkout_line_checkout FOREIGN KEY(checkout_id, organization_id, branch_id, '
             'scope_context_key) REFERENCES srm_pos_service_checkouts (id, organization_id, branch_id, '
             'scope_context_key) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_checkout_line_client_key UNIQUE (checkout_id, client_line_key), \n'
             '\tCONSTRAINT uq_checkout_line_source UNIQUE (id, checkout_id, organization_id, branch_id, '
             'scope_context_key, product_id), \n'
             '\tCONSTRAINT ck_checkout_line_kind CHECK (line_kind IN '
             "('product','unscheduled_service','booked_service')), \n"
             '\tCONSTRAINT ck_checkout_line_quantity CHECK (quantity > 0 AND quantity <= 1000000000 AND '
             "(line_kind != 'booked_service' OR quantity = 1)), \n"
             '\tCONSTRAINT ck_checkout_line_money CHECK (unit_price >= 0 AND discount_amount >= 0 AND '
             'tax_amount >= 0 AND line_total >= 0 AND discount_amount <= quantity * unit_price), \n'
             '\tCONSTRAINT ck_checkout_line_identity CHECK (length(client_line_key) = 36 AND revision > '
             '0), \n'
             '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (sales_order_line_id), \n'
             '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE RESTRICT, \n'
             '\tUNIQUE (invoice_line_id), \n'
             '\tFOREIGN KEY(invoice_line_id) REFERENCES srm_invoice_lines (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('srm_pos_service_occurrences',
             '\n'
             'CREATE TABLE srm_pos_service_occurrences (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tcheckout_line_id INTEGER NOT NULL, \n'
             '\tcheckout_id INTEGER NOT NULL, \n'
             '\toccurrence_key VARCHAR(36) NOT NULL, \n'
             '\tappointment_id INTEGER NOT NULL, \n'
             '\tservice_product_id INTEGER NOT NULL, \n'
             '\tprovider_resource_id INTEGER NOT NULL, \n'
             '\temployee_id INTEGER NOT NULL, \n'
             '\tstarts_at DATETIME NOT NULL, \n'
             '\tends_at DATETIME NOT NULL, \n'
             '\tduration_minutes INTEGER NOT NULL, \n'
             '\tbooking_policy_id INTEGER NOT NULL, \n'
             '\tpolicy_revision INTEGER NOT NULL, \n'
             '\teligibility_id INTEGER NOT NULL, \n'
             '\teligibility_revision INTEGER NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tscope_context_key INTEGER NOT NULL, \n'
             "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_service_occurrence_line FOREIGN KEY(checkout_line_id, checkout_id, '
             'organization_id, branch_id, scope_context_key, service_product_id) REFERENCES '
             'srm_pos_checkout_lines (id, checkout_id, organization_id, branch_id, scope_context_key, '
             'product_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT fk_service_occurrence_eligibility FOREIGN KEY(eligibility_id, booking_policy_id, '
             'organization_id, branch_id, scope_context_key, service_product_id, provider_resource_id) '
             'REFERENCES srm_service_specialist_eligibility (id, booking_policy_id, organization_id, '
             'branch_id, scope_context_key, service_product_id, provider_resource_id) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_service_occurrence_key UNIQUE (checkout_id, occurrence_key), \n'
             '\tCONSTRAINT ck_service_occurrence_duration CHECK (ends_at > starts_at AND duration_minutes >= '
             '5 AND duration_minutes <= 720), \n'
             '\tCONSTRAINT ck_service_occurrence_revision CHECK (policy_revision > 0 AND '
             'eligibility_revision > 0 AND revision > 0 AND length(occurrence_key) = 36), \n'
             '\tUNIQUE (checkout_line_id), \n'
             '\tUNIQUE (appointment_id), \n'
             '\tFOREIGN KEY(appointment_id) REFERENCES srm_industry_records (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(service_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(provider_resource_id) REFERENCES srm_industry_records (id) ON DELETE RESTRICT, \n'
             '\tFOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             []),
            ('srm_pos_checkout_payments',
             '\n'
             'CREATE TABLE srm_pos_checkout_payments (\n'
             '\tid INTEGER NOT NULL, \n'
             '\tcheckout_id INTEGER NOT NULL, \n'
             '\tpayment_key VARCHAR(36) NOT NULL, \n'
             '\treceipt_id INTEGER NOT NULL, \n'
             '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
             '\torganization_id INTEGER NOT NULL, \n'
             '\tbranch_id INTEGER NOT NULL, \n'
             '\tscope_context_key INTEGER NOT NULL, \n'
             "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
             '\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n'
             '\tPRIMARY KEY (id), \n'
             '\tCONSTRAINT fk_checkout_payment_checkout FOREIGN KEY(checkout_id, organization_id, branch_id, '
             'scope_context_key) REFERENCES srm_pos_service_checkouts (id, organization_id, branch_id, '
             'scope_context_key) ON DELETE RESTRICT, \n'
             '\tCONSTRAINT uq_checkout_payment_key UNIQUE (checkout_id, payment_key), \n'
             '\tCONSTRAINT ck_checkout_payment_identity CHECK (length(payment_key) = 36 AND '
             'length(request_sha256) = 64 AND revision > 0), \n'
             '\tUNIQUE (receipt_id), \n'
             '\tFOREIGN KEY(receipt_id) REFERENCES srm_receipts (id) ON DELETE RESTRICT\n'
             ')\n'
             '\n',
             [])],
 'postgresql': [('srm_service_booking_policies',
                 '\n'
                 'CREATE TABLE srm_service_booking_policies (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tservice_product_id INTEGER NOT NULL, \n'
                 "\tbooking_required BOOLEAN DEFAULT 'true' NOT NULL, \n"
                 '\tdefault_duration_minutes INTEGER NOT NULL, \n'
                 '\tmin_duration_minutes INTEGER NOT NULL, \n'
                 '\tmax_duration_minutes INTEGER NOT NULL, \n'
                 "\tallow_duration_override BOOLEAN DEFAULT 'false' NOT NULL, \n"
                 "\tactive BOOLEAN DEFAULT 'true' NOT NULL, \n"
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER, \n'
                 '\tscope_context_key INTEGER GENERATED ALWAYS AS (coalesce(pack_context_id, 0)) STORED NOT '
                 'NULL, \n'
                 "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_service_policy_pack_context FOREIGN KEY(pack_context_id, organization_id, '
                 'branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT ck_service_policy_pack_context CHECK (pack_context_id IS NULL OR '
                 'pack_context_id > 0), \n'
                 '\tCONSTRAINT uq_service_policy_source UNIQUE (id, organization_id, branch_id, '
                 'scope_context_key, service_product_id), \n'
                 '\tCONSTRAINT ck_service_policy_duration CHECK (min_duration_minutes >= 5 AND '
                 'max_duration_minutes <= 720 AND min_duration_minutes <= default_duration_minutes AND '
                 'default_duration_minutes <= max_duration_minutes), \n'
                 '\tCONSTRAINT ck_service_policy_revision CHECK (revision > 0), \n'
                 '\tFOREIGN KEY(service_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [('uq_service_policy_legacy',
                   'CREATE UNIQUE INDEX uq_service_policy_legacy ON srm_service_booking_policies '
                   '(organization_id, branch_id, service_product_id) WHERE pack_context_id IS NULL'),
                  ('uq_service_policy_pack',
                   'CREATE UNIQUE INDEX uq_service_policy_pack ON srm_service_booking_policies '
                   '(organization_id, branch_id, pack_context_id, service_product_id) WHERE pack_context_id '
                   'IS NOT NULL')]),
                ('srm_service_specialist_eligibility',
                 '\n'
                 'CREATE TABLE srm_service_specialist_eligibility (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tbooking_policy_id INTEGER NOT NULL, \n'
                 '\tservice_product_id INTEGER NOT NULL, \n'
                 '\tprovider_resource_id INTEGER NOT NULL, \n'
                 '\teffective_from TIMESTAMP WITH TIME ZONE, \n'
                 '\teffective_until TIMESTAMP WITH TIME ZONE, \n'
                 "\tactive BOOLEAN DEFAULT 'true' NOT NULL, \n"
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER, \n'
                 '\tscope_context_key INTEGER GENERATED ALWAYS AS (coalesce(pack_context_id, 0)) STORED NOT '
                 'NULL, \n'
                 "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_service_eligibility_pack_context FOREIGN KEY(pack_context_id, '
                 'organization_id, branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) '
                 'ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT ck_service_eligibility_pack_context CHECK (pack_context_id IS NULL OR '
                 'pack_context_id > 0), \n'
                 '\tCONSTRAINT fk_service_eligibility_policy FOREIGN KEY(booking_policy_id, organization_id, '
                 'branch_id, scope_context_key, service_product_id) REFERENCES srm_service_booking_policies '
                 '(id, organization_id, branch_id, scope_context_key, service_product_id) ON DELETE '
                 'RESTRICT, \n'
                 '\tCONSTRAINT uq_service_eligibility_source UNIQUE (id, booking_policy_id, organization_id, '
                 'branch_id, scope_context_key, service_product_id, provider_resource_id), \n'
                 '\tCONSTRAINT ck_service_eligibility_interval CHECK (effective_until IS NULL OR '
                 'effective_from IS NULL OR effective_until > effective_from), \n'
                 '\tCONSTRAINT ck_service_eligibility_revision CHECK (revision > 0), \n'
                 '\tFOREIGN KEY(service_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(provider_resource_id) REFERENCES srm_industry_records (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tFOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [('uq_service_eligibility_legacy',
                   'CREATE UNIQUE INDEX uq_service_eligibility_legacy ON srm_service_specialist_eligibility '
                   '(organization_id, branch_id, service_product_id, provider_resource_id) WHERE '
                   'pack_context_id IS NULL'),
                  ('uq_service_eligibility_pack',
                   'CREATE UNIQUE INDEX uq_service_eligibility_pack ON srm_service_specialist_eligibility '
                   '(organization_id, branch_id, pack_context_id, service_product_id, provider_resource_id) '
                   'WHERE pack_context_id IS NOT NULL')]),
                ('srm_pos_service_checkouts',
                 '\n'
                 'CREATE TABLE srm_pos_service_checkouts (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\trequest_id VARCHAR(36) NOT NULL, \n'
                 '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
                 '\tcreated_by INTEGER NOT NULL, \n'
                 '\tcustomer_id INTEGER NOT NULL, \n'
                 '\tcurrency VARCHAR(3) NOT NULL, \n'
                 '\tpos_session_id INTEGER NOT NULL, \n'
                 '\tsales_order_id INTEGER, \n'
                 '\tinvoice_id INTEGER, \n'
                 "\tstate VARCHAR(20) DEFAULT 'draft' NOT NULL, \n"
                 '\tbilling_mode VARCHAR(30) NOT NULL, \n'
                 '\tcommitted_at TIMESTAMP WITH TIME ZONE, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tpack_context_id INTEGER, \n'
                 '\tscope_context_key INTEGER GENERATED ALWAYS AS (coalesce(pack_context_id, 0)) STORED NOT '
                 'NULL, \n'
                 "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_service_checkout_pack_context FOREIGN KEY(pack_context_id, '
                 'organization_id, branch_id) REFERENCES business_pack_contexts (id, company_id, branch_id) '
                 'ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT ck_service_checkout_pack_context CHECK (pack_context_id IS NULL OR '
                 'pack_context_id > 0), \n'
                 '\tCONSTRAINT uq_service_checkout_source UNIQUE (id, organization_id, branch_id, '
                 'scope_context_key), \n'
                 '\tCONSTRAINT ck_service_checkout_state CHECK (state IN '
                 "('draft','committed','cancelled')), \n"
                 '\tCONSTRAINT ck_service_checkout_billing_mode CHECK (billing_mode IN '
                 "('invoice_at_checkout','advance_then_invoice')), \n"
                 "\tCONSTRAINT ck_service_checkout_commit_sources CHECK (state != 'committed' OR "
                 '(sales_order_id IS NOT NULL AND committed_at IS NOT NULL AND (billing_mode != '
                 "'invoice_at_checkout' OR invoice_id IS NOT NULL))), \n"
                 '\tCONSTRAINT ck_service_checkout_request CHECK (length(request_id) = 36 AND '
                 'length(request_sha256) = 64), \n'
                 '\tCONSTRAINT ck_service_checkout_currency CHECK (length(currency) = 3 AND currency = '
                 'upper(currency)), \n'
                 '\tCONSTRAINT ck_service_checkout_revision CHECK (revision > 0), \n'
                 '\tFOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(customer_id) REFERENCES crm_companies (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(pos_session_id) REFERENCES srm_pos_sessions (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (sales_order_id), \n'
                 '\tFOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (invoice_id), \n'
                 '\tFOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [('uq_service_checkout_request_legacy',
                   'CREATE UNIQUE INDEX uq_service_checkout_request_legacy ON srm_pos_service_checkouts '
                   '(organization_id, branch_id, request_id) WHERE pack_context_id IS NULL'),
                  ('uq_service_checkout_request_pack',
                   'CREATE UNIQUE INDEX uq_service_checkout_request_pack ON srm_pos_service_checkouts '
                   '(organization_id, branch_id, pack_context_id, request_id) WHERE pack_context_id IS NOT '
                   'NULL')]),
                ('srm_pos_checkout_lines',
                 '\n'
                 'CREATE TABLE srm_pos_checkout_lines (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tcheckout_id INTEGER NOT NULL, \n'
                 '\tclient_line_key VARCHAR(36) NOT NULL, \n'
                 '\tline_kind VARCHAR(30) NOT NULL, \n'
                 '\tproduct_id INTEGER NOT NULL, \n'
                 '\tsales_order_line_id INTEGER NOT NULL, \n'
                 '\tinvoice_line_id INTEGER, \n'
                 '\tquantity NUMERIC(24, 10) NOT NULL, \n'
                 '\tunit_price NUMERIC(14, 2) NOT NULL, \n'
                 '\tdiscount_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\ttax_amount NUMERIC(14, 2) NOT NULL, \n'
                 '\tline_total NUMERIC(14, 2) NOT NULL, \n'
                 '\tcatalog_tax_snapshot JSON NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tscope_context_key INTEGER NOT NULL, \n'
                 "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_checkout_line_checkout FOREIGN KEY(checkout_id, organization_id, '
                 'branch_id, scope_context_key) REFERENCES srm_pos_service_checkouts (id, organization_id, '
                 'branch_id, scope_context_key) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_checkout_line_client_key UNIQUE (checkout_id, client_line_key), \n'
                 '\tCONSTRAINT uq_checkout_line_source UNIQUE (id, checkout_id, organization_id, branch_id, '
                 'scope_context_key, product_id), \n'
                 '\tCONSTRAINT ck_checkout_line_kind CHECK (line_kind IN '
                 "('product','unscheduled_service','booked_service')), \n"
                 '\tCONSTRAINT ck_checkout_line_quantity CHECK (quantity > 0 AND quantity <= 1000000000 AND '
                 "(line_kind != 'booked_service' OR quantity = 1)), \n"
                 '\tCONSTRAINT ck_checkout_line_money CHECK (unit_price >= 0 AND discount_amount >= 0 AND '
                 'tax_amount >= 0 AND line_total >= 0 AND discount_amount <= quantity * unit_price), \n'
                 '\tCONSTRAINT ck_checkout_line_identity CHECK (length(client_line_key) = 36 AND revision > '
                 '0), \n'
                 '\tFOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tUNIQUE (sales_order_line_id), \n'
                 '\tFOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tUNIQUE (invoice_line_id), \n'
                 '\tFOREIGN KEY(invoice_line_id) REFERENCES srm_invoice_lines (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('srm_pos_service_occurrences',
                 '\n'
                 'CREATE TABLE srm_pos_service_occurrences (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tcheckout_line_id INTEGER NOT NULL, \n'
                 '\tcheckout_id INTEGER NOT NULL, \n'
                 '\toccurrence_key VARCHAR(36) NOT NULL, \n'
                 '\tappointment_id INTEGER NOT NULL, \n'
                 '\tservice_product_id INTEGER NOT NULL, \n'
                 '\tprovider_resource_id INTEGER NOT NULL, \n'
                 '\temployee_id INTEGER NOT NULL, \n'
                 '\tstarts_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                 '\tends_at TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                 '\tduration_minutes INTEGER NOT NULL, \n'
                 '\tbooking_policy_id INTEGER NOT NULL, \n'
                 '\tpolicy_revision INTEGER NOT NULL, \n'
                 '\teligibility_id INTEGER NOT NULL, \n'
                 '\teligibility_revision INTEGER NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tscope_context_key INTEGER NOT NULL, \n'
                 "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_service_occurrence_line FOREIGN KEY(checkout_line_id, checkout_id, '
                 'organization_id, branch_id, scope_context_key, service_product_id) REFERENCES '
                 'srm_pos_checkout_lines (id, checkout_id, organization_id, branch_id, scope_context_key, '
                 'product_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT fk_service_occurrence_eligibility FOREIGN KEY(eligibility_id, '
                 'booking_policy_id, organization_id, branch_id, scope_context_key, service_product_id, '
                 'provider_resource_id) REFERENCES srm_service_specialist_eligibility (id, '
                 'booking_policy_id, organization_id, branch_id, scope_context_key, service_product_id, '
                 'provider_resource_id) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_service_occurrence_key UNIQUE (checkout_id, occurrence_key), \n'
                 '\tCONSTRAINT ck_service_occurrence_duration CHECK (ends_at > starts_at AND '
                 'duration_minutes >= 5 AND duration_minutes <= 720), \n'
                 '\tCONSTRAINT ck_service_occurrence_revision CHECK (policy_revision > 0 AND '
                 'eligibility_revision > 0 AND revision > 0 AND length(occurrence_key) = 36), \n'
                 '\tUNIQUE (checkout_line_id), \n'
                 '\tUNIQUE (appointment_id), \n'
                 '\tFOREIGN KEY(appointment_id) REFERENCES srm_industry_records (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(service_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, \n'
                 '\tFOREIGN KEY(provider_resource_id) REFERENCES srm_industry_records (id) ON DELETE '
                 'RESTRICT, \n'
                 '\tFOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 []),
                ('srm_pos_checkout_payments',
                 '\n'
                 'CREATE TABLE srm_pos_checkout_payments (\n'
                 '\tid SERIAL NOT NULL, \n'
                 '\tcheckout_id INTEGER NOT NULL, \n'
                 '\tpayment_key VARCHAR(36) NOT NULL, \n'
                 '\treceipt_id INTEGER NOT NULL, \n'
                 '\trequest_sha256 VARCHAR(64) NOT NULL, \n'
                 '\torganization_id INTEGER NOT NULL, \n'
                 '\tbranch_id INTEGER NOT NULL, \n'
                 '\tscope_context_key INTEGER NOT NULL, \n'
                 "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                 '\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n'
                 '\tPRIMARY KEY (id), \n'
                 '\tCONSTRAINT fk_checkout_payment_checkout FOREIGN KEY(checkout_id, organization_id, '
                 'branch_id, scope_context_key) REFERENCES srm_pos_service_checkouts (id, organization_id, '
                 'branch_id, scope_context_key) ON DELETE RESTRICT, \n'
                 '\tCONSTRAINT uq_checkout_payment_key UNIQUE (checkout_id, payment_key), \n'
                 '\tCONSTRAINT ck_checkout_payment_identity CHECK (length(payment_key) = 36 AND '
                 'length(request_sha256) = 64 AND revision > 0), \n'
                 '\tUNIQUE (receipt_id), \n'
                 '\tFOREIGN KEY(receipt_id) REFERENCES srm_receipts (id) ON DELETE RESTRICT\n'
                 ')\n'
                 '\n',
                 [])]}

def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect not in _DDL:
        raise RuntimeError('Service checkout migration supports PostgreSQL and SQLite')
    existing = set(sa.inspect(bind).get_table_names())
    for name, ddl, indexes in _DDL[dialect]:
        if name not in existing:
            op.execute(sa.text(ddl))
            existing.add(name)
        present = {item['name'] for item in sa.inspect(bind).get_indexes(name)}
        for index_name, index_ddl in indexes:
            if index_name not in present:
                op.execute(sa.text(index_ddl))


def downgrade():
    # Issued checkout sources are financial history: retain additive tables.
    pass
