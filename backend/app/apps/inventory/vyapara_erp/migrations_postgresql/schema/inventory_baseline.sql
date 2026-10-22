-- Frozen Inventory/POS PostgreSQL schema, no data.

CREATE TABLE roles (
	id SERIAL NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	description VARCHAR(200), 
	is_system BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE permissions (
	id SERIAL NOT NULL, 
	module VARCHAR(50) NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	description VARCHAR(200), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_module_action UNIQUE (module, action)
);

CREATE TABLE categories (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	parent_id INTEGER, 
	description TEXT, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES categories (id)
);

CREATE TABLE brands (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE units (
	id SERIAL NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	short_name VARCHAR(20) NOT NULL, 
	decimal_allowed BOOLEAN, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE taxes (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	rate NUMERIC(5, 2) NOT NULL, 
	tax_type VARCHAR(20), 
	is_inclusive BOOLEAN, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE tax_groups (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE financial_years (
	id SERIAL NOT NULL, 
	name VARCHAR(20) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	is_current BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE account_groups (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	type VARCHAR(20) NOT NULL, 
	parent_id INTEGER, 
	description TEXT, 
	is_system BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES account_groups (id)
);

CREATE TABLE bank_accounts (
	id SERIAL NOT NULL, 
	account_name VARCHAR(100) NOT NULL, 
	account_type VARCHAR(20), 
	bank_name VARCHAR(100), 
	account_number VARCHAR(30), 
	ifsc_code VARCHAR(20), 
	opening_balance NUMERIC(12, 2), 
	current_balance NUMERIC(12, 2), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE cash_accounts (
	id SERIAL NOT NULL, 
	account_name VARCHAR(100) NOT NULL, 
	opening_balance NUMERIC(12, 2), 
	current_balance NUMERIC(12, 2), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE expense_categories (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE tds_sections (
	id SERIAL NOT NULL, 
	section_code VARCHAR(20) NOT NULL, 
	description VARCHAR(255), 
	default_rate NUMERIC(5, 2), 
	threshold_amount NUMERIC(12, 2), 
	is_active BOOLEAN, 
	PRIMARY KEY (id), 
	UNIQUE (section_code)
);

CREATE TABLE company_settings (
	id SERIAL NOT NULL, 
	company_name VARCHAR(200) NOT NULL, 
	business_type VARCHAR(100), 
	logo VARCHAR(255), 
	address TEXT, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	postal_code VARCHAR(20), 
	phone VARCHAR(30), 
	email VARCHAR(150), 
	website VARCHAR(150), 
	tax_number VARCHAR(50), 
	pan_number VARCHAR(20), 
	currency VARCHAR(10), 
	financial_year_start DATE, 
	invoice_prefix VARCHAR(10), 
	purchase_prefix VARCHAR(10), 
	quotation_prefix VARCHAR(10), 
	receipt_prefix VARCHAR(10), 
	payment_prefix VARCHAR(10), 
	sales_return_prefix VARCHAR(10), 
	purchase_return_prefix VARCHAR(10), 
	date_format VARCHAR(20), 
	decimal_places INTEGER, 
	tax_mode VARCHAR(20), 
	enable_negative_stock BOOLEAN, 
	enable_batch_tracking BOOLEAN, 
	enable_expiry_tracking BOOLEAN, 
	enable_barcode BOOLEAN, 
	default_invoice_terms TEXT, 
	stock_valuation_method VARCHAR(30), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE companies (
	id SERIAL NOT NULL, 
	legal_name VARCHAR(200) NOT NULL, 
	trade_name VARCHAR(200), 
	logo VARCHAR(255), 
	address TEXT, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	postal_code VARCHAR(20), 
	phone VARCHAR(30), 
	email VARCHAR(150), 
	website VARCHAR(150), 
	tax_number VARCHAR(50), 
	currency VARCHAR(10), 
	financial_year_start_month INTEGER, 
	invoice_prefix VARCHAR(10), 
	purchase_prefix VARCHAR(10), 
	quotation_prefix VARCHAR(10), 
	receipt_prefix VARCHAR(10), 
	payment_prefix VARCHAR(10), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE branches (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	address TEXT, 
	contact_person VARCHAR(100), 
	phone VARCHAR(30), 
	email VARCHAR(150), 
	tax_number VARCHAR(50), 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE TABLE app_settings (
	id SERIAL NOT NULL, 
	key VARCHAR(100) NOT NULL, 
	value TEXT, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (key)
);

CREATE TABLE print_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	template_type VARCHAR(50) NOT NULL, 
	module VARCHAR(50), 
	paper_size VARCHAR(20), 
	show_header BOOLEAN, 
	show_footer BOOLEAN, 
	show_logo BOOLEAN, 
	column_config TEXT, 
	terms_conditions TEXT, 
	html TEXT, 
	is_default BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE currencies (
	id SERIAL NOT NULL, 
	code VARCHAR(10) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	symbol VARCHAR(10), 
	exchange_rate NUMERIC(12, 6), 
	is_base BOOLEAN, 
	auto_update BOOLEAN, 
	last_updated TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE TABLE email_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	template_type VARCHAR(50) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	body TEXT NOT NULL, 
	placeholders TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE communication_logs (
	id SERIAL NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	recipient VARCHAR(180) NOT NULL, 
	subject VARCHAR(255), 
	body TEXT, 
	provider VARCHAR(80), 
	status VARCHAR(30), 
	reference_type VARCHAR(50), 
	reference_id INTEGER, 
	error_message TEXT, 
	sent_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE integration_settings (
	id SERIAL NOT NULL, 
	provider_type VARCHAR(50) NOT NULL, 
	provider_name VARCHAR(100) NOT NULL, 
	config_json TEXT, 
	is_active BOOLEAN, 
	test_mode BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE payment_gateways (
	id SERIAL NOT NULL, 
	provider VARCHAR(80) NOT NULL, 
	display_name VARCHAR(120) NOT NULL, 
	api_key_label VARCHAR(120), 
	config_json TEXT, 
	is_active BOOLEAN, 
	test_mode BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE shipping_providers (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	provider_code VARCHAR(50) NOT NULL, 
	config_json TEXT, 
	is_active BOOLEAN, 
	test_mode BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE webhook_subscriptions (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	target_url VARCHAR(500) NOT NULL, 
	events TEXT NOT NULL, 
	secret VARCHAR(120), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE incoming_webhook_logs (
	id SERIAL NOT NULL, 
	provider VARCHAR(80) NOT NULL, 
	event_type VARCHAR(80), 
	payload TEXT, 
	headers TEXT, 
	status VARCHAR(30), 
	error_message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE custom_fields (
	id SERIAL NOT NULL, 
	entity_type VARCHAR(50) NOT NULL, 
	field_key VARCHAR(80) NOT NULL, 
	label VARCHAR(120) NOT NULL, 
	field_type VARCHAR(30) NOT NULL, 
	options TEXT, 
	is_required BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE workflow_rules (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	trigger_event VARCHAR(80) NOT NULL, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE scheduled_jobs (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	job_type VARCHAR(80) NOT NULL, 
	frequency VARCHAR(20), 
	time_of_day VARCHAR(5), 
	config_json TEXT, 
	is_active BOOLEAN, 
	last_run_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE loyalty_settings (
	id SERIAL NOT NULL, 
	is_enabled BOOLEAN, 
	earn_points_per_amount NUMERIC(12, 2), 
	points_earned NUMERIC(12, 2), 
	redemption_value_per_point NUMERIC(12, 2), 
	points_expiry_days INTEGER, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE promotions (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	valid_from DATE, 
	valid_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE role_permissions (
	id SERIAL NOT NULL, 
	role_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	granted BOOLEAN, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role_id INTEGER NOT NULL, 
	is_active BOOLEAN, 
	phone VARCHAR(20), 
	profile_image VARCHAR(255), 
	totp_secret VARCHAR(32), 
	totp_enabled BOOLEAN, 
	backup_codes TEXT, 
	last_login TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
);

CREATE TABLE warehouses (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	branch_id INTEGER, 
	address TEXT, 
	contact_person VARCHAR(100), 
	phone VARCHAR(20), 
	email VARCHAR(150), 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);

CREATE TABLE tax_rates (
	id SERIAL NOT NULL, 
	tax_group_id INTEGER, 
	name VARCHAR(100) NOT NULL, 
	rate NUMERIC(5, 2), 
	tax_type VARCHAR(30), 
	treatment VARCHAR(30), 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tax_group_id) REFERENCES tax_groups (id)
);

CREATE TABLE price_lists (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	discount_pct NUMERIC(5, 2), 
	price_type VARCHAR(30), 
	customer_group VARCHAR(80), 
	branch_id INTEGER, 
	is_default BOOLEAN, 
	currency VARCHAR(10), 
	valid_from DATE, 
	valid_to DATE, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);

CREATE TABLE chart_of_accounts (
	id SERIAL NOT NULL, 
	account_code VARCHAR(20) NOT NULL, 
	account_name VARCHAR(150) NOT NULL, 
	account_group_id INTEGER NOT NULL, 
	description TEXT, 
	opening_balance NUMERIC(12, 2), 
	current_balance NUMERIC(12, 2), 
	is_system BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (account_code), 
	FOREIGN KEY(account_group_id) REFERENCES account_groups (id)
);

CREATE TABLE bank_statement_lines (
	id SERIAL NOT NULL, 
	bank_account_id INTEGER NOT NULL, 
	txn_date DATE NOT NULL, 
	description TEXT, 
	debit NUMERIC(12, 2), 
	credit NUMERIC(12, 2), 
	balance NUMERIC(12, 2), 
	reference_no VARCHAR(80), 
	matched_to_type VARCHAR(30), 
	matched_to_id INTEGER, 
	is_reconciled BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(bank_account_id) REFERENCES bank_accounts (id)
);

CREATE TABLE exchange_rate_logs (
	id SERIAL NOT NULL, 
	currency_id INTEGER NOT NULL, 
	rate NUMERIC(12, 6) NOT NULL, 
	fetched_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(currency_id) REFERENCES currencies (id)
);

CREATE TABLE shipments (
	id SERIAL NOT NULL, 
	provider_id INTEGER, 
	reference_type VARCHAR(50) NOT NULL, 
	reference_id INTEGER NOT NULL, 
	awb_no VARCHAR(120), 
	tracking_no VARCHAR(120), 
	status VARCHAR(40), 
	delivery_partner VARCHAR(120), 
	shipping_label TEXT, 
	tracking_url VARCHAR(500), 
	delivery_updates TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_id) REFERENCES shipping_providers (id)
);

CREATE TABLE webhook_logs (
	id SERIAL NOT NULL, 
	subscription_id INTEGER, 
	event VARCHAR(80) NOT NULL, 
	payload TEXT, 
	response_status INTEGER, 
	response_body TEXT, 
	status VARCHAR(30), 
	error_message TEXT, 
	delivered_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(subscription_id) REFERENCES webhook_subscriptions (id)
);

CREATE TABLE custom_field_values (
	id SERIAL NOT NULL, 
	field_id INTEGER NOT NULL, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	value TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(field_id) REFERENCES custom_fields (id)
);

CREATE TABLE workflow_conditions (
	id SERIAL NOT NULL, 
	workflow_id INTEGER NOT NULL, 
	field_name VARCHAR(100) NOT NULL, 
	operator VARCHAR(30) NOT NULL, 
	value VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES workflow_rules (id)
);

CREATE TABLE workflow_actions (
	id SERIAL NOT NULL, 
	workflow_id INTEGER NOT NULL, 
	action_type VARCHAR(80) NOT NULL, 
	config_json TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES workflow_rules (id)
);

CREATE TABLE scheduled_job_logs (
	id SERIAL NOT NULL, 
	job_id INTEGER, 
	status VARCHAR(30), 
	message TEXT, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES scheduled_jobs (id)
);

CREATE TABLE promotion_rules (
	id SERIAL NOT NULL, 
	promotion_id INTEGER NOT NULL, 
	rule_type VARCHAR(40) NOT NULL, 
	config_json TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(promotion_id) REFERENCES promotions (id)
);

CREATE TABLE customers (
	id SERIAL NOT NULL, 
	customer_code VARCHAR(20) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	business_name VARCHAR(200), 
	email VARCHAR(150), 
	phone VARCHAR(20), 
	alt_phone VARCHAR(20), 
	billing_address TEXT, 
	shipping_address TEXT, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	postal_code VARCHAR(20), 
	gst_number VARCHAR(20), 
	pan_number VARCHAR(20), 
	customer_type VARCHAR(20), 
	tags VARCHAR(255), 
	credit_limit NUMERIC(12, 2), 
	opening_balance NUMERIC(12, 2), 
	current_balance NUMERIC(12, 2), 
	payment_terms INTEGER, 
	price_list_id INTEGER, 
	status BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (customer_code), 
	FOREIGN KEY(price_list_id) REFERENCES price_lists (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE suppliers (
	id SERIAL NOT NULL, 
	supplier_code VARCHAR(20) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	business_name VARCHAR(200), 
	contact_person VARCHAR(120), 
	email VARCHAR(150), 
	phone VARCHAR(20), 
	alt_phone VARCHAR(20), 
	address TEXT, 
	billing_address TEXT, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	postal_code VARCHAR(20), 
	gst_number VARCHAR(20), 
	pan_number VARCHAR(20), 
	tax_treatment VARCHAR(30), 
	tags VARCHAR(255), 
	opening_balance NUMERIC(12, 2), 
	current_balance NUMERIC(12, 2), 
	payment_terms INTEGER, 
	tds_applicable BOOLEAN, 
	tds_section_id INTEGER, 
	status BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (supplier_code), 
	FOREIGN KEY(tds_section_id) REFERENCES tds_sections (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE stock_adjustments (
	id SERIAL NOT NULL, 
	adjustment_no VARCHAR(30) NOT NULL, 
	adjustment_date DATE NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	adjustment_type VARCHAR(30), 
	reason VARCHAR(100), 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (adjustment_no), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE stock_transfers (
	id SERIAL NOT NULL, 
	transfer_no VARCHAR(30) NOT NULL, 
	transfer_date DATE NOT NULL, 
	from_warehouse_id INTEGER NOT NULL, 
	to_warehouse_id INTEGER NOT NULL, 
	notes TEXT, 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (transfer_no), 
	FOREIGN KEY(from_warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(to_warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE repacking_transactions (
	id SERIAL NOT NULL, 
	repack_no VARCHAR(30) NOT NULL, 
	repack_date DATE NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	notes TEXT, 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (repack_no), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE journal_entries (
	id SERIAL NOT NULL, 
	entry_no VARCHAR(30) NOT NULL, 
	entry_date DATE NOT NULL, 
	reference_type VARCHAR(30), 
	reference_id INTEGER, 
	narration TEXT, 
	total_debit NUMERIC(12, 2), 
	total_credit NUMERIC(12, 2), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (entry_no), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE expenses (
	id SERIAL NOT NULL, 
	expense_no VARCHAR(30) NOT NULL, 
	expense_date DATE NOT NULL, 
	category_id INTEGER, 
	bank_account_id INTEGER, 
	amount NUMERIC(12, 2) NOT NULL, 
	tax_amount NUMERIC(12, 2), 
	vendor_name VARCHAR(150), 
	notes TEXT, 
	attachment VARCHAR(255), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (expense_no), 
	FOREIGN KEY(category_id) REFERENCES expense_categories (id), 
	FOREIGN KEY(bank_account_id) REFERENCES bank_accounts (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE tds_entries (
	id SERIAL NOT NULL, 
	entry_date DATE NOT NULL, 
	party_type VARCHAR(20) NOT NULL, 
	party_id INTEGER NOT NULL, 
	reference_type VARCHAR(30), 
	reference_id INTEGER, 
	reference_no VARCHAR(50), 
	section_id INTEGER NOT NULL, 
	base_amount NUMERIC(12, 2), 
	tds_rate NUMERIC(5, 2), 
	tds_amount NUMERIC(12, 2), 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES tds_sections (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE tcs_entries (
	id SERIAL NOT NULL, 
	entry_date DATE NOT NULL, 
	party_type VARCHAR(20) NOT NULL, 
	party_id INTEGER NOT NULL, 
	reference_type VARCHAR(30), 
	reference_id INTEGER, 
	reference_no VARCHAR(50), 
	section_id INTEGER NOT NULL, 
	base_amount NUMERIC(12, 2), 
	tds_rate NUMERIC(5, 2), 
	tds_amount NUMERIC(12, 2), 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES tds_sections (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE registers (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	branch_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	receipt_printer VARCHAR(150), 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(branch_id) REFERENCES branches (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id)
);

CREATE TABLE scheduled_reports (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	report_type VARCHAR(30) NOT NULL, 
	frequency VARCHAR(20), 
	day_of_week INTEGER, 
	day_of_month INTEGER, 
	time_of_day VARCHAR(5), 
	recipient_emails TEXT, 
	format VARCHAR(10), 
	is_active BOOLEAN, 
	last_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE api_tokens (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	token_hash VARCHAR(255) NOT NULL, 
	prefix VARCHAR(16) NOT NULL, 
	user_id INTEGER, 
	is_active BOOLEAN, 
	last_used_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE custom_views (
	id SERIAL NOT NULL, 
	entity_type VARCHAR(50) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	filters_json TEXT, 
	columns_json TEXT, 
	sort_json TEXT, 
	is_default BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE custom_modules (
	id SERIAL NOT NULL, 
	module_key VARCHAR(80) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	plural_name VARCHAR(140), 
	description TEXT, 
	icon VARCHAR(50), 
	show_in_sidebar BOOLEAN, 
	allow_import BOOLEAN, 
	allow_export BOOLEAN, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (module_key), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE audit_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(50) NOT NULL, 
	module VARCHAR(50) NOT NULL, 
	record_id INTEGER, 
	old_data JSON, 
	new_data JSON, 
	ip_address VARCHAR(45), 
	user_agent VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE attachments (
	id SERIAL NOT NULL, 
	module VARCHAR(50) NOT NULL, 
	record_id INTEGER NOT NULL, 
	file_path VARCHAR(255) NOT NULL, 
	original_name VARCHAR(255), 
	mime_type VARCHAR(100), 
	uploaded_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id)
);

CREATE TABLE products (
	id SERIAL NOT NULL, 
	sku VARCHAR(50) NOT NULL, 
	barcode VARCHAR(100), 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	category_id INTEGER, 
	brand_id INTEGER, 
	unit_id INTEGER, 
	tax_id INTEGER, 
	preferred_supplier_id INTEGER, 
	hsn_code VARCHAR(20), 
	purchase_price NUMERIC(12, 2), 
	sales_price NUMERIC(12, 2), 
	mrp NUMERIC(12, 2), 
	current_stock NUMERIC(12, 3), 
	average_cost NUMERIC(12, 4), 
	opening_stock NUMERIC(12, 3), 
	min_stock NUMERIC(12, 3), 
	max_stock NUMERIC(12, 3), 
	reorder_level NUMERIC(12, 3), 
	warehouse_id INTEGER, 
	rack_bin VARCHAR(50), 
	track_inventory BOOLEAN, 
	batch_tracking BOOLEAN, 
	serial_tracking BOOLEAN, 
	expiry_tracking BOOLEAN, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (sku), 
	FOREIGN KEY(category_id) REFERENCES categories (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id), 
	FOREIGN KEY(unit_id) REFERENCES units (id), 
	FOREIGN KEY(tax_id) REFERENCES taxes (id), 
	FOREIGN KEY(preferred_supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE purchases (
	id SERIAL NOT NULL, 
	purchase_no VARCHAR(30) NOT NULL, 
	purchase_date DATE NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	currency_id INTEGER, 
	exchange_rate_snapshot NUMERIC(12, 6), 
	original_currency_total NUMERIC(12, 2), 
	supplier_invoice_no VARCHAR(50), 
	supplier_invoice_date DATE, 
	due_date DATE, 
	status VARCHAR(20), 
	cancelled_at TIMESTAMP WITHOUT TIME ZONE, 
	cancellation_reason TEXT, 
	subtotal NUMERIC(12, 2), 
	discount_total NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	shipping_charges NUMERIC(12, 2), 
	other_charges NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	paid_amount NUMERIC(12, 2), 
	balance_amount NUMERIC(12, 2), 
	payment_status VARCHAR(20), 
	notes TEXT, 
	attachment VARCHAR(255), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (purchase_no), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(currency_id) REFERENCES currencies (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE purchase_orders (
	id SERIAL NOT NULL, 
	po_no VARCHAR(30) NOT NULL, 
	po_date DATE NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	expected_date DATE, 
	status VARCHAR(20), 
	subtotal NUMERIC(12, 2), 
	discount_total NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	notes TEXT, 
	terms TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (po_no), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE sales (
	id SERIAL NOT NULL, 
	invoice_no VARCHAR(30) NOT NULL, 
	invoice_date DATE NOT NULL, 
	customer_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	currency_id INTEGER, 
	exchange_rate_snapshot NUMERIC(12, 6), 
	original_currency_total NUMERIC(12, 2), 
	invoice_type VARCHAR(30), 
	sale_type VARCHAR(10), 
	status VARCHAR(20), 
	subtotal NUMERIC(12, 2), 
	discount_total NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	shipping_charges NUMERIC(12, 2), 
	round_off NUMERIC(5, 2), 
	grand_total NUMERIC(12, 2), 
	paid_amount NUMERIC(12, 2), 
	balance_amount NUMERIC(12, 2), 
	payment_status VARCHAR(20), 
	due_date DATE, 
	notes TEXT, 
	terms TEXT, 
	created_by INTEGER, 
	updated_by INTEGER, 
	issued_at TIMESTAMP WITHOUT TIME ZONE, 
	cancelled_at TIMESTAMP WITHOUT TIME ZONE, 
	cancellation_reason TEXT, 
	irn VARCHAR(64), 
	irn_ack_no VARCHAR(64), 
	irn_ack_dt TIMESTAMP WITHOUT TIME ZONE, 
	qr_code_data TEXT, 
	e_invoice_status VARCHAR(20), 
	razorpay_order_id VARCHAR(100), 
	razorpay_payment_id VARCHAR(100), 
	razorpay_signature VARCHAR(255), 
	razorpay_verified_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (invoice_no), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(currency_id) REFERENCES currencies (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

CREATE TABLE pos_sessions (
	id SERIAL NOT NULL, 
	session_no VARCHAR(30) NOT NULL, 
	opened_by INTEGER NOT NULL, 
	register_id INTEGER, 
	opened_at TIMESTAMP WITHOUT TIME ZONE, 
	closed_at TIMESTAMP WITHOUT TIME ZONE, 
	opening_cash NUMERIC(12, 2), 
	closing_cash NUMERIC(12, 2), 
	total_sales NUMERIC(12, 2), 
	total_cash NUMERIC(12, 2), 
	total_card NUMERIC(12, 2), 
	total_upi NUMERIC(12, 2), 
	total_wallet NUMERIC(12, 2), 
	total_credit NUMERIC(12, 2), 
	total_refunds NUMERIC(12, 2), 
	cash_withdrawals NUMERIC(12, 2), 
	expected_closing_cash NUMERIC(12, 2), 
	cash_difference NUMERIC(12, 2), 
	status VARCHAR(20), 
	PRIMARY KEY (id), 
	UNIQUE (session_no), 
	FOREIGN KEY(opened_by) REFERENCES users (id), 
	FOREIGN KEY(register_id) REFERENCES registers (id)
);

CREATE TABLE sales_orders (
	id SERIAL NOT NULL, 
	order_no VARCHAR(30) NOT NULL, 
	order_date DATE NOT NULL, 
	customer_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	expected_date DATE, 
	status VARCHAR(20), 
	subtotal NUMERIC(12, 2), 
	discount_total NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (order_no), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE recurring_invoices (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	customer_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	frequency VARCHAR(20), 
	interval_value INTEGER, 
	next_run_date DATE NOT NULL, 
	last_run_date DATE, 
	end_date DATE, 
	auto_send BOOLEAN, 
	auto_collect BOOLEAN, 
	status VARCHAR(20), 
	notes TEXT, 
	terms TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE quotations (
	id SERIAL NOT NULL, 
	quotation_no VARCHAR(30) NOT NULL, 
	quotation_date DATE NOT NULL, 
	valid_until DATE, 
	customer_id INTEGER NOT NULL, 
	subtotal NUMERIC(12, 2), 
	discount_total NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	notes TEXT, 
	terms TEXT, 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (quotation_no), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE proforma_invoices (
	id SERIAL NOT NULL, 
	proforma_no VARCHAR(30) NOT NULL, 
	proforma_date DATE NOT NULL, 
	customer_id INTEGER NOT NULL, 
	subtotal NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	notes TEXT, 
	terms TEXT, 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (proforma_no), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE delivery_challans (
	id SERIAL NOT NULL, 
	challan_no VARCHAR(30) NOT NULL, 
	challan_date DATE NOT NULL, 
	customer_id INTEGER NOT NULL, 
	delivery_address TEXT, 
	vehicle_no VARCHAR(20), 
	driver_name VARCHAR(100), 
	notes TEXT, 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (challan_no), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE journal_entry_lines (
	id SERIAL NOT NULL, 
	journal_entry_id INTEGER NOT NULL, 
	account_id INTEGER NOT NULL, 
	debit NUMERIC(12, 2), 
	credit NUMERIC(12, 2), 
	narration VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE, 
	FOREIGN KEY(account_id) REFERENCES chart_of_accounts (id)
);

CREATE TABLE customer_ledger (
	id SERIAL NOT NULL, 
	date DATE NOT NULL, 
	customer_id INTEGER NOT NULL, 
	reference_type VARCHAR(30), 
	reference_id INTEGER, 
	reference_no VARCHAR(30), 
	debit NUMERIC(12, 2), 
	credit NUMERIC(12, 2), 
	balance NUMERIC(12, 2), 
	narration VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE TABLE supplier_ledger (
	id SERIAL NOT NULL, 
	date DATE NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	reference_type VARCHAR(30), 
	reference_id INTEGER, 
	reference_no VARCHAR(30), 
	debit NUMERIC(12, 2), 
	credit NUMERIC(12, 2), 
	balance NUMERIC(12, 2), 
	narration VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);

CREATE TABLE custom_module_fields (
	id SERIAL NOT NULL, 
	module_id INTEGER NOT NULL, 
	field_key VARCHAR(80) NOT NULL, 
	label VARCHAR(120) NOT NULL, 
	field_type VARCHAR(30), 
	options TEXT, 
	is_required BOOLEAN, 
	show_in_list BOOLEAN, 
	sort_order INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_custom_module_field UNIQUE (module_id, field_key), 
	FOREIGN KEY(module_id) REFERENCES custom_modules (id) ON DELETE CASCADE
);

CREATE TABLE custom_module_records (
	id SERIAL NOT NULL, 
	module_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	data_json TEXT, 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(module_id) REFERENCES custom_modules (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE customer_loyalty_accounts (
	id SERIAL NOT NULL, 
	customer_id INTEGER NOT NULL, 
	points_balance NUMERIC(12, 2), 
	lifetime_points NUMERIC(12, 2), 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE TABLE product_images (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	image_path VARCHAR(255) NOT NULL, 
	is_primary BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);

CREATE TABLE product_variants (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	size VARCHAR(50), 
	color VARCHAR(50), 
	weight VARCHAR(50), 
	model VARCHAR(80), 
	packaging VARCHAR(80), 
	sku VARCHAR(50) NOT NULL, 
	barcode VARCHAR(100), 
	purchase_price NUMERIC(12, 2), 
	sales_price NUMERIC(12, 2), 
	mrp NUMERIC(12, 2), 
	current_stock NUMERIC(12, 3), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	UNIQUE (sku), 
	UNIQUE (barcode)
);

CREATE TABLE product_batches (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	batch_no VARCHAR(100) NOT NULL, 
	serial_no VARCHAR(100), 
	manufacture_date DATE, 
	expiry_date DATE, 
	quantity NUMERIC(12, 3), 
	cost_rate NUMERIC(12, 4), 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id)
);

CREATE TABLE batches (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	batch_no VARCHAR(100) NOT NULL, 
	manufacture_date DATE, 
	expiry_date DATE, 
	purchase_reference VARCHAR(50), 
	quantity NUMERIC(12, 3), 
	cost NUMERIC(12, 4), 
	status VARCHAR(20), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_batch_product_warehouse_no UNIQUE (product_id, warehouse_id, batch_no), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id)
);

CREATE TABLE price_list_items (
	id SERIAL NOT NULL, 
	price_list_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	sales_price NUMERIC(12, 2) NOT NULL, 
	min_qty NUMERIC(12, 3), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_price_list_item UNIQUE (price_list_id, product_id, min_qty), 
	FOREIGN KEY(price_list_id) REFERENCES price_lists (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE product_price_lists (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	branch_id INTEGER, 
	customer_group VARCHAR(80), 
	price_type VARCHAR(30), 
	price NUMERIC(12, 2) NOT NULL, 
	discount_pct NUMERIC(5, 2), 
	valid_from DATE, 
	valid_to DATE, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(branch_id) REFERENCES branches (id)
);

CREATE TABLE composite_items (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	description TEXT, 
	status BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE bill_of_materials (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	yield_qty NUMERIC(12, 3), 
	version VARCHAR(20), 
	is_active BOOLEAN, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE purchase_items (
	id SERIAL NOT NULL, 
	purchase_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	discount NUMERIC(5, 2), 
	discount_amount NUMERIC(12, 2), 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE purchase_returns (
	id SERIAL NOT NULL, 
	return_no VARCHAR(30) NOT NULL, 
	return_date DATE NOT NULL, 
	purchase_id INTEGER, 
	supplier_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	subtotal NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	reason TEXT, 
	refund_mode VARCHAR(20), 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (return_no), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE purchase_order_items (
	id SERIAL NOT NULL, 
	po_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	discount NUMERIC(5, 2), 
	discount_amount NUMERIC(12, 2), 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	received_qty NUMERIC(12, 3), 
	PRIMARY KEY (id), 
	FOREIGN KEY(po_id) REFERENCES purchase_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE goods_receipt_notes (
	id SERIAL NOT NULL, 
	grn_no VARCHAR(30) NOT NULL, 
	grn_date DATE NOT NULL, 
	po_id INTEGER, 
	supplier_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (grn_no), 
	FOREIGN KEY(po_id) REFERENCES purchase_orders (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE held_bills (
	id SERIAL NOT NULL, 
	hold_no VARCHAR(30) NOT NULL, 
	session_id INTEGER, 
	customer_id INTEGER, 
	warehouse_id INTEGER, 
	cart_json TEXT NOT NULL, 
	notes VARCHAR(255), 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (hold_no), 
	FOREIGN KEY(session_id) REFERENCES pos_sessions (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE sales_order_items (
	id SERIAL NOT NULL, 
	order_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	discount NUMERIC(5, 2), 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	fulfilled_qty NUMERIC(12, 3), 
	backorder_qty NUMERIC(12, 3), 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES sales_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE recurring_invoice_items (
	id SERIAL NOT NULL, 
	recurring_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	discount NUMERIC(5, 2), 
	tax_rate NUMERIC(5, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(recurring_id) REFERENCES recurring_invoices (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE sale_items (
	id SERIAL NOT NULL, 
	sale_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	discount NUMERIC(5, 2), 
	discount_amount NUMERIC(12, 2), 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	cost_price NUMERIC(12, 4), 
	PRIMARY KEY (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE eway_bills (
	id SERIAL NOT NULL, 
	sale_id INTEGER NOT NULL, 
	ewb_no VARCHAR(30) NOT NULL, 
	ewb_date TIMESTAMP WITHOUT TIME ZONE, 
	valid_upto TIMESTAMP WITHOUT TIME ZONE, 
	vehicle_no VARCHAR(30), 
	transporter_name VARCHAR(150), 
	transporter_id VARCHAR(30), 
	supply_type VARCHAR(20), 
	sub_type VARCHAR(20), 
	distance_km INTEGER, 
	status VARCHAR(20), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id) ON DELETE CASCADE, 
	UNIQUE (ewb_no)
);

CREATE TABLE sales_returns (
	id SERIAL NOT NULL, 
	return_no VARCHAR(30) NOT NULL, 
	return_date DATE NOT NULL, 
	sale_id INTEGER, 
	customer_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	subtotal NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	reason TEXT, 
	restock BOOLEAN, 
	status VARCHAR(20), 
	refund_mode VARCHAR(20), 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (return_no), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE quotation_items (
	id SERIAL NOT NULL, 
	quotation_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	discount NUMERIC(5, 2), 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(quotation_id) REFERENCES quotations (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE proforma_invoice_items (
	id SERIAL NOT NULL, 
	proforma_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(proforma_id) REFERENCES proforma_invoices (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE delivery_challan_items (
	id SERIAL NOT NULL, 
	challan_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	notes VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(challan_id) REFERENCES delivery_challans (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE delivery_bills (
	id SERIAL NOT NULL, 
	delivery_no VARCHAR(30) NOT NULL, 
	sale_id INTEGER, 
	sales_order_id INTEGER, 
	customer_id INTEGER NOT NULL, 
	delivery_status VARCHAR(30), 
	delivery_address TEXT, 
	delivery_person VARCHAR(120), 
	delivery_date DATE, 
	remarks TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (delivery_no), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(sales_order_id) REFERENCES sales_orders (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE picklists (
	id SERIAL NOT NULL, 
	picklist_no VARCHAR(30) NOT NULL, 
	sale_id INTEGER, 
	sales_order_id INTEGER, 
	warehouse_id INTEGER NOT NULL, 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (picklist_no), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(sales_order_id) REFERENCES sales_orders (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE credit_notes (
	id SERIAL NOT NULL, 
	cn_no VARCHAR(30) NOT NULL, 
	cn_date DATE NOT NULL, 
	customer_id INTEGER NOT NULL, 
	sale_id INTEGER, 
	reason TEXT, 
	adjustment_type VARCHAR(20), 
	subtotal NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	applied_amount NUMERIC(12, 2), 
	refunded_amount NUMERIC(12, 2), 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (cn_no), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE debit_notes (
	id SERIAL NOT NULL, 
	dn_no VARCHAR(30) NOT NULL, 
	dn_date DATE NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	purchase_id INTEGER, 
	reason TEXT, 
	adjustment_type VARCHAR(20), 
	subtotal NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (dn_no), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE inventory_ledger (
	id SERIAL NOT NULL, 
	date DATE NOT NULL, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	movement_type VARCHAR(30) NOT NULL, 
	reference_type VARCHAR(30), 
	reference_id INTEGER, 
	reference_no VARCHAR(30), 
	qty_in NUMERIC(12, 3), 
	qty_out NUMERIC(12, 3), 
	balance_qty NUMERIC(12, 3), 
	rate NUMERIC(12, 4), 
	value NUMERIC(12, 2), 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id)
);

CREATE TABLE stock_adjustment_items (
	id SERIAL NOT NULL, 
	adjustment_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	qty_in NUMERIC(12, 3), 
	qty_out NUMERIC(12, 3), 
	rate NUMERIC(12, 4), 
	notes VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(adjustment_id) REFERENCES stock_adjustments (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE stock_transfer_items (
	id SERIAL NOT NULL, 
	transfer_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4), 
	PRIMARY KEY (id), 
	FOREIGN KEY(transfer_id) REFERENCES stock_transfers (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE stock_openings (
	id SERIAL NOT NULL, 
	opening_no VARCHAR(30) NOT NULL, 
	opening_date DATE NOT NULL, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4), 
	value NUMERIC(12, 2), 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (opening_no), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE repacking_items (
	id SERIAL NOT NULL, 
	repacking_id INTEGER NOT NULL, 
	line_type VARCHAR(10) NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4), 
	PRIMARY KEY (id), 
	FOREIGN KEY(repacking_id) REFERENCES repacking_transactions (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE payments_received (
	id SERIAL NOT NULL, 
	receipt_no VARCHAR(30) NOT NULL, 
	receipt_date DATE NOT NULL, 
	customer_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	payment_mode VARCHAR(30), 
	bank_account_id INTEGER, 
	reference_no VARCHAR(50), 
	notes TEXT, 
	sale_id INTEGER, 
	unallocated_amount NUMERIC(12, 2), 
	status VARCHAR(20), 
	reversed_at TIMESTAMP WITHOUT TIME ZONE, 
	reversal_reason TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (receipt_no), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(bank_account_id) REFERENCES bank_accounts (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE cash_movements (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	movement_date TIMESTAMP WITHOUT TIME ZONE, 
	movement_type VARCHAR(20) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	reason VARCHAR(255), 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES pos_sessions (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE payments_made (
	id SERIAL NOT NULL, 
	voucher_no VARCHAR(30) NOT NULL, 
	voucher_date DATE NOT NULL, 
	payee_type VARCHAR(20), 
	supplier_id INTEGER, 
	expense_id INTEGER, 
	amount NUMERIC(12, 2) NOT NULL, 
	payment_mode VARCHAR(30), 
	bank_account_id INTEGER, 
	reference_no VARCHAR(50), 
	notes TEXT, 
	purchase_id INTEGER, 
	unallocated_amount NUMERIC(12, 2), 
	status VARCHAR(20), 
	reversed_at TIMESTAMP WITHOUT TIME ZONE, 
	reversal_reason TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (voucher_no), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(expense_id) REFERENCES expenses (id), 
	FOREIGN KEY(bank_account_id) REFERENCES bank_accounts (id), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE itc_entries (
	id SERIAL NOT NULL, 
	purchase_id INTEGER NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	invoice_no VARCHAR(50), 
	invoice_date DATE, 
	taxable_value NUMERIC(12, 2), 
	input_tax_cgst NUMERIC(12, 2), 
	input_tax_sgst NUMERIC(12, 2), 
	input_tax_igst NUMERIC(12, 2), 
	input_tax_vat NUMERIC(12, 2), 
	eligible_itc_amount NUMERIC(12, 2), 
	blocked_itc_amount NUMERIC(12, 2), 
	ineligible_reason VARCHAR(255), 
	itc_status VARCHAR(20), 
	claim_period VARCHAR(7), 
	reversal_reason VARCHAR(255), 
	remarks TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);

CREATE TABLE payment_links (
	id SERIAL NOT NULL, 
	sale_id INTEGER NOT NULL, 
	gateway_id INTEGER, 
	link_url VARCHAR(500), 
	provider_reference VARCHAR(120), 
	amount NUMERIC(12, 2), 
	currency VARCHAR(10), 
	status VARCHAR(30), 
	expires_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(gateway_id) REFERENCES payment_gateways (id)
);

CREATE TABLE ecommerce_orders (
	id SERIAL NOT NULL, 
	platform VARCHAR(80) NOT NULL, 
	external_order_id VARCHAR(120) NOT NULL, 
	customer_id INTEGER, 
	customer_payload TEXT, 
	stock_sync_status VARCHAR(30), 
	import_status VARCHAR(30), 
	invoice_id INTEGER, 
	order_date TIMESTAMP WITHOUT TIME ZONE, 
	total_amount NUMERIC(12, 2), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(invoice_id) REFERENCES sales (id)
);

CREATE TABLE loyalty_transactions (
	id SERIAL NOT NULL, 
	customer_id INTEGER NOT NULL, 
	sale_id INTEGER, 
	transaction_type VARCHAR(20) NOT NULL, 
	points NUMERIC(12, 2), 
	expiry_date DATE, 
	notes VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id)
);

CREATE TABLE coupons (
	id SERIAL NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	description VARCHAR(255), 
	discount_type VARCHAR(20), 
	discount_value NUMERIC(12, 2), 
	valid_from DATE, 
	valid_to DATE, 
	minimum_invoice_amount NUMERIC(12, 2), 
	customer_group VARCHAR(80), 
	product_id INTEGER, 
	category_id INTEGER, 
	max_usage INTEGER, 
	per_customer_usage_limit INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id)
);

CREATE TABLE serial_numbers (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	serial_no VARCHAR(100) NOT NULL, 
	status VARCHAR(20), 
	purchase_id INTEGER, 
	sale_id INTEGER, 
	batch_id INTEGER, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	UNIQUE (serial_no), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(batch_id) REFERENCES batches (id)
);

CREATE TABLE composite_item_components (
	id SERIAL NOT NULL, 
	composite_item_id INTEGER NOT NULL, 
	component_product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(composite_item_id) REFERENCES composite_items (id) ON DELETE CASCADE, 
	FOREIGN KEY(component_product_id) REFERENCES products (id)
);

CREATE TABLE bom_items (
	id SERIAL NOT NULL, 
	bom_id INTEGER NOT NULL, 
	component_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	unit_id INTEGER, 
	waste_pct NUMERIC(5, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(bom_id) REFERENCES bill_of_materials (id) ON DELETE CASCADE, 
	FOREIGN KEY(component_id) REFERENCES products (id), 
	FOREIGN KEY(unit_id) REFERENCES units (id)
);

CREATE TABLE manufacturing_orders (
	id SERIAL NOT NULL, 
	mo_no VARCHAR(30) NOT NULL, 
	bom_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	planned_qty NUMERIC(12, 3) NOT NULL, 
	produced_qty NUMERIC(12, 3), 
	planned_date DATE, 
	completed_date DATE, 
	status VARCHAR(20), 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (mo_no), 
	FOREIGN KEY(bom_id) REFERENCES bill_of_materials (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE purchase_return_items (
	id SERIAL NOT NULL, 
	purchase_return_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(purchase_return_id) REFERENCES purchase_returns (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE goods_receipt_items (
	id SERIAL NOT NULL, 
	grn_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	po_item_id INTEGER, 
	expected_qty NUMERIC(12, 3), 
	received_qty NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(grn_id) REFERENCES goods_receipt_notes (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(po_item_id) REFERENCES purchase_order_items (id)
);

CREATE TABLE vendor_credits (
	id SERIAL NOT NULL, 
	credit_no VARCHAR(30) NOT NULL, 
	credit_date DATE NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	purchase_id INTEGER, 
	purchase_return_id INTEGER, 
	reason TEXT, 
	subtotal NUMERIC(12, 2), 
	tax_total NUMERIC(12, 2), 
	grand_total NUMERIC(12, 2), 
	applied_amount NUMERIC(12, 2), 
	refunded_amount NUMERIC(12, 2), 
	status VARCHAR(20), 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (credit_no), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id), 
	FOREIGN KEY(purchase_return_id) REFERENCES purchase_returns (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE sales_return_items (
	id SERIAL NOT NULL, 
	sales_return_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sales_return_id) REFERENCES sales_returns (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE picklist_items (
	id SERIAL NOT NULL, 
	picklist_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	picked_qty NUMERIC(12, 3), 
	is_picked BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(picklist_id) REFERENCES picklists (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE packages (
	id SERIAL NOT NULL, 
	package_no VARCHAR(30) NOT NULL, 
	picklist_id INTEGER, 
	sale_id INTEGER, 
	customer_id INTEGER NOT NULL, 
	status VARCHAR(20), 
	weight NUMERIC(12, 3), 
	remarks TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (package_no), 
	FOREIGN KEY(picklist_id) REFERENCES picklists (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE credit_note_items (
	id SERIAL NOT NULL, 
	cn_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cn_id) REFERENCES credit_notes (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE debit_note_items (
	id SERIAL NOT NULL, 
	dn_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dn_id) REFERENCES debit_notes (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE payment_allocations (
	id SERIAL NOT NULL, 
	payment_id INTEGER NOT NULL, 
	sale_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(payment_id) REFERENCES payments_received (id) ON DELETE CASCADE, 
	FOREIGN KEY(sale_id) REFERENCES sales (id)
);

CREATE TABLE refunds (
	id SERIAL NOT NULL, 
	refund_no VARCHAR(30) NOT NULL, 
	refund_date DATE NOT NULL, 
	customer_id INTEGER NOT NULL, 
	credit_note_id INTEGER, 
	sale_return_id INTEGER, 
	amount NUMERIC(12, 2) NOT NULL, 
	refund_mode VARCHAR(30), 
	reference_no VARCHAR(50), 
	approval_status VARCHAR(20), 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (refund_no), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(credit_note_id) REFERENCES credit_notes (id), 
	FOREIGN KEY(sale_return_id) REFERENCES sales_returns (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE vendor_payment_allocations (
	id SERIAL NOT NULL, 
	payment_id INTEGER NOT NULL, 
	purchase_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(payment_id) REFERENCES payments_made (id) ON DELETE CASCADE, 
	FOREIGN KEY(purchase_id) REFERENCES purchases (id)
);

CREATE TABLE ecommerce_order_items (
	id SERIAL NOT NULL, 
	ecommerce_order_id INTEGER NOT NULL, 
	external_product_id VARCHAR(120), 
	product_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	sku VARCHAR(80), 
	quantity NUMERIC(12, 3), 
	rate NUMERIC(12, 2), 
	tax_rate NUMERIC(5, 2), 
	line_total NUMERIC(12, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(ecommerce_order_id) REFERENCES ecommerce_orders (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE coupon_redemptions (
	id SERIAL NOT NULL, 
	coupon_id INTEGER NOT NULL, 
	sale_id INTEGER NOT NULL, 
	customer_id INTEGER, 
	discount_amount NUMERIC(12, 2), 
	redeemed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(coupon_id) REFERENCES coupons (id), 
	FOREIGN KEY(sale_id) REFERENCES sales (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE TABLE vendor_credit_items (
	id SERIAL NOT NULL, 
	vendor_credit_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	rate NUMERIC(12, 4) NOT NULL, 
	tax_rate NUMERIC(5, 2), 
	tax_amount NUMERIC(12, 2), 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(vendor_credit_id) REFERENCES vendor_credits (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE package_items (
	id SERIAL NOT NULL, 
	package_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(package_id) REFERENCES packages (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);