-- Frozen schema-only PostgreSQL baseline. No source data.

CREATE TABLE permissions (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(255), 
	module VARCHAR(50), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_permissions_id ON permissions (id);

CREATE UNIQUE INDEX ix_permissions_name ON permissions (name);

CREATE TABLE roles (
	id SERIAL NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	description VARCHAR(255), 
	is_system BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_roles_id ON roles (id);

CREATE UNIQUE INDEX ix_roles_name ON roles (name);

CREATE TABLE password_policies (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	min_length INTEGER, 
	require_uppercase BOOLEAN, 
	require_lowercase BOOLEAN, 
	require_number BOOLEAN, 
	require_special BOOLEAN, 
	require_symbol BOOLEAN, 
	max_age_days INTEGER, 
	expiry_days INTEGER, 
	lockout_attempts INTEGER, 
	lockout_duration_minutes INTEGER, 
	lockout_minutes INTEGER, 
	mfa_required BOOLEAN, 
	is_default BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_password_policies_is_active ON password_policies (is_active);

CREATE INDEX ix_password_policies_id ON password_policies (id);

CREATE TABLE ip_access_policies (
	id SERIAL NOT NULL, 
	cidr VARCHAR(80) NOT NULL, 
	action VARCHAR(20) NOT NULL, 
	description VARCHAR(255), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_ip_access_policies_action ON ip_access_policies (action);

CREATE INDEX ix_ip_access_policies_cidr ON ip_access_policies (cidr);

CREATE INDEX ix_ip_access_policies_is_active ON ip_access_policies (is_active);

CREATE INDEX ix_ip_access_policies_id ON ip_access_policies (id);

CREATE TABLE companies (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	legal_name VARCHAR(200), 
	registration_number VARCHAR(100), 
	cin_number VARCHAR(30), 
	pan_number VARCHAR(20), 
	tan_number VARCHAR(20), 
	gstin VARCHAR(20), 
	website VARCHAR(200), 
	email VARCHAR(100), 
	phone VARCHAR(20), 
	address TEXT, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	pincode VARCHAR(20), 
	logo_url VARCHAR(500), 
	working_days_per_week INTEGER, 
	fiscal_year_start_month INTEGER, 
	default_timezone VARCHAR(80), 
	default_currency VARCHAR(10), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_companies_id ON companies (id);

CREATE INDEX ix_companies_name ON companies (name);

CREATE TABLE job_families (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_job_families_code ON job_families (code);

CREATE INDEX ix_job_families_is_active ON job_families (is_active);

CREATE INDEX ix_job_families_id ON job_families (id);

CREATE INDEX ix_job_families_name ON job_families (name);

CREATE TABLE communication_consents (
	id SERIAL NOT NULL, 
	email VARCHAR(180), 
	phone VARCHAR(60), 
	record_type VARCHAR(60), 
	record_id INTEGER, 
	consent_type VARCHAR(60), 
	status VARCHAR(40) NOT NULL, 
	source VARCHAR(120), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_communication_consent_subject UNIQUE (email, phone, record_type, record_id, consent_type)
);

CREATE INDEX ix_communication_consents_email ON communication_consents (email);

CREATE INDEX ix_communication_consents_phone ON communication_consents (phone);

CREATE INDEX ix_communication_consents_status ON communication_consents (status);

CREATE INDEX ix_communication_consents_id ON communication_consents (id);

CREATE INDEX ix_communication_consents_consent_type ON communication_consents (consent_type);

CREATE INDEX ix_communication_consents_updated_at ON communication_consents (updated_at);

CREATE INDEX ix_communication_consents_record_type ON communication_consents (record_type);

CREATE INDEX ix_communication_consents_record_id ON communication_consents (record_id);

CREATE TABLE communication_opt_outs (
	id SERIAL NOT NULL, 
	email VARCHAR(180) NOT NULL, 
	channel VARCHAR(40) NOT NULL, 
	reason TEXT, 
	source VARCHAR(120), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_communication_opt_out_email_channel UNIQUE (email, channel)
);

CREATE INDEX ix_communication_opt_outs_created_at ON communication_opt_outs (created_at);

CREATE INDEX ix_communication_opt_outs_channel ON communication_opt_outs (channel);

CREATE INDEX ix_communication_opt_outs_email ON communication_opt_outs (email);

CREATE INDEX ix_communication_opt_outs_id ON communication_opt_outs (id);

CREATE TABLE communication_delivery_logs (
	id SERIAL NOT NULL, 
	channel VARCHAR(40) NOT NULL, 
	related_message_id INTEGER, 
	provider VARCHAR(80) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	request_json JSON, 
	response_json JSON, 
	error_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_communication_delivery_logs_channel ON communication_delivery_logs (channel);

CREATE INDEX ix_communication_delivery_logs_related_message_id ON communication_delivery_logs (related_message_id);

CREATE INDEX ix_communication_delivery_logs_id ON communication_delivery_logs (id);

CREATE INDEX ix_communication_delivery_logs_created_at ON communication_delivery_logs (created_at);

CREATE INDEX ix_communication_delivery_logs_provider ON communication_delivery_logs (provider);

CREATE INDEX ix_communication_delivery_logs_status ON communication_delivery_logs (status);

CREATE TABLE admin_profiles (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_admin_profiles_active ON admin_profiles (active);

CREATE INDEX ix_admin_profiles_id ON admin_profiles (id);

CREATE UNIQUE INDEX ix_admin_profiles_name ON admin_profiles (name);

CREATE TABLE admin_record_sharing_rules (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	rule_name VARCHAR(160) NOT NULL, 
	condition_json JSON, 
	share_with_type VARCHAR(40) NOT NULL, 
	share_with_id INTEGER NOT NULL, 
	access_level VARCHAR(20), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_admin_record_sharing_rules_id ON admin_record_sharing_rules (id);

CREATE INDEX ix_admin_record_sharing_rules_access_level ON admin_record_sharing_rules (access_level);

CREATE INDEX ix_admin_record_sharing_rules_module_name ON admin_record_sharing_rules (module_name);

CREATE INDEX ix_admin_record_sharing_rules_share_with_id ON admin_record_sharing_rules (share_with_id);

CREATE INDEX ix_admin_record_sharing_rules_active ON admin_record_sharing_rules (active);

CREATE INDEX ix_admin_record_sharing_rules_share_with_type ON admin_record_sharing_rules (share_with_type);

CREATE TABLE admin_data_sharing_rules (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	rule_json JSON, 
	access_level VARCHAR(20), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_admin_data_sharing_rules_active ON admin_data_sharing_rules (active);

CREATE INDEX ix_admin_data_sharing_rules_module_name ON admin_data_sharing_rules (module_name);

CREATE INDEX ix_admin_data_sharing_rules_id ON admin_data_sharing_rules (id);

CREATE TABLE admin_ip_restrictions (
	id SERIAL NOT NULL, 
	cidr VARCHAR(80) NOT NULL, 
	action VARCHAR(20), 
	description VARCHAR(255), 
	active BOOLEAN, 
	environment_safe BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_admin_ip_restrictions_cidr ON admin_ip_restrictions (cidr);

CREATE INDEX ix_admin_ip_restrictions_action ON admin_ip_restrictions (action);

CREATE INDEX ix_admin_ip_restrictions_id ON admin_ip_restrictions (id);

CREATE INDEX ix_admin_ip_restrictions_active ON admin_ip_restrictions (active);

CREATE TABLE admin_duplicate_rules (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	match_fields_json JSON, 
	match_logic VARCHAR(40), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_admin_duplicate_rules_active ON admin_duplicate_rules (active);

CREATE INDEX ix_admin_duplicate_rules_id ON admin_duplicate_rules (id);

CREATE INDEX ix_admin_duplicate_rules_module_name ON admin_duplicate_rules (module_name);

CREATE TABLE admin_export_controls (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	max_rows INTEGER, 
	require_approval BOOLEAN, 
	watermark BOOLEAN, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_admin_export_controls_id ON admin_export_controls (id);

CREATE INDEX ix_admin_export_controls_module_name ON admin_export_controls (module_name);

CREATE INDEX ix_admin_export_controls_active ON admin_export_controls (active);

CREATE TABLE admin_compliance_settings (
	id SERIAL NOT NULL, 
	setting_key VARCHAR(120) NOT NULL, 
	setting_value_json JSON, 
	active BOOLEAN, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_admin_compliance_settings_id ON admin_compliance_settings (id);

CREATE UNIQUE INDEX ix_admin_compliance_settings_setting_key ON admin_compliance_settings (setting_key);

CREATE TABLE admin_data_retention_rules (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	retention_days INTEGER NOT NULL, 
	action VARCHAR(40), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_admin_data_retention_rules_id ON admin_data_retention_rules (id);

CREATE INDEX ix_admin_data_retention_rules_active ON admin_data_retention_rules (active);

CREATE INDEX ix_admin_data_retention_rules_module_name ON admin_data_retention_rules (module_name);

CREATE TABLE portal_roles (
	id SERIAL NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	portal_type VARCHAR(30) NOT NULL, 
	permissions_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_portal_roles_id ON portal_roles (id);

CREATE UNIQUE INDEX ix_portal_roles_name ON portal_roles (name);

CREATE INDEX ix_portal_roles_portal_type ON portal_roles (portal_type);

CREATE TABLE tenant_subscription_plans (
	id SERIAL NOT NULL, 
	code VARCHAR(60) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	features_json JSON, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_tenant_subscription_plans_id ON tenant_subscription_plans (id);

CREATE UNIQUE INDEX ix_tenant_subscription_plans_code ON tenant_subscription_plans (code);

CREATE INDEX ix_tenant_subscription_plans_active ON tenant_subscription_plans (active);

CREATE TABLE tenant_usage_metrics (
	id SERIAL NOT NULL, 
	metric_key VARCHAR(120) NOT NULL, 
	metric_value INTEGER, 
	period VARCHAR(30), 
	detail_json JSON, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_tenant_usage_metrics_period ON tenant_usage_metrics (period);

CREATE INDEX ix_tenant_usage_metrics_id ON tenant_usage_metrics (id);

CREATE INDEX ix_tenant_usage_metrics_metric_key ON tenant_usage_metrics (metric_key);

CREATE INDEX ix_tenant_usage_metrics_recorded_at ON tenant_usage_metrics (recorded_at);

CREATE TABLE bos_module_dependencies (
	id SERIAL NOT NULL, 
	module_key VARCHAR(80) NOT NULL, 
	depends_on_module_key VARCHAR(80) NOT NULL, 
	dependency_type VARCHAR(40) NOT NULL, 
	reason TEXT, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_bos_module_dependency UNIQUE (module_key, depends_on_module_key)
);

CREATE INDEX ix_bos_module_dependencies_id ON bos_module_dependencies (id);

CREATE INDEX ix_bos_module_dependencies_depends_on_module_key ON bos_module_dependencies (depends_on_module_key);

CREATE INDEX ix_bos_module_dependencies_module_key ON bos_module_dependencies (module_key);

CREATE TABLE shifts (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	code VARCHAR(20), 
	start_time TIME WITHOUT TIME ZONE NOT NULL, 
	end_time TIME WITHOUT TIME ZONE NOT NULL, 
	grace_minutes INTEGER, 
	working_hours NUMERIC(4, 2), 
	is_night_shift BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_shifts_id ON shifts (id);

CREATE TABLE holidays (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	holiday_date DATE NOT NULL, 
	holiday_type VARCHAR(30), 
	description TEXT, 
	applicable_branches VARCHAR(500), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_holidays_id ON holidays (id);

CREATE TABLE biometric_devices (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	vendor VARCHAR(80) NOT NULL, 
	device_code VARCHAR(80) NOT NULL, 
	location VARCHAR(150), 
	sync_mode VARCHAR(40), 
	last_sync_at TIMESTAMP WITH TIME ZONE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_biometric_devices_device_code ON biometric_devices (device_code);

CREATE INDEX ix_biometric_devices_is_active ON biometric_devices (is_active);

CREATE INDEX ix_biometric_devices_id ON biometric_devices (id);

CREATE TABLE geo_attendance_policies (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	latitude NUMERIC(10, 7) NOT NULL, 
	longitude NUMERIC(10, 7) NOT NULL, 
	radius_meters INTEGER, 
	require_selfie BOOLEAN, 
	require_qr BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_geo_attendance_policies_is_active ON geo_attendance_policies (is_active);

CREATE INDEX ix_geo_attendance_policies_id ON geo_attendance_policies (id);

CREATE TABLE leave_types (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	description TEXT, 
	days_allowed NUMERIC(5, 1) NOT NULL, 
	accrual_frequency VARCHAR(20) NOT NULL, 
	carry_forward BOOLEAN, 
	carry_forward_limit NUMERIC(5, 1), 
	encashable BOOLEAN, 
	applicable_gender VARCHAR(20), 
	applicable_from_months INTEGER, 
	half_day_allowed BOOLEAN, 
	is_active BOOLEAN, 
	color VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	CONSTRAINT ck_leave_type_accrual_frequency CHECK (accrual_frequency IN ('daily','weekly','monthly','quarterly','annual'))
);

CREATE INDEX ix_leave_types_id ON leave_types (id);

CREATE TABLE salary_component_categories (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	category_type VARCHAR(50) NOT NULL, 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	UNIQUE (code)
);

CREATE INDEX ix_salary_component_categories_is_active ON salary_component_categories (is_active);

CREATE INDEX ix_salary_component_categories_id ON salary_component_categories (id);

CREATE TABLE salary_structures (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	description TEXT, 
	version VARCHAR(20), 
	parent_structure_id INTEGER, 
	effective_from DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_structure_id) REFERENCES salary_structures (id) ON DELETE SET NULL
);

CREATE INDEX ix_salary_structures_id ON salary_structures (id);

CREATE TABLE tax_regimes (
	id SERIAL NOT NULL, 
	country VARCHAR(80), 
	financial_year VARCHAR(20) NOT NULL, 
	regime_code VARCHAR(40) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	is_default BOOLEAN, 
	rebate_rules_json JSON, 
	surcharge_rules_json JSON, 
	cess_percent NUMERIC(6, 2), 
	standard_deduction_amount NUMERIC(12, 2), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_tax_regimes_country ON tax_regimes (country);

CREATE INDEX ix_tax_regimes_id ON tax_regimes (id);

CREATE INDEX ix_tax_regimes_is_default ON tax_regimes (is_default);

CREATE INDEX ix_tax_regimes_financial_year ON tax_regimes (financial_year);

CREATE INDEX ix_tax_regimes_regime_code ON tax_regimes (regime_code);

CREATE INDEX ix_tax_regimes_is_active ON tax_regimes (is_active);

CREATE TABLE tax_sections (
	id SERIAL NOT NULL, 
	section_code VARCHAR(40) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	description TEXT, 
	proof_required BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (section_code)
);

CREATE INDEX ix_tax_sections_is_active ON tax_sections (is_active);

CREATE INDEX ix_tax_sections_id ON tax_sections (id);

CREATE TABLE pf_rules (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	wage_ceiling NUMERIC(12, 2), 
	employee_rate NUMERIC(6, 2), 
	employer_rate NUMERIC(6, 2), 
	eps_rate NUMERIC(6, 2), 
	edli_rate NUMERIC(6, 3), 
	admin_charge_rate NUMERIC(6, 3), 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	rounding_rule VARCHAR(50), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_pf_rules_id ON pf_rules (id);

CREATE INDEX ix_pf_rules_is_active ON pf_rules (is_active);

CREATE TABLE esi_rules (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	wage_threshold NUMERIC(12, 2), 
	employee_rate NUMERIC(6, 3), 
	employer_rate NUMERIC(6, 3), 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	rounding_rule VARCHAR(50), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_esi_rules_id ON esi_rules (id);

CREATE INDEX ix_esi_rules_is_active ON esi_rules (is_active);

CREATE TABLE professional_tax_slabs (
	id SERIAL NOT NULL, 
	state VARCHAR(100) NOT NULL, 
	salary_from NUMERIC(12, 2), 
	salary_to NUMERIC(12, 2), 
	employee_amount NUMERIC(12, 2), 
	month INTEGER, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_professional_tax_slabs_state ON professional_tax_slabs (state);

CREATE INDEX ix_professional_tax_slabs_id ON professional_tax_slabs (id);

CREATE INDEX ix_professional_tax_slabs_is_active ON professional_tax_slabs (is_active);

CREATE TABLE lwf_slabs (
	id SERIAL NOT NULL, 
	state VARCHAR(100) NOT NULL, 
	salary_from NUMERIC(12, 2), 
	salary_to NUMERIC(12, 2), 
	employee_amount NUMERIC(12, 2), 
	employer_amount NUMERIC(12, 2), 
	deduction_month INTEGER, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_lwf_slabs_is_active ON lwf_slabs (is_active);

CREATE INDEX ix_lwf_slabs_state ON lwf_slabs (state);

CREATE INDEX ix_lwf_slabs_id ON lwf_slabs (id);

CREATE TABLE gratuity_rules (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	days_per_year NUMERIC(6, 2), 
	wage_days_divisor NUMERIC(6, 2), 
	min_service_years NUMERIC(6, 2), 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	rounding_rule VARCHAR(50), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_gratuity_rules_id ON gratuity_rules (id);

CREATE INDEX ix_gratuity_rules_is_active ON gratuity_rules (is_active);

CREATE TABLE payroll_compliance_rules (
	id SERIAL NOT NULL, 
	state VARCHAR(80) NOT NULL, 
	rule_type VARCHAR(30) NOT NULL, 
	salary_from NUMERIC(12, 2), 
	salary_to NUMERIC(12, 2), 
	employee_amount NUMERIC(12, 2), 
	employer_amount NUMERIC(12, 2), 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_payroll_compliance_rules_id ON payroll_compliance_rules (id);

CREATE TABLE bank_advice_formats (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	bank_name VARCHAR(120) NOT NULL, 
	file_format VARCHAR(20), 
	delimiter VARCHAR(5), 
	include_header BOOLEAN, 
	column_order TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_bank_advice_formats_id ON bank_advice_formats (id);

CREATE TABLE accounting_ledgers (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	ledger_type VARCHAR(50) NOT NULL, 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE INDEX ix_accounting_ledgers_is_active ON accounting_ledgers (is_active);

CREATE INDEX ix_accounting_ledgers_id ON accounting_ledgers (id);

CREATE TABLE tax_declaration_cycles (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	proof_due_date DATE, 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_tax_declaration_cycles_id ON tax_declaration_cycles (id);

CREATE INDEX ix_tax_declaration_cycles_financial_year ON tax_declaration_cycles (financial_year);

CREATE TABLE tax_declaration_categories (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	financial_year VARCHAR(20) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	section VARCHAR(80) NOT NULL, 
	max_limit NUMERIC(14, 2), 
	requires_proof BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_tax_declaration_categories_code ON tax_declaration_categories (code);

CREATE INDEX ix_tax_declaration_categories_id ON tax_declaration_categories (id);

CREATE INDEX ix_tax_declaration_categories_financial_year ON tax_declaration_categories (financial_year);

CREATE INDEX ix_tax_declaration_categories_organization_id ON tax_declaration_categories (organization_id);

CREATE INDEX idx_tax_declaration_category_fy_code ON tax_declaration_categories (organization_id, financial_year, code);

CREATE TABLE review_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	template_type VARCHAR(40), 
	description TEXT, 
	rating_scale_min INTEGER, 
	rating_scale_max INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_review_templates_template_type ON review_templates (template_type);

CREATE INDEX ix_review_templates_is_active ON review_templates (is_active);

CREATE INDEX ix_review_templates_id ON review_templates (id);

CREATE TABLE competencies (
	id SERIAL NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	category VARCHAR(80), 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_competencies_is_active ON competencies (is_active);

CREATE UNIQUE INDEX ix_competencies_code ON competencies (code);

CREATE INDEX ix_competencies_id ON competencies (id);

CREATE INDEX ix_competencies_category ON competencies (category);

CREATE TABLE compensation_cycles (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	cycle_type VARCHAR(40), 
	financial_year VARCHAR(20) NOT NULL, 
	budget_amount NUMERIC(14, 2), 
	budget_percent NUMERIC(5, 2), 
	status VARCHAR(30), 
	starts_on DATE, 
	ends_on DATE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_compensation_cycles_status ON compensation_cycles (status);

CREATE INDEX ix_compensation_cycles_id ON compensation_cycles (id);

CREATE INDEX ix_compensation_cycles_financial_year ON compensation_cycles (financial_year);

CREATE TABLE helpdesk_categories (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	sla_hours INTEGER, 
	assigned_team VARCHAR(100), 
	is_active BOOLEAN, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_helpdesk_categories_id ON helpdesk_categories (id);

CREATE TABLE document_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	template_type VARCHAR(50), 
	description TEXT, 
	content TEXT, 
	variables TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_document_templates_id ON document_templates (id);

CREATE TABLE company_policies (
	id SERIAL NOT NULL, 
	title VARCHAR(300) NOT NULL, 
	category VARCHAR(100), 
	content TEXT, 
	document_url VARCHAR(500), 
	version VARCHAR(20), 
	effective_date TIMESTAMP WITH TIME ZONE, 
	is_published BOOLEAN, 
	require_acknowledgement BOOLEAN, 
	embedding_data TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_company_policies_id ON company_policies (id);

CREATE TABLE asset_categories (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_asset_categories_id ON asset_categories (id);

CREATE TABLE industry_targets (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	slug VARCHAR(120) NOT NULL, 
	headline VARCHAR(255) NOT NULL, 
	description TEXT, 
	icon VARCHAR(80), 
	color VARCHAR(40), 
	sort_order INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_industry_targets_name ON industry_targets (name);

CREATE UNIQUE INDEX ix_industry_targets_slug ON industry_targets (slug);

CREATE INDEX ix_industry_targets_id ON industry_targets (id);

CREATE TABLE feature_plans (
	id SERIAL NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	tagline VARCHAR(255), 
	strength TEXT, 
	sort_order INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_feature_plans_code ON feature_plans (code);

CREATE INDEX ix_feature_plans_id ON feature_plans (id);

CREATE TABLE custom_field_definitions (
	id SERIAL NOT NULL, 
	module VARCHAR(80) NOT NULL, 
	section VARCHAR(120), 
	field_key VARCHAR(120) NOT NULL, 
	label VARCHAR(150) NOT NULL, 
	field_type VARCHAR(40), 
	options_json JSON, 
	validation_json JSON, 
	is_required BOOLEAN, 
	is_sensitive BOOLEAN, 
	visible_to_roles VARCHAR(250), 
	editable_by_roles VARCHAR(250), 
	display_order INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_custom_field_definitions_is_active ON custom_field_definitions (is_active);

CREATE INDEX ix_custom_field_definitions_field_key ON custom_field_definitions (field_key);

CREATE INDEX ix_custom_field_definitions_module ON custom_field_definitions (module);

CREATE INDEX ix_custom_field_definitions_id ON custom_field_definitions (id);

CREATE TABLE data_retention_policies (
	id SERIAL NOT NULL, 
	module VARCHAR(80) NOT NULL, 
	record_type VARCHAR(100) NOT NULL, 
	retention_days INTEGER NOT NULL, 
	action VARCHAR(40), 
	legal_basis TEXT, 
	last_run_at TIMESTAMP WITH TIME ZONE, 
	last_run_summary_json JSON, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_data_retention_policies_id ON data_retention_policies (id);

CREATE INDEX ix_data_retention_policies_is_active ON data_retention_policies (is_active);

CREATE INDEX ix_data_retention_policies_module ON data_retention_policies (module);

CREATE TABLE metric_definitions (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	module VARCHAR(80) NOT NULL, 
	formula_json JSON, 
	owner_role VARCHAR(80), 
	refresh_frequency VARCHAR(50), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_metric_definitions_is_active ON metric_definitions (is_active);

CREATE INDEX ix_metric_definitions_id ON metric_definitions (id);

CREATE INDEX ix_metric_definitions_module ON metric_definitions (module);

CREATE UNIQUE INDEX ix_metric_definitions_code ON metric_definitions (code);

CREATE TABLE benefit_plans (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	plan_type VARCHAR(50) NOT NULL, 
	provider_name VARCHAR(150), 
	policy_number VARCHAR(100), 
	description TEXT, 
	employer_contribution NUMERIC(12, 2), 
	employee_contribution NUMERIC(12, 2), 
	taxable BOOLEAN, 
	payroll_component_code VARCHAR(50), 
	effective_from DATE, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_benefit_plans_is_active ON benefit_plans (is_active);

CREATE INDEX ix_benefit_plans_id ON benefit_plans (id);

CREATE INDEX ix_benefit_plans_plan_type ON benefit_plans (plan_type);

CREATE TABLE flexi_benefit_policies (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	component_code VARCHAR(50) NOT NULL, 
	monthly_limit NUMERIC(12, 2), 
	annual_limit NUMERIC(12, 2), 
	proof_required BOOLEAN, 
	taxable_if_unclaimed BOOLEAN, 
	carry_forward_allowed BOOLEAN, 
	effective_from DATE, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_flexi_benefit_policies_is_active ON flexi_benefit_policies (is_active);

CREATE INDEX ix_flexi_benefit_policies_id ON flexi_benefit_policies (id);

CREATE INDEX ix_flexi_benefit_policies_component_code ON flexi_benefit_policies (component_code);

CREATE TABLE esop_plans (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	plan_code VARCHAR(50) NOT NULL, 
	grant_currency VARCHAR(10), 
	exercise_price NUMERIC(12, 2), 
	vesting_frequency VARCHAR(30), 
	cliff_months INTEGER, 
	total_vesting_months INTEGER, 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_esop_plans_is_active ON esop_plans (is_active);

CREATE UNIQUE INDEX ix_esop_plans_plan_code ON esop_plans (plan_code);

CREATE INDEX ix_esop_plans_id ON esop_plans (id);

CREATE TABLE background_verification_vendors (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	contact_email VARCHAR(150), 
	provider_code VARCHAR(80), 
	api_base_url VARCHAR(500), 
	api_key_ref VARCHAR(200), 
	webhook_secret_ref VARCHAR(200), 
	supports_api_submission VARCHAR(10), 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE INDEX ix_background_verification_vendors_id ON background_verification_vendors (id);

CREATE INDEX ix_background_verification_vendors_status ON background_verification_vendors (status);

CREATE TABLE crm_tags (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(100) NOT NULL, 
	color VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_crm_tag_org_name UNIQUE (organization_id, name)
);

CREATE INDEX ix_crm_tags_organization_id ON crm_tags (organization_id);

CREATE INDEX ix_crm_tags_id ON crm_tags (id);

CREATE TABLE pms_clients (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	company_name VARCHAR(180), 
	email VARCHAR(150), 
	phone VARCHAR(40), 
	website VARCHAR(200), 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_pms_clients_organization_id ON pms_clients (organization_id);

CREATE INDEX ix_pms_clients_email ON pms_clients (email);

CREATE INDEX ix_pms_clients_name ON pms_clients (name);

CREATE INDEX ix_pms_clients_id ON pms_clients (id);

CREATE TABLE pms_workspaces (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_pms_workspaces_organization_id ON pms_workspaces (organization_id);

CREATE TABLE pms_tags (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(100) NOT NULL, 
	color VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pms_tag_org_name UNIQUE (organization_id, name)
);

CREATE INDEX ix_pms_tags_id ON pms_tags (id);

CREATE INDEX ix_pms_tags_organization_id ON pms_tags (organization_id);

CREATE TABLE srm_customer_aging (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	customer_id INTEGER NOT NULL, 
	current_amount NUMERIC(14, 2), 
	days_1_30 NUMERIC(14, 2), 
	days_31_60 NUMERIC(14, 2), 
	days_61_90 NUMERIC(14, 2), 
	days_90_plus NUMERIC(14, 2), 
	total_outstanding NUMERIC(14, 2), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_customer_aging_org_customer UNIQUE (organization_id, customer_id)
);

CREATE INDEX ix_srm_customer_aging_customer_id ON srm_customer_aging (customer_id);

CREATE INDEX ix_srm_customer_aging_organization_id ON srm_customer_aging (organization_id);

CREATE INDEX ix_srm_customer_aging_id ON srm_customer_aging (id);

CREATE TABLE fam_company_financial_settings (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	country_code VARCHAR(2) NOT NULL, 
	base_currency VARCHAR(3) NOT NULL, 
	gst_enabled BOOLEAN, 
	gstin VARCHAR(20), 
	legal_name VARCHAR(220), 
	trade_name VARCHAR(220), 
	pan VARCHAR(20), 
	tan VARCHAR(20), 
	cin VARCHAR(30), 
	registered_address TEXT, 
	state_code VARCHAR(4), 
	financial_year_start_month INTEGER, 
	books_start_date DATE, 
	decimal_places INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_company_settings UNIQUE (company_id)
);

CREATE INDEX ix_fam_company_financial_settings_company_id ON fam_company_financial_settings (company_id);

CREATE INDEX ix_fam_company_financial_settings_id ON fam_company_financial_settings (id);

CREATE TABLE fam_financial_years (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	status VARCHAR(20), 
	is_current BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_financial_year_company_name UNIQUE (company_id, name)
);

CREATE INDEX ix_fam_financial_years_id ON fam_financial_years (id);

CREATE INDEX ix_fam_financial_years_start_date ON fam_financial_years (start_date);

CREATE INDEX ix_fam_financial_years_status ON fam_financial_years (status);

CREATE INDEX ix_fam_financial_years_company_id ON fam_financial_years (company_id);

CREATE INDEX ix_fam_financial_years_name ON fam_financial_years (name);

CREATE INDEX ix_fam_financial_years_is_current ON fam_financial_years (is_current);

CREATE INDEX ix_fam_financial_years_end_date ON fam_financial_years (end_date);

CREATE TABLE fam_ledger_groups (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	parent_group_id INTEGER, 
	group_name VARCHAR(160) NOT NULL, 
	group_code VARCHAR(80) NOT NULL, 
	nature VARCHAR(20) NOT NULL, 
	system_group BOOLEAN, 
	affects_gross_profit BOOLEAN, 
	sequence_order INTEGER, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_ledger_group_company_code UNIQUE (company_id, group_code), 
	FOREIGN KEY(parent_group_id) REFERENCES fam_ledger_groups (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_ledger_groups_company_id ON fam_ledger_groups (company_id);

CREATE INDEX ix_fam_ledger_groups_group_name ON fam_ledger_groups (group_name);

CREATE INDEX ix_fam_ledger_groups_system_group ON fam_ledger_groups (system_group);

CREATE INDEX ix_fam_ledger_groups_id ON fam_ledger_groups (id);

CREATE INDEX ix_fam_ledger_groups_nature ON fam_ledger_groups (nature);

CREATE INDEX ix_fam_ledger_groups_active ON fam_ledger_groups (active);

CREATE INDEX ix_fam_ledger_groups_parent_group_id ON fam_ledger_groups (parent_group_id);

CREATE INDEX ix_fam_ledger_groups_group_code ON fam_ledger_groups (group_code);

CREATE TABLE fam_cost_centers (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	parent_id INTEGER, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES fam_cost_centers (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_cost_center_company_code UNIQUE (company_id, code)
);

CREATE INDEX ix_fam_cost_centers_name ON fam_cost_centers (name);

CREATE INDEX ix_fam_cost_centers_active ON fam_cost_centers (active);

CREATE INDEX ix_fam_cost_centers_id ON fam_cost_centers (id);

CREATE INDEX ix_fam_cost_centers_code ON fam_cost_centers (code);

CREATE INDEX ix_fam_cost_centers_company_id ON fam_cost_centers (company_id);

CREATE INDEX ix_fam_cost_centers_parent_id ON fam_cost_centers (parent_id);

CREATE TABLE fam_branches (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	branch_code VARCHAR(80) NOT NULL, 
	branch_name VARCHAR(180) NOT NULL, 
	gstin VARCHAR(20), 
	state_code VARCHAR(4), 
	address TEXT, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_branch_company_code UNIQUE (company_id, branch_code)
);

CREATE INDEX ix_fam_branches_active ON fam_branches (active);

CREATE INDEX ix_fam_branches_branch_name ON fam_branches (branch_name);

CREATE INDEX ix_fam_branches_branch_code ON fam_branches (branch_code);

CREATE INDEX ix_fam_branches_company_id ON fam_branches (company_id);

CREATE INDEX ix_fam_branches_id ON fam_branches (id);

CREATE TABLE fam_voucher_types (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	voucher_type_code VARCHAR(40) NOT NULL, 
	voucher_type_name VARCHAR(120) NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	numbering_prefix VARCHAR(30) NOT NULL, 
	numbering_sequence INTEGER NOT NULL, 
	auto_numbering BOOLEAN NOT NULL, 
	active BOOLEAN, 
	system_type BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_voucher_type_company_code UNIQUE (company_id, voucher_type_code)
);

CREATE INDEX ix_fam_voucher_types_company_id ON fam_voucher_types (company_id);

CREATE INDEX ix_fam_voucher_types_active ON fam_voucher_types (active);

CREATE INDEX ix_fam_voucher_types_voucher_type_code ON fam_voucher_types (voucher_type_code);

CREATE INDEX ix_fam_voucher_types_category ON fam_voucher_types (category);

CREATE INDEX ix_fam_voucher_types_id ON fam_voucher_types (id);

CREATE INDEX ix_fam_voucher_types_voucher_type_name ON fam_voucher_types (voucher_type_name);

CREATE INDEX ix_fam_voucher_types_system_type ON fam_voucher_types (system_type);

CREATE TABLE fam_srm_mapping (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	srm_record_type VARCHAR(40) NOT NULL, 
	srm_record_id INTEGER NOT NULL, 
	fam_record_type VARCHAR(40) NOT NULL, 
	fam_record_id INTEGER NOT NULL, 
	mapping_status VARCHAR(40), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_srm_mapping_source_target UNIQUE (company_id, srm_record_type, srm_record_id, fam_record_type)
);

CREATE INDEX ix_fam_srm_mapping_id ON fam_srm_mapping (id);

CREATE INDEX ix_fam_srm_mapping_fam_record_type ON fam_srm_mapping (fam_record_type);

CREATE INDEX ix_fam_srm_mapping_company_id ON fam_srm_mapping (company_id);

CREATE INDEX ix_fam_srm_mapping_srm_record_type ON fam_srm_mapping (srm_record_type);

CREATE INDEX ix_fam_srm_mapping_mapping_status ON fam_srm_mapping (mapping_status);

CREATE INDEX ix_fam_srm_mapping_srm_record_id ON fam_srm_mapping (srm_record_id);

CREATE INDEX ix_fam_srm_mapping_fam_record_id ON fam_srm_mapping (fam_record_id);

CREATE INDEX ix_fam_srm_mapping_created_at ON fam_srm_mapping (created_at);

CREATE TABLE fam_tax_registrations (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	gstin VARCHAR(20) NOT NULL, 
	legal_name VARCHAR(220) NOT NULL, 
	trade_name VARCHAR(220), 
	state_code VARCHAR(4) NOT NULL, 
	registration_type VARCHAR(40), 
	effective_from DATE NOT NULL, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_tax_registration_gstin UNIQUE (company_id, gstin)
);

CREATE INDEX ix_fam_tax_registrations_gstin ON fam_tax_registrations (gstin);

CREATE INDEX ix_fam_tax_registrations_effective_from ON fam_tax_registrations (effective_from);

CREATE INDEX ix_fam_tax_registrations_company_id ON fam_tax_registrations (company_id);

CREATE INDEX ix_fam_tax_registrations_state_code ON fam_tax_registrations (state_code);

CREATE INDEX ix_fam_tax_registrations_active ON fam_tax_registrations (active);

CREATE INDEX ix_fam_tax_registrations_id ON fam_tax_registrations (id);

CREATE INDEX ix_fam_tax_registrations_legal_name ON fam_tax_registrations (legal_name);

CREATE INDEX ix_fam_tax_registrations_registration_type ON fam_tax_registrations (registration_type);

CREATE INDEX ix_fam_tax_registrations_created_at ON fam_tax_registrations (created_at);

CREATE TABLE fam_gst_rates (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	rate_name VARCHAR(120) NOT NULL, 
	tax_type VARCHAR(30) NOT NULL, 
	cgst_rate NUMERIC(7, 3), 
	sgst_rate NUMERIC(7, 3), 
	igst_rate NUMERIC(7, 3), 
	cess_rate NUMERIC(7, 3), 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_fam_gst_rates_id ON fam_gst_rates (id);

CREATE INDEX ix_fam_gst_rates_effective_to ON fam_gst_rates (effective_to);

CREATE INDEX ix_fam_gst_rates_created_at ON fam_gst_rates (created_at);

CREATE INDEX ix_fam_gst_rates_rate_name ON fam_gst_rates (rate_name);

CREATE INDEX ix_fam_gst_rates_effective_from ON fam_gst_rates (effective_from);

CREATE INDEX ix_fam_gst_rates_company_id ON fam_gst_rates (company_id);

CREATE INDEX ix_fam_gst_rates_tax_type ON fam_gst_rates (tax_type);

CREATE INDEX ix_fam_gst_rates_active ON fam_gst_rates (active);

CREATE TABLE fam_einvoice_settings (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	provider_name VARCHAR(120), 
	api_base_url VARCHAR(300), 
	credentials_configured BOOLEAN, 
	applicable_from DATE, 
	applicability_json JSON, 
	active BOOLEAN, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_einvoice_settings_company UNIQUE (company_id)
);

CREATE INDEX ix_fam_einvoice_settings_credentials_configured ON fam_einvoice_settings (credentials_configured);

CREATE INDEX ix_fam_einvoice_settings_id ON fam_einvoice_settings (id);

CREATE INDEX ix_fam_einvoice_settings_active ON fam_einvoice_settings (active);

CREATE INDEX ix_fam_einvoice_settings_company_id ON fam_einvoice_settings (company_id);

CREATE TABLE fam_ewaybill_settings (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	provider_name VARCHAR(120), 
	api_base_url VARCHAR(300), 
	credentials_configured BOOLEAN, 
	threshold_amount NUMERIC(14, 2), 
	applicability_json JSON, 
	active BOOLEAN, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_ewaybill_settings_company UNIQUE (company_id)
);

CREATE INDEX ix_fam_ewaybill_settings_company_id ON fam_ewaybill_settings (company_id);

CREATE INDEX ix_fam_ewaybill_settings_active ON fam_ewaybill_settings (active);

CREATE INDEX ix_fam_ewaybill_settings_id ON fam_ewaybill_settings (id);

CREATE INDEX ix_fam_ewaybill_settings_credentials_configured ON fam_ewaybill_settings (credentials_configured);

CREATE TABLE fam_tds_sections (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	section_code VARCHAR(40) NOT NULL, 
	description TEXT NOT NULL, 
	default_rate NUMERIC(7, 3), 
	threshold_amount NUMERIC(14, 2), 
	effective_from DATE NOT NULL, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_tds_section_code UNIQUE (company_id, section_code)
);

CREATE INDEX ix_fam_tds_sections_company_id ON fam_tds_sections (company_id);

CREATE INDEX ix_fam_tds_sections_created_at ON fam_tds_sections (created_at);

CREATE INDEX ix_fam_tds_sections_id ON fam_tds_sections (id);

CREATE INDEX ix_fam_tds_sections_effective_from ON fam_tds_sections (effective_from);

CREATE INDEX ix_fam_tds_sections_active ON fam_tds_sections (active);

CREATE INDEX ix_fam_tds_sections_section_code ON fam_tds_sections (section_code);

CREATE TABLE fam_stock_groups (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	parent_group_id INTEGER, 
	group_code VARCHAR(80) NOT NULL, 
	group_name VARCHAR(180) NOT NULL, 
	description TEXT, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_group_id) REFERENCES fam_stock_groups (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_stock_group_company_code UNIQUE (company_id, group_code)
);

CREATE INDEX ix_fam_stock_groups_parent_group_id ON fam_stock_groups (parent_group_id);

CREATE INDEX ix_fam_stock_groups_group_name ON fam_stock_groups (group_name);

CREATE INDEX ix_fam_stock_groups_id ON fam_stock_groups (id);

CREATE INDEX ix_fam_stock_groups_group_code ON fam_stock_groups (group_code);

CREATE INDEX ix_fam_stock_groups_created_at ON fam_stock_groups (created_at);

CREATE INDEX ix_fam_stock_groups_company_id ON fam_stock_groups (company_id);

CREATE INDEX ix_fam_stock_groups_active ON fam_stock_groups (active);

CREATE TABLE fam_units_of_measure (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	unit_code VARCHAR(40) NOT NULL, 
	unit_name VARCHAR(120) NOT NULL, 
	symbol VARCHAR(20), 
	decimal_allowed BOOLEAN, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_uom_company_code UNIQUE (company_id, unit_code)
);

CREATE INDEX ix_fam_units_of_measure_active ON fam_units_of_measure (active);

CREATE INDEX ix_fam_units_of_measure_unit_code ON fam_units_of_measure (unit_code);

CREATE INDEX ix_fam_units_of_measure_unit_name ON fam_units_of_measure (unit_name);

CREATE INDEX ix_fam_units_of_measure_id ON fam_units_of_measure (id);

CREATE INDEX ix_fam_units_of_measure_company_id ON fam_units_of_measure (company_id);

CREATE INDEX ix_fam_units_of_measure_created_at ON fam_units_of_measure (created_at);

CREATE TABLE role_permissions (
	role_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	PRIMARY KEY (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE TABLE sso_providers (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	provider_type VARCHAR(20) NOT NULL, 
	is_active BOOLEAN, 
	is_default BOOLEAN, 
	button_label VARCHAR(100), 
	button_icon VARCHAR(50), 
	domain_hint VARCHAR(255), 
	client_id VARCHAR(500), 
	client_secret VARCHAR(500), 
	authorization_url VARCHAR(1000), 
	token_url VARCHAR(1000), 
	userinfo_url VARCHAR(1000), 
	scope VARCHAR(500), 
	redirect_uri VARCHAR(500), 
	idp_entity_id VARCHAR(500), 
	idp_sso_url VARCHAR(500), 
	idp_slo_url VARCHAR(500), 
	idp_x509_cert TEXT, 
	sp_entity_id VARCHAR(500), 
	sp_private_key TEXT, 
	sp_certificate TEXT, 
	attr_email VARCHAR(100), 
	attr_first_name VARCHAR(100), 
	attr_last_name VARCHAR(100), 
	attr_role VARCHAR(100), 
	auto_provision BOOLEAN, 
	default_role_id INTEGER, 
	force_mfa BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(default_role_id) REFERENCES roles (id)
);

CREATE TABLE admin_profile_permissions (
	id SERIAL NOT NULL, 
	profile_id INTEGER NOT NULL, 
	permission_name VARCHAR(120) NOT NULL, 
	allowed BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_admin_profile_permission UNIQUE (profile_id, permission_name), 
	FOREIGN KEY(profile_id) REFERENCES admin_profiles (id) ON DELETE CASCADE
);

CREATE INDEX ix_admin_profile_permissions_id ON admin_profile_permissions (id);

CREATE INDEX ix_admin_profile_permissions_profile_id ON admin_profile_permissions (profile_id);

CREATE INDEX ix_admin_profile_permissions_permission_name ON admin_profile_permissions (permission_name);

CREATE TABLE admin_roles (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	profile_id INTEGER, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(profile_id) REFERENCES admin_profiles (id) ON DELETE SET NULL
);

CREATE INDEX ix_admin_roles_active ON admin_roles (active);

CREATE INDEX ix_admin_roles_id ON admin_roles (id);

CREATE INDEX ix_admin_roles_profile_id ON admin_roles (profile_id);

CREATE UNIQUE INDEX ix_admin_roles_name ON admin_roles (name);

CREATE TABLE admin_field_security (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	field_name VARCHAR(120) NOT NULL, 
	profile_id INTEGER NOT NULL, 
	can_view BOOLEAN, 
	can_edit BOOLEAN, 
	mask_value BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_admin_field_security UNIQUE (module_name, field_name, profile_id), 
	FOREIGN KEY(profile_id) REFERENCES admin_profiles (id) ON DELETE CASCADE
);

CREATE INDEX ix_admin_field_security_profile_id ON admin_field_security (profile_id);

CREATE INDEX ix_admin_field_security_can_view ON admin_field_security (can_view);

CREATE INDEX ix_admin_field_security_id ON admin_field_security (id);

CREATE INDEX ix_admin_field_security_field_name ON admin_field_security (field_name);

CREATE INDEX ix_admin_field_security_module_name ON admin_field_security (module_name);

CREATE INDEX ix_admin_field_security_can_edit ON admin_field_security (can_edit);

CREATE TABLE admin_duplicate_candidates (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	rule_id INTEGER, 
	record_id INTEGER NOT NULL, 
	duplicate_record_id INTEGER NOT NULL, 
	confidence_score INTEGER, 
	status VARCHAR(30), 
	evidence_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(rule_id) REFERENCES admin_duplicate_rules (id) ON DELETE SET NULL
);

CREATE INDEX ix_admin_duplicate_candidates_id ON admin_duplicate_candidates (id);

CREATE INDEX ix_admin_duplicate_candidates_rule_id ON admin_duplicate_candidates (rule_id);

CREATE INDEX ix_admin_duplicate_candidates_status ON admin_duplicate_candidates (status);

CREATE INDEX ix_admin_duplicate_candidates_record_id ON admin_duplicate_candidates (record_id);

CREATE INDEX ix_admin_duplicate_candidates_duplicate_record_id ON admin_duplicate_candidates (duplicate_record_id);

CREATE INDEX ix_admin_duplicate_candidates_module_name ON admin_duplicate_candidates (module_name);

CREATE TABLE tenant_subscriptions (
	id SERIAL NOT NULL, 
	plan_id INTEGER, 
	edition VARCHAR(60), 
	status VARCHAR(30), 
	admin_override BOOLEAN, 
	started_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES tenant_subscription_plans (id) ON DELETE SET NULL
);

CREATE INDEX ix_tenant_subscriptions_plan_id ON tenant_subscriptions (plan_id);

CREATE INDEX ix_tenant_subscriptions_status ON tenant_subscriptions (status);

CREATE INDEX ix_tenant_subscriptions_edition ON tenant_subscriptions (edition);

CREATE INDEX ix_tenant_subscriptions_id ON tenant_subscriptions (id);

CREATE INDEX ix_tenant_subscriptions_started_at ON tenant_subscriptions (started_at);

CREATE TABLE bos_feature_flags (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	module_key VARCHAR(80) NOT NULL, 
	flag_key VARCHAR(120) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	value_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	CONSTRAINT uq_bos_feature_flag UNIQUE (company_id, module_key, flag_key)
);

CREATE INDEX ix_bos_feature_flags_flag_key ON bos_feature_flags (flag_key);

CREATE INDEX ix_bos_feature_flags_company_id ON bos_feature_flags (company_id);

CREATE INDEX ix_bos_feature_flags_module_key ON bos_feature_flags (module_key);

CREATE INDEX ix_bos_feature_flags_id ON bos_feature_flags (id);

CREATE TABLE bos_integration_rules (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	rule_key VARCHAR(120) NOT NULL, 
	source_module VARCHAR(80) NOT NULL, 
	target_module VARCHAR(80) NOT NULL, 
	event_name VARCHAR(120) NOT NULL, 
	action_name VARCHAR(120) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	skip_when_source_disabled BOOLEAN NOT NULL, 
	skip_when_target_disabled BOOLEAN NOT NULL, 
	config_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_bos_integration_rule UNIQUE (company_id, source_module, target_module, rule_key), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_bos_integration_rules_enabled ON bos_integration_rules (enabled);

CREATE INDEX ix_bos_integration_rules_rule_key ON bos_integration_rules (rule_key);

CREATE INDEX ix_bos_integration_rules_source_module ON bos_integration_rules (source_module);

CREATE INDEX ix_bos_integration_rules_company_id ON bos_integration_rules (company_id);

CREATE INDEX ix_bos_integration_rules_target_module ON bos_integration_rules (target_module);

CREATE INDEX ix_bos_integration_rules_id ON bos_integration_rules (id);

CREATE TABLE bos_entity_links (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	source_module VARCHAR(80) NOT NULL, 
	source_entity VARCHAR(120) NOT NULL, 
	source_entity_id VARCHAR(80) NOT NULL, 
	target_module VARCHAR(80) NOT NULL, 
	target_entity VARCHAR(120) NOT NULL, 
	target_entity_id VARCHAR(80) NOT NULL, 
	link_type VARCHAR(80) NOT NULL, 
	active BOOLEAN NOT NULL, 
	metadata_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_bos_entity_link UNIQUE (company_id, source_module, source_entity, source_entity_id, target_module, target_entity, target_entity_id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_bos_entity_links_source_module ON bos_entity_links (source_module);

CREATE INDEX ix_bos_entity_links_source_entity_id ON bos_entity_links (source_entity_id);

CREATE INDEX ix_bos_entity_links_active ON bos_entity_links (active);

CREATE INDEX ix_bos_entity_links_id ON bos_entity_links (id);

CREATE INDEX ix_bos_entity_links_source_entity ON bos_entity_links (source_entity);

CREATE INDEX ix_bos_entity_links_target_entity ON bos_entity_links (target_entity);

CREATE INDEX ix_bos_entity_links_company_id ON bos_entity_links (company_id);

CREATE INDEX ix_bos_entity_links_target_module ON bos_entity_links (target_module);

CREATE INDEX ix_bos_entity_links_target_entity_id ON bos_entity_links (target_entity_id);

CREATE TABLE bos_posting_rules (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	posting_key VARCHAR(120) NOT NULL, 
	source_module VARCHAR(80) NOT NULL, 
	target_module VARCHAR(80) NOT NULL, 
	transaction_type VARCHAR(120) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	requires_target_module BOOLEAN NOT NULL, 
	config_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	CONSTRAINT uq_bos_posting_rule UNIQUE (company_id, source_module, target_module, posting_key)
);

CREATE INDEX ix_bos_posting_rules_id ON bos_posting_rules (id);

CREATE INDEX ix_bos_posting_rules_posting_key ON bos_posting_rules (posting_key);

CREATE INDEX ix_bos_posting_rules_enabled ON bos_posting_rules (enabled);

CREATE INDEX ix_bos_posting_rules_company_id ON bos_posting_rules (company_id);

CREATE INDEX ix_bos_posting_rules_transaction_type ON bos_posting_rules (transaction_type);

CREATE INDEX ix_bos_posting_rules_source_module ON bos_posting_rules (source_module);

CREATE INDEX ix_bos_posting_rules_target_module ON bos_posting_rules (target_module);

CREATE TABLE shift_weekly_offs (
	id SERIAL NOT NULL, 
	shift_id INTEGER NOT NULL, 
	weekday INTEGER NOT NULL, 
	week_pattern VARCHAR(20), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(shift_id) REFERENCES shifts (id) ON DELETE CASCADE
);

CREATE INDEX ix_shift_weekly_offs_shift_id ON shift_weekly_offs (shift_id);

CREATE INDEX ix_shift_weekly_offs_id ON shift_weekly_offs (id);

CREATE TABLE salary_components (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	component_type VARCHAR(20) NOT NULL, 
	calculation_type VARCHAR(20), 
	amount NUMERIC(12, 2), 
	percentage_of VARCHAR(50), 
	formula_expression TEXT, 
	payslip_group VARCHAR(50), 
	display_sequence INTEGER, 
	is_taxable BOOLEAN, 
	is_pf_applicable BOOLEAN, 
	is_esi_applicable BOOLEAN, 
	description TEXT, 
	is_active BOOLEAN, 
	category_id INTEGER, 
	earning_type VARCHAR(50), 
	deduction_timing VARCHAR(50), 
	pay_frequency VARCHAR(30), 
	taxable_treatment VARCHAR(50), 
	exemption_section VARCHAR(50), 
	appears_in_ctc BOOLEAN, 
	appears_in_payslip BOOLEAN, 
	pro_rata_rule VARCHAR(50), 
	lop_applicable BOOLEAN, 
	pf_wage_flag BOOLEAN, 
	esi_wage_flag BOOLEAN, 
	gratuity_wage_flag BOOLEAN, 
	min_amount NUMERIC(12, 2), 
	max_amount NUMERIC(12, 2), 
	rounding_rule VARCHAR(50), 
	effective_from DATE, 
	effective_to DATE, 
	is_currency_fixed BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(category_id) REFERENCES salary_component_categories (id) ON DELETE SET NULL
);

CREATE INDEX ix_salary_components_id ON salary_components (id);

CREATE TABLE tax_slabs (
	id SERIAL NOT NULL, 
	tax_regime_id INTEGER NOT NULL, 
	min_income NUMERIC(14, 2), 
	max_income NUMERIC(14, 2), 
	rate_percent NUMERIC(6, 2), 
	fixed_amount NUMERIC(14, 2), 
	sequence INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tax_regime_id) REFERENCES tax_regimes (id) ON DELETE CASCADE
);

CREATE INDEX ix_tax_slabs_id ON tax_slabs (id);

CREATE INDEX ix_tax_slabs_tax_regime_id ON tax_slabs (tax_regime_id);

CREATE TABLE tax_section_limits (
	id SERIAL NOT NULL, 
	tax_section_id INTEGER NOT NULL, 
	tax_regime_id INTEGER, 
	financial_year VARCHAR(20) NOT NULL, 
	limit_amount NUMERIC(14, 2) NOT NULL, 
	effective_from DATE, 
	effective_to DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tax_regime_id) REFERENCES tax_regimes (id) ON DELETE CASCADE, 
	FOREIGN KEY(tax_section_id) REFERENCES tax_sections (id) ON DELETE CASCADE
);

CREATE INDEX ix_tax_section_limits_id ON tax_section_limits (id);

CREATE INDEX ix_tax_section_limits_tax_regime_id ON tax_section_limits (tax_regime_id);

CREATE INDEX ix_tax_section_limits_financial_year ON tax_section_limits (financial_year);

CREATE INDEX ix_tax_section_limits_tax_section_id ON tax_section_limits (tax_section_id);

CREATE TABLE review_template_questions (
	id SERIAL NOT NULL, 
	template_id INTEGER NOT NULL, 
	question_text TEXT NOT NULL, 
	question_type VARCHAR(30), 
	competency_code VARCHAR(80), 
	weightage NUMERIC(5, 2), 
	is_required BOOLEAN, 
	order_sequence INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(template_id) REFERENCES review_templates (id) ON DELETE CASCADE
);

CREATE INDEX ix_review_template_questions_template_id ON review_template_questions (template_id);

CREATE INDEX ix_review_template_questions_competency_code ON review_template_questions (competency_code);

CREATE INDEX ix_review_template_questions_id ON review_template_questions (id);

CREATE TABLE assets (
	id SERIAL NOT NULL, 
	asset_tag VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	category_id INTEGER, 
	brand VARCHAR(100), 
	model VARCHAR(100), 
	serial_number VARCHAR(100), 
	purchase_date DATE, 
	purchase_cost NUMERIC(12, 2), 
	warranty_expiry DATE, 
	condition VARCHAR(30), 
	status VARCHAR(30), 
	location VARCHAR(200), 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (serial_number), 
	FOREIGN KEY(category_id) REFERENCES asset_categories (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX ix_assets_asset_tag ON assets (asset_tag);

CREATE INDEX ix_assets_id ON assets (id);

CREATE TABLE feature_catalog (
	id SERIAL NOT NULL, 
	plan_id INTEGER, 
	module VARCHAR(120) NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	description TEXT, 
	is_highlight BOOLEAN, 
	sort_order INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES feature_plans (id) ON DELETE CASCADE
);

CREATE INDEX ix_feature_catalog_name ON feature_catalog (name);

CREATE INDEX ix_feature_catalog_id ON feature_catalog (id);

CREATE INDEX ix_feature_catalog_module ON feature_catalog (module);

CREATE TABLE payroll_legal_entities (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	legal_name VARCHAR(200) NOT NULL, 
	registered_address TEXT, 
	state VARCHAR(100), 
	city VARCHAR(100), 
	pincode VARCHAR(20), 
	pan VARCHAR(20), 
	tan VARCHAR(20), 
	cin VARCHAR(30), 
	gstin VARCHAR(30), 
	pf_establishment_code VARCHAR(50), 
	esi_employer_code VARCHAR(50), 
	pt_registration_number VARCHAR(80), 
	lwf_registration_number VARCHAR(80), 
	signatory_name VARCHAR(120), 
	signatory_designation VARCHAR(120), 
	logo_url VARCHAR(500), 
	is_default BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_legal_entities_id ON payroll_legal_entities (id);

CREATE INDEX ix_payroll_legal_entities_is_active ON payroll_legal_entities (is_active);

CREATE INDEX ix_payroll_legal_entities_company_id ON payroll_legal_entities (company_id);

CREATE INDEX ix_payroll_legal_entities_is_default ON payroll_legal_entities (is_default);

CREATE TABLE pms_workspace_invitations (
	id SERIAL NOT NULL, 
	workspace_id INTEGER NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (token_hash), 
	FOREIGN KEY(workspace_id) REFERENCES pms_workspaces (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_workspace_invitations_workspace_id ON pms_workspace_invitations (workspace_id);

CREATE INDEX ix_pms_workspace_invitations_email ON pms_workspace_invitations (email);

CREATE TABLE fam_accounting_periods (
	id SERIAL NOT NULL, 
	financial_year_id INTEGER NOT NULL, 
	period_name VARCHAR(80) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	status VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(financial_year_id) REFERENCES fam_financial_years (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_accounting_periods_status ON fam_accounting_periods (status);

CREATE INDEX ix_fam_accounting_periods_financial_year_id ON fam_accounting_periods (financial_year_id);

CREATE INDEX ix_fam_accounting_periods_id ON fam_accounting_periods (id);

CREATE TABLE fam_ledgers (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	ledger_code VARCHAR(80) NOT NULL, 
	ledger_name VARCHAR(180) NOT NULL, 
	ledger_group_id INTEGER NOT NULL, 
	nature VARCHAR(20) NOT NULL, 
	ledger_type VARCHAR(30), 
	gst_applicable BOOLEAN, 
	pan VARCHAR(20), 
	gstin VARCHAR(20), 
	state_code VARCHAR(4), 
	billing_address TEXT, 
	opening_balance_dr NUMERIC(14, 2), 
	opening_balance_cr NUMERIC(14, 2), 
	current_balance_dr NUMERIC(14, 2), 
	current_balance_cr NUMERIC(14, 2), 
	active BOOLEAN, 
	system_ledger BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_ledger_company_name UNIQUE (company_id, ledger_name), 
	CONSTRAINT uq_fam_ledger_company_code UNIQUE (company_id, ledger_code), 
	FOREIGN KEY(ledger_group_id) REFERENCES fam_ledger_groups (id) ON DELETE RESTRICT
);

CREATE INDEX ix_fam_ledgers_company_id ON fam_ledgers (company_id);

CREATE INDEX ix_fam_ledgers_nature ON fam_ledgers (nature);

CREATE INDEX ix_fam_ledgers_system_ledger ON fam_ledgers (system_ledger);

CREATE INDEX ix_fam_ledgers_id ON fam_ledgers (id);

CREATE INDEX ix_fam_ledgers_ledger_group_id ON fam_ledgers (ledger_group_id);

CREATE INDEX ix_fam_ledgers_ledger_type ON fam_ledgers (ledger_type);

CREATE INDEX ix_fam_ledgers_ledger_name ON fam_ledgers (ledger_name);

CREATE INDEX ix_fam_ledgers_ledger_code ON fam_ledgers (ledger_code);

CREATE INDEX ix_fam_ledgers_active ON fam_ledgers (active);

CREATE TABLE fam_hsn_sac_codes (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	description TEXT NOT NULL, 
	type VARCHAR(10) NOT NULL, 
	default_gst_rate_id INTEGER, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(default_gst_rate_id) REFERENCES fam_gst_rates (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_hsn_sac_code UNIQUE (company_id, code)
);

CREATE INDEX ix_fam_hsn_sac_codes_code ON fam_hsn_sac_codes (code);

CREATE INDEX ix_fam_hsn_sac_codes_default_gst_rate_id ON fam_hsn_sac_codes (default_gst_rate_id);

CREATE INDEX ix_fam_hsn_sac_codes_company_id ON fam_hsn_sac_codes (company_id);

CREATE INDEX ix_fam_hsn_sac_codes_type ON fam_hsn_sac_codes (type);

CREATE INDEX ix_fam_hsn_sac_codes_created_at ON fam_hsn_sac_codes (created_at);

CREATE INDEX ix_fam_hsn_sac_codes_id ON fam_hsn_sac_codes (id);

CREATE INDEX ix_fam_hsn_sac_codes_active ON fam_hsn_sac_codes (active);

CREATE TABLE fam_tds_rates (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	section_id INTEGER NOT NULL, 
	rate NUMERIC(7, 3), 
	threshold_amount NUMERIC(14, 2), 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES fam_tds_sections (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_tds_rates_company_id ON fam_tds_rates (company_id);

CREATE INDEX ix_fam_tds_rates_effective_from ON fam_tds_rates (effective_from);

CREATE INDEX ix_fam_tds_rates_active ON fam_tds_rates (active);

CREATE INDEX ix_fam_tds_rates_id ON fam_tds_rates (id);

CREATE INDEX ix_fam_tds_rates_effective_to ON fam_tds_rates (effective_to);

CREATE INDEX ix_fam_tds_rates_section_id ON fam_tds_rates (section_id);

CREATE TABLE fam_warehouses (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	warehouse_code VARCHAR(80) NOT NULL, 
	warehouse_name VARCHAR(180) NOT NULL, 
	branch_id INTEGER, 
	address TEXT, 
	contact_person VARCHAR(180), 
	phone VARCHAR(40), 
	email VARCHAR(180), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_warehouse_company_code UNIQUE (company_id, warehouse_code), 
	FOREIGN KEY(branch_id) REFERENCES fam_branches (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_warehouses_active ON fam_warehouses (active);

CREATE INDEX ix_fam_warehouses_warehouse_code ON fam_warehouses (warehouse_code);

CREATE INDEX ix_fam_warehouses_branch_id ON fam_warehouses (branch_id);

CREATE INDEX ix_fam_warehouses_company_id ON fam_warehouses (company_id);

CREATE INDEX ix_fam_warehouses_warehouse_name ON fam_warehouses (warehouse_name);

CREATE INDEX ix_fam_warehouses_created_at ON fam_warehouses (created_at);

CREATE INDEX ix_fam_warehouses_id ON fam_warehouses (id);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	hashed_password VARCHAR(255) NOT NULL, 
	is_active BOOLEAN, 
	is_superuser BOOLEAN, 
	role_id INTEGER, 
	last_login TIMESTAMP WITH TIME ZONE, 
	password_reset_token VARCHAR(255), 
	password_reset_expires TIMESTAMP WITH TIME ZONE, 
	mfa_enabled BOOLEAN, 
	mfa_enforced_at TIMESTAMP WITH TIME ZONE, 
	sso_provider_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE SET NULL, 
	FOREIGN KEY(sso_provider_id) REFERENCES sso_providers (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_users_id ON users (id);

CREATE TABLE admin_role_hierarchy (
	id SERIAL NOT NULL, 
	parent_role_id INTEGER NOT NULL, 
	child_role_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_role_id) REFERENCES admin_roles (id) ON DELETE CASCADE, 
	CONSTRAINT uq_admin_role_hierarchy UNIQUE (parent_role_id, child_role_id), 
	FOREIGN KEY(child_role_id) REFERENCES admin_roles (id) ON DELETE CASCADE
);

CREATE INDEX ix_admin_role_hierarchy_parent_role_id ON admin_role_hierarchy (parent_role_id);

CREATE INDEX ix_admin_role_hierarchy_child_role_id ON admin_role_hierarchy (child_role_id);

CREATE INDEX ix_admin_role_hierarchy_id ON admin_role_hierarchy (id);

CREATE TABLE salary_component_formula_rules (
	id SERIAL NOT NULL, 
	component_id INTEGER NOT NULL, 
	formula_expression TEXT NOT NULL, 
	dependency_order INTEGER, 
	formula_scope VARCHAR(40), 
	effective_from DATE, 
	effective_to DATE, 
	validation_status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES salary_components (id) ON DELETE CASCADE
);

CREATE INDEX ix_salary_component_formula_rules_component_id ON salary_component_formula_rules (component_id);

CREATE INDEX ix_salary_component_formula_rules_id ON salary_component_formula_rules (id);

CREATE INDEX ix_salary_component_formula_rules_validation_status ON salary_component_formula_rules (validation_status);

CREATE TABLE payroll_statutory_profiles (
	id SERIAL NOT NULL, 
	legal_entity_id INTEGER NOT NULL, 
	pf_establishment_code VARCHAR(50), 
	pf_signatory VARCHAR(120), 
	esi_employer_code VARCHAR(50), 
	pt_registration_number VARCHAR(80), 
	lwf_registration_number VARCHAR(80), 
	tan_circle VARCHAR(80), 
	tax_deductor_type VARCHAR(80), 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_statutory_profiles_legal_entity_id ON payroll_statutory_profiles (legal_entity_id);

CREATE INDEX ix_payroll_statutory_profiles_is_active ON payroll_statutory_profiles (is_active);

CREATE INDEX ix_payroll_statutory_profiles_id ON payroll_statutory_profiles (id);

CREATE TABLE salary_structure_components (
	id SERIAL NOT NULL, 
	structure_id INTEGER NOT NULL, 
	component_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2), 
	percentage NUMERIC(5, 2), 
	order_sequence INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES salary_components (id) ON DELETE CASCADE, 
	FOREIGN KEY(structure_id) REFERENCES salary_structures (id) ON DELETE CASCADE
);

CREATE INDEX ix_salary_structure_components_id ON salary_structure_components (id);

CREATE TABLE fam_parties (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	party_type VARCHAR(20) NOT NULL, 
	crm_account_id INTEGER, 
	crm_contact_id INTEGER, 
	ledger_id INTEGER, 
	party_code VARCHAR(80) NOT NULL, 
	legal_name VARCHAR(220) NOT NULL, 
	trade_name VARCHAR(220), 
	pan VARCHAR(20), 
	gstin VARCHAR(20), 
	registration_type VARCHAR(30), 
	state_code VARCHAR(4), 
	billing_address TEXT, 
	shipping_address TEXT, 
	email VARCHAR(180), 
	phone VARCHAR(60), 
	mobile VARCHAR(60), 
	payment_terms_days INTEGER, 
	credit_limit NUMERIC(14, 2), 
	opening_balance_dr NUMERIC(14, 2), 
	opening_balance_cr NUMERIC(14, 2), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_party_company_code UNIQUE (company_id, party_code), 
	FOREIGN KEY(ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_party_company_ledger UNIQUE (company_id, ledger_id)
);

CREATE INDEX ix_fam_parties_party_type ON fam_parties (party_type);

CREATE INDEX ix_fam_parties_crm_contact_id ON fam_parties (crm_contact_id);

CREATE INDEX ix_fam_parties_trade_name ON fam_parties (trade_name);

CREATE INDEX ix_fam_parties_crm_account_id ON fam_parties (crm_account_id);

CREATE INDEX ix_fam_parties_party_code ON fam_parties (party_code);

CREATE INDEX ix_fam_parties_registration_type ON fam_parties (registration_type);

CREATE INDEX ix_fam_parties_id ON fam_parties (id);

CREATE INDEX ix_fam_parties_ledger_id ON fam_parties (ledger_id);

CREATE INDEX ix_fam_parties_legal_name ON fam_parties (legal_name);

CREATE INDEX ix_fam_parties_active ON fam_parties (active);

CREATE INDEX ix_fam_parties_company_id ON fam_parties (company_id);

CREATE TABLE fam_posting_rules (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	source_module VARCHAR(40) NOT NULL, 
	transaction_type VARCHAR(80) NOT NULL, 
	debit_ledger_rule_json JSON, 
	credit_ledger_rule_json JSON, 
	tax_ledger_rule_json JSON, 
	roundoff_ledger_id INTEGER, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_posting_rule UNIQUE (company_id, source_module, transaction_type), 
	FOREIGN KEY(roundoff_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_posting_rules_transaction_type ON fam_posting_rules (transaction_type);

CREATE INDEX ix_fam_posting_rules_active ON fam_posting_rules (active);

CREATE INDEX ix_fam_posting_rules_id ON fam_posting_rules (id);

CREATE INDEX ix_fam_posting_rules_source_module ON fam_posting_rules (source_module);

CREATE INDEX ix_fam_posting_rules_created_at ON fam_posting_rules (created_at);

CREATE INDEX ix_fam_posting_rules_company_id ON fam_posting_rules (company_id);

CREATE INDEX ix_fam_posting_rules_roundoff_ledger_id ON fam_posting_rules (roundoff_ledger_id);

CREATE TABLE fam_bank_accounts (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	ledger_id INTEGER NOT NULL, 
	bank_name VARCHAR(180) NOT NULL, 
	branch_name VARCHAR(180), 
	account_number_masked VARCHAR(80) NOT NULL, 
	ifsc VARCHAR(20), 
	account_type VARCHAR(40), 
	opening_balance NUMERIC(14, 2), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_fam_bank_account_company_ledger UNIQUE (company_id, ledger_id)
);

CREATE INDEX ix_fam_bank_accounts_ifsc ON fam_bank_accounts (ifsc);

CREATE INDEX ix_fam_bank_accounts_account_type ON fam_bank_accounts (account_type);

CREATE INDEX ix_fam_bank_accounts_ledger_id ON fam_bank_accounts (ledger_id);

CREATE INDEX ix_fam_bank_accounts_bank_name ON fam_bank_accounts (bank_name);

CREATE INDEX ix_fam_bank_accounts_active ON fam_bank_accounts (active);

CREATE INDEX ix_fam_bank_accounts_company_id ON fam_bank_accounts (company_id);

CREATE INDEX ix_fam_bank_accounts_id ON fam_bank_accounts (id);

CREATE INDEX ix_fam_bank_accounts_account_number_masked ON fam_bank_accounts (account_number_masked);

CREATE INDEX ix_fam_bank_accounts_created_at ON fam_bank_accounts (created_at);

CREATE TABLE fam_payment_modes (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	type VARCHAR(30) NOT NULL, 
	default_ledger_id INTEGER, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_payment_mode_company_name UNIQUE (company_id, name), 
	FOREIGN KEY(default_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_payment_modes_company_id ON fam_payment_modes (company_id);

CREATE INDEX ix_fam_payment_modes_name ON fam_payment_modes (name);

CREATE INDEX ix_fam_payment_modes_default_ledger_id ON fam_payment_modes (default_ledger_id);

CREATE INDEX ix_fam_payment_modes_type ON fam_payment_modes (type);

CREATE INDEX ix_fam_payment_modes_created_at ON fam_payment_modes (created_at);

CREATE INDEX ix_fam_payment_modes_id ON fam_payment_modes (id);

CREATE INDEX ix_fam_payment_modes_active ON fam_payment_modes (active);

CREATE TABLE fam_cash_registers (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	ledger_id INTEGER NOT NULL, 
	register_name VARCHAR(160) NOT NULL, 
	location VARCHAR(160), 
	opening_balance NUMERIC(14, 2), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_fam_cash_register_company_ledger UNIQUE (company_id, ledger_id)
);

CREATE INDEX ix_fam_cash_registers_id ON fam_cash_registers (id);

CREATE INDEX ix_fam_cash_registers_register_name ON fam_cash_registers (register_name);

CREATE INDEX ix_fam_cash_registers_company_id ON fam_cash_registers (company_id);

CREATE INDEX ix_fam_cash_registers_created_at ON fam_cash_registers (created_at);

CREATE INDEX ix_fam_cash_registers_ledger_id ON fam_cash_registers (ledger_id);

CREATE INDEX ix_fam_cash_registers_active ON fam_cash_registers (active);

CREATE TABLE user_sessions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	session_token_hash VARCHAR(255) NOT NULL, 
	device_name VARCHAR(150), 
	ip_address VARCHAR(50), 
	user_agent TEXT, 
	trusted_device BOOLEAN, 
	status VARCHAR(30), 
	last_seen_at TIMESTAMP WITH TIME ZONE, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_sessions_id ON user_sessions (id);

CREATE INDEX ix_user_sessions_session_token_hash ON user_sessions (session_token_hash);

CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);

CREATE INDEX ix_user_sessions_status ON user_sessions (status);

CREATE TABLE mfa_methods (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	method_type VARCHAR(30) NOT NULL, 
	secret VARCHAR(255), 
	secret_ref VARCHAR(255), 
	phone_number VARCHAR(30), 
	email VARCHAR(120), 
	is_primary BOOLEAN, 
	is_verified BOOLEAN, 
	is_active BOOLEAN, 
	enabled_at TIMESTAMP WITH TIME ZONE, 
	last_used_at TIMESTAMP WITH TIME ZONE, 
	recovery_codes_json JSON, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	backup_email VARCHAR(255), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_mfa_methods_user_id ON mfa_methods (user_id);

CREATE INDEX ix_mfa_methods_id ON mfa_methods (id);

CREATE TABLE login_attempts (
	id SERIAL NOT NULL, 
	email VARCHAR(120), 
	user_id INTEGER, 
	ip_address VARCHAR(50), 
	user_agent TEXT, 
	status VARCHAR(30) NOT NULL, 
	success BOOLEAN, 
	failure_reason VARCHAR(255), 
	mfa_attempted BOOLEAN, 
	mfa_success BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_login_attempts_user_id ON login_attempts (user_id);

CREATE INDEX ix_login_attempts_id ON login_attempts (id);

CREATE INDEX ix_login_attempts_email ON login_attempts (email);

CREATE INDEX ix_login_attempts_status ON login_attempts (status);

CREATE TABLE branches (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(20), 
	company_id INTEGER NOT NULL, 
	organization_id INTEGER, 
	description TEXT, 
	address TEXT, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	pincode VARCHAR(20), 
	phone VARCHAR(20), 
	email VARCHAR(100), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_branches_organization_id ON branches (organization_id);

CREATE INDEX ix_branches_id ON branches (id);

CREATE INDEX ix_branches_name ON branches (name);

CREATE TABLE business_units (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	company_id INTEGER NOT NULL, 
	organization_id INTEGER, 
	parent_id INTEGER, 
	head_employee_id INTEGER, 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(parent_id) REFERENCES business_units (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_business_units_id ON business_units (id);

CREATE UNIQUE INDEX ix_business_units_code ON business_units (code);

CREATE INDEX ix_business_units_is_active ON business_units (is_active);

CREATE INDEX ix_business_units_name ON business_units (name);

CREATE INDEX ix_business_units_organization_id ON business_units (organization_id);

CREATE INDEX ix_business_units_company_id ON business_units (company_id);

CREATE TABLE grade_bands (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(120) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	description TEXT, 
	level INTEGER, 
	min_ctc NUMERIC(14, 2), 
	max_ctc NUMERIC(14, 2), 
	currency VARCHAR(10), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_grade_bands_id ON grade_bands (id);

CREATE INDEX ix_grade_bands_name ON grade_bands (name);

CREATE INDEX ix_grade_bands_is_active ON grade_bands (is_active);

CREATE INDEX ix_grade_bands_organization_id ON grade_bands (organization_id);

CREATE UNIQUE INDEX ix_grade_bands_code ON grade_bands (code);

CREATE TABLE common_people (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	user_id INTEGER, 
	primary_email VARCHAR(150), 
	phone_number VARCHAR(30), 
	first_name VARCHAR(80), 
	middle_name VARCHAR(80), 
	last_name VARCHAR(80), 
	display_name VARCHAR(180) NOT NULL, 
	status VARCHAR(30), 
	source_module VARCHAR(50), 
	source_record_type VARCHAR(80), 
	source_record_id INTEGER, 
	external_refs_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_common_people_org_status ON common_people (organization_id, status);

CREATE UNIQUE INDEX ix_common_people_primary_email ON common_people (primary_email);

CREATE INDEX ix_common_people_source_module ON common_people (source_module);

CREATE INDEX ix_common_people_id ON common_people (id);

CREATE UNIQUE INDEX ix_common_people_user_id ON common_people (user_id);

CREATE INDEX ix_common_people_display_name ON common_people (display_name);

CREATE INDEX ix_common_people_source_record_id ON common_people (source_record_id);

CREATE INDEX idx_common_people_source ON common_people (source_module, source_record_type, source_record_id);

CREATE INDEX ix_common_people_organization_id ON common_people (organization_id);

CREATE INDEX ix_common_people_status ON common_people (status);

CREATE TABLE audit_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	method VARCHAR(10) NOT NULL, 
	endpoint VARCHAR(500), 
	ip_address VARCHAR(50), 
	user_agent VARCHAR(500), 
	status_code INTEGER, 
	duration_ms INTEGER, 
	entity_type VARCHAR(100), 
	entity_id INTEGER, 
	action VARCHAR(50), 
	old_values TEXT, 
	new_values TEXT, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_logs_id ON audit_logs (id);

CREATE INDEX idx_audit_log_entity ON audit_logs (entity_type, entity_id, created_at);

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE TABLE approval_requests (
	id SERIAL NOT NULL, 
	source_module VARCHAR(80) NOT NULL, 
	approval_type VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	title VARCHAR(220) NOT NULL, 
	description TEXT, 
	requester_user_id INTEGER, 
	assigned_to_user_id INTEGER, 
	assigned_role VARCHAR(120), 
	delegated_to_user_id INTEGER, 
	delegated_role VARCHAR(120), 
	priority VARCHAR(30), 
	status VARCHAR(30), 
	sla_due_at TIMESTAMP WITH TIME ZONE, 
	escalated_at TIMESTAMP WITH TIME ZONE, 
	escalation_user_id INTEGER, 
	escalation_role VARCHAR(120), 
	ai_summary TEXT, 
	context_json JSON, 
	decision_reason TEXT, 
	decided_by INTEGER, 
	decided_at TIMESTAMP WITH TIME ZONE, 
	mobile_enabled BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(escalation_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_to_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(decided_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(delegated_to_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(requester_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_approval_requests_id ON approval_requests (id);

CREATE INDEX ix_approval_requests_approval_type ON approval_requests (approval_type);

CREATE INDEX ix_approval_requests_assigned_role ON approval_requests (assigned_role);

CREATE INDEX ix_approval_requests_sla_due_at ON approval_requests (sla_due_at);

CREATE INDEX ix_approval_requests_entity_id ON approval_requests (entity_id);

CREATE INDEX ix_approval_requests_requester_user_id ON approval_requests (requester_user_id);

CREATE INDEX ix_approval_requests_priority ON approval_requests (priority);

CREATE INDEX ix_approval_requests_mobile_enabled ON approval_requests (mobile_enabled);

CREATE INDEX ix_approval_requests_entity_type ON approval_requests (entity_type);

CREATE INDEX ix_approval_requests_source_module ON approval_requests (source_module);

CREATE INDEX ix_approval_requests_assigned_to_user_id ON approval_requests (assigned_to_user_id);

CREATE INDEX ix_approval_requests_status ON approval_requests (status);

CREATE INDEX ix_approval_requests_created_at ON approval_requests (created_at);

CREATE TABLE notifications (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	message TEXT NOT NULL, 
	module VARCHAR(50), 
	event_type VARCHAR(80), 
	related_entity_type VARCHAR(80), 
	related_entity_id INTEGER, 
	action_url VARCHAR(500), 
	priority VARCHAR(20), 
	channels JSON, 
	is_read BOOLEAN, 
	read_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_notifications_created_at ON notifications (created_at);

CREATE INDEX idx_notifications_company_user_unread ON notifications (company_id, user_id, is_read, created_at);

CREATE INDEX idx_notifications_user_unread ON notifications (user_id, is_read, created_at);

CREATE INDEX ix_notifications_company_id ON notifications (company_id);

CREATE INDEX ix_notifications_event_type ON notifications (event_type);

CREATE INDEX idx_notifications_company_module ON notifications (company_id, module, created_at);

CREATE INDEX ix_notifications_module ON notifications (module);

CREATE INDEX ix_notifications_is_read ON notifications (is_read);

CREATE INDEX ix_notifications_id ON notifications (id);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE sso_sessions (
	id SERIAL NOT NULL, 
	provider_id INTEGER, 
	state VARCHAR(100), 
	nonce VARCHAR(100), 
	relay_state VARCHAR(500), 
	code_verifier VARCHAR(200), 
	user_id INTEGER, 
	completed BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (state), 
	FOREIGN KEY(provider_id) REFERENCES sso_providers (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE workflow_definitions (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	module VARCHAR(80) NOT NULL, 
	trigger_event VARCHAR(120) NOT NULL, 
	description TEXT, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_workflow_definitions_trigger_event ON workflow_definitions (trigger_event);

CREATE INDEX ix_workflow_definitions_id ON workflow_definitions (id);

CREATE INDEX ix_workflow_definitions_module ON workflow_definitions (module);

CREATE INDEX ix_workflow_definitions_is_active ON workflow_definitions (is_active);

CREATE TABLE workflow_delegations (
	id SERIAL NOT NULL, 
	delegator_user_id INTEGER, 
	delegator_role VARCHAR(120), 
	delegate_to_user_id INTEGER, 
	delegate_to_role VARCHAR(120), 
	module VARCHAR(80), 
	reason TEXT, 
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(delegate_to_user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(delegator_user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_workflow_delegations_is_active ON workflow_delegations (is_active);

CREATE INDEX ix_workflow_delegations_delegator_user_id ON workflow_delegations (delegator_user_id);

CREATE INDEX ix_workflow_delegations_module ON workflow_delegations (module);

CREATE INDEX ix_workflow_delegations_id ON workflow_delegations (id);

CREATE INDEX ix_workflow_delegations_delegator_role ON workflow_delegations (delegator_role);

CREATE INDEX ix_workflow_delegations_delegate_to_role ON workflow_delegations (delegate_to_role);

CREATE INDEX ix_workflow_delegations_delegate_to_user_id ON workflow_delegations (delegate_to_user_id);

CREATE TABLE automation_workflows (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	description TEXT, 
	module_name VARCHAR(60) NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	trigger_type VARCHAR(80) NOT NULL, 
	is_active BOOLEAN, 
	max_execution_depth INTEGER, 
	created_by INTEGER, 
	updated_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_workflows_organization_id ON automation_workflows (organization_id);

CREATE INDEX ix_automation_workflows_trigger_type ON automation_workflows (trigger_type);

CREATE INDEX ix_automation_workflows_created_by ON automation_workflows (created_by);

CREATE INDEX ix_automation_workflows_name ON automation_workflows (name);

CREATE INDEX ix_automation_workflows_record_type ON automation_workflows (record_type);

CREATE INDEX ix_automation_workflows_created_at ON automation_workflows (created_at);

CREATE INDEX ix_automation_workflows_id ON automation_workflows (id);

CREATE INDEX ix_automation_workflows_module_name ON automation_workflows (module_name);

CREATE INDEX ix_automation_workflows_is_active ON automation_workflows (is_active);

CREATE TABLE automation_blueprints (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	module_name VARCHAR(60) NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_blueprints_name ON automation_blueprints (name);

CREATE INDEX ix_automation_blueprints_record_type ON automation_blueprints (record_type);

CREATE INDEX ix_automation_blueprints_organization_id ON automation_blueprints (organization_id);

CREATE INDEX ix_automation_blueprints_module_name ON automation_blueprints (module_name);

CREATE INDEX ix_automation_blueprints_created_at ON automation_blueprints (created_at);

CREATE INDEX ix_automation_blueprints_id ON automation_blueprints (id);

CREATE INDEX ix_automation_blueprints_is_active ON automation_blueprints (is_active);

CREATE TABLE automation_approval_rules (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	module_name VARCHAR(60) NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	condition_json JSON, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_approval_rules_name ON automation_approval_rules (name);

CREATE INDEX ix_automation_approval_rules_module_name ON automation_approval_rules (module_name);

CREATE INDEX ix_automation_approval_rules_organization_id ON automation_approval_rules (organization_id);

CREATE INDEX ix_automation_approval_rules_id ON automation_approval_rules (id);

CREATE INDEX ix_automation_approval_rules_record_type ON automation_approval_rules (record_type);

CREATE INDEX ix_automation_approval_rules_is_active ON automation_approval_rules (is_active);

CREATE INDEX ix_automation_approval_rules_created_at ON automation_approval_rules (created_at);

CREATE TABLE automation_assignment_rules (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	module_name VARCHAR(60) NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	condition_json JSON, 
	assignment_json JSON NOT NULL, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_assignment_rules_is_active ON automation_assignment_rules (is_active);

CREATE INDEX ix_automation_assignment_rules_created_at ON automation_assignment_rules (created_at);

CREATE INDEX ix_automation_assignment_rules_name ON automation_assignment_rules (name);

CREATE INDEX ix_automation_assignment_rules_record_type ON automation_assignment_rules (record_type);

CREATE INDEX ix_automation_assignment_rules_organization_id ON automation_assignment_rules (organization_id);

CREATE INDEX ix_automation_assignment_rules_module_name ON automation_assignment_rules (module_name);

CREATE INDEX ix_automation_assignment_rules_id ON automation_assignment_rules (id);

CREATE TABLE automation_cadences (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	module_name VARCHAR(60) NOT NULL, 
	target_type VARCHAR(80) NOT NULL, 
	stop_rules_json JSON, 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_cadences_module_name ON automation_cadences (module_name);

CREATE INDEX ix_automation_cadences_target_type ON automation_cadences (target_type);

CREATE INDEX ix_automation_cadences_organization_id ON automation_cadences (organization_id);

CREATE INDEX ix_automation_cadences_name ON automation_cadences (name);

CREATE INDEX ix_automation_cadences_created_at ON automation_cadences (created_at);

CREATE INDEX ix_automation_cadences_id ON automation_cadences (id);

CREATE INDEX ix_automation_cadences_status ON automation_cadences (status);

CREATE TABLE automation_webhook_endpoints (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	target_url VARCHAR(500) NOT NULL, 
	event_types_json JSON, 
	secret_ref VARCHAR(180), 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_webhook_endpoints_name ON automation_webhook_endpoints (name);

CREATE INDEX ix_automation_webhook_endpoints_id ON automation_webhook_endpoints (id);

CREATE INDEX ix_automation_webhook_endpoints_organization_id ON automation_webhook_endpoints (organization_id);

CREATE INDEX ix_automation_webhook_endpoints_created_at ON automation_webhook_endpoints (created_at);

CREATE INDEX ix_automation_webhook_endpoints_is_active ON automation_webhook_endpoints (is_active);

CREATE TABLE automation_scheduled_jobs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	job_type VARCHAR(80) NOT NULL, 
	module_name VARCHAR(60) NOT NULL, 
	record_type VARCHAR(80), 
	record_id INTEGER, 
	status VARCHAR(30), 
	run_at TIMESTAMP WITH TIME ZONE, 
	payload_json JSON, 
	attempts INTEGER, 
	last_error TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_scheduled_jobs_id ON automation_scheduled_jobs (id);

CREATE INDEX ix_automation_scheduled_jobs_record_id ON automation_scheduled_jobs (record_id);

CREATE INDEX ix_automation_scheduled_jobs_run_at ON automation_scheduled_jobs (run_at);

CREATE INDEX ix_automation_scheduled_jobs_organization_id ON automation_scheduled_jobs (organization_id);

CREATE INDEX ix_automation_scheduled_jobs_module_name ON automation_scheduled_jobs (module_name);

CREATE INDEX ix_automation_scheduled_jobs_record_type ON automation_scheduled_jobs (record_type);

CREATE INDEX ix_automation_scheduled_jobs_created_at ON automation_scheduled_jobs (created_at);

CREATE INDEX ix_automation_scheduled_jobs_job_type ON automation_scheduled_jobs (job_type);

CREATE INDEX ix_automation_scheduled_jobs_status ON automation_scheduled_jobs (status);

CREATE TABLE customization_modules (
	id SERIAL NOT NULL, 
	module_api_name VARCHAR(100) NOT NULL, 
	module_label VARCHAR(160) NOT NULL, 
	plural_label VARCHAR(160) NOT NULL, 
	icon VARCHAR(80), 
	description TEXT, 
	enabled BOOLEAN, 
	owner_field_enabled BOOLEAN, 
	timeline_enabled BOOLEAN, 
	activities_enabled BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_customization_module_api_name UNIQUE (module_api_name), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_modules_module_api_name ON customization_modules (module_api_name);

CREATE INDEX ix_customization_modules_enabled ON customization_modules (enabled);

CREATE INDEX ix_customization_modules_id ON customization_modules (id);

CREATE INDEX ix_customization_modules_created_at ON customization_modules (created_at);

CREATE TABLE customization_fields (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	field_api_name VARCHAR(120) NOT NULL, 
	field_label VARCHAR(160) NOT NULL, 
	field_type VARCHAR(40) NOT NULL, 
	required BOOLEAN, 
	"unique" BOOLEAN, 
	default_value TEXT, 
	help_text TEXT, 
	options_source VARCHAR(120), 
	lookup_module VARCHAR(100), 
	formula_expression TEXT, 
	rollup_config_json JSON, 
	validation_json JSON, 
	visible BOOLEAN, 
	editable BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_customization_field_module_api UNIQUE (module_name, field_api_name)
);

CREATE INDEX ix_customization_fields_id ON customization_fields (id);

CREATE INDEX ix_customization_fields_field_type ON customization_fields (field_type);

CREATE INDEX ix_customization_fields_module_name ON customization_fields (module_name);

CREATE INDEX ix_customization_fields_created_at ON customization_fields (created_at);

CREATE INDEX ix_customization_fields_field_api_name ON customization_fields (field_api_name);

CREATE TABLE customization_layouts (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	layout_type VARCHAR(40), 
	is_default BOOLEAN, 
	role_visibility_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_layouts_module_name ON customization_layouts (module_name);

CREATE INDEX ix_customization_layouts_created_at ON customization_layouts (created_at);

CREATE INDEX ix_customization_layouts_id ON customization_layouts (id);

CREATE INDEX ix_customization_layouts_is_default ON customization_layouts (is_default);

CREATE INDEX ix_customization_layouts_layout_type ON customization_layouts (layout_type);

CREATE TABLE customization_views (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	view_type VARCHAR(40), 
	filters_json JSON, 
	columns_json JSON, 
	sort_json JSON, 
	shared BOOLEAN, 
	is_default BOOLEAN, 
	owner_user_id INTEGER, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_views_created_at ON customization_views (created_at);

CREATE INDEX ix_customization_views_id ON customization_views (id);

CREATE INDEX ix_customization_views_view_type ON customization_views (view_type);

CREATE INDEX ix_customization_views_module_name ON customization_views (module_name);

CREATE TABLE customization_kanban_views (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	group_by_field VARCHAR(120) NOT NULL, 
	card_fields_json JSON, 
	transition_validation_json JSON, 
	shared BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_kanban_views_module_name ON customization_kanban_views (module_name);

CREATE INDEX ix_customization_kanban_views_created_at ON customization_kanban_views (created_at);

CREATE INDEX ix_customization_kanban_views_id ON customization_kanban_views (id);

CREATE TABLE customization_validation_rules (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	condition_json JSON NOT NULL, 
	error_message TEXT NOT NULL, 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_validation_rules_id ON customization_validation_rules (id);

CREATE INDEX ix_customization_validation_rules_created_at ON customization_validation_rules (created_at);

CREATE INDEX ix_customization_validation_rules_active ON customization_validation_rules (active);

CREATE INDEX ix_customization_validation_rules_module_name ON customization_validation_rules (module_name);

CREATE TABLE customization_related_lists (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	related_module_name VARCHAR(100) NOT NULL, 
	relationship_type VARCHAR(60), 
	lookup_field VARCHAR(120), 
	label VARCHAR(160) NOT NULL, 
	columns_json JSON, 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_related_lists_module_name ON customization_related_lists (module_name);

CREATE INDEX ix_customization_related_lists_id ON customization_related_lists (id);

CREATE TABLE customization_buttons (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	label VARCHAR(160) NOT NULL, 
	action_type VARCHAR(60) NOT NULL, 
	action_config_json JSON, 
	placement VARCHAR(60), 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_buttons_id ON customization_buttons (id);

CREATE INDEX ix_customization_buttons_module_name ON customization_buttons (module_name);

CREATE TABLE customization_global_picklists (
	id SERIAL NOT NULL, 
	api_name VARCHAR(120) NOT NULL, 
	label VARCHAR(160) NOT NULL, 
	description TEXT, 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_customization_picklist_api UNIQUE (api_name)
);

CREATE INDEX ix_customization_global_picklists_api_name ON customization_global_picklists (api_name);

CREATE INDEX ix_customization_global_picklists_id ON customization_global_picklists (id);

CREATE TABLE customization_formula_fields (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	field_api_name VARCHAR(120) NOT NULL, 
	expression TEXT NOT NULL, 
	return_type VARCHAR(40), 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_formula_fields_id ON customization_formula_fields (id);

CREATE INDEX ix_customization_formula_fields_module_name ON customization_formula_fields (module_name);

CREATE INDEX ix_customization_formula_fields_field_api_name ON customization_formula_fields (field_api_name);

CREATE TABLE customization_rollup_fields (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	field_api_name VARCHAR(120) NOT NULL, 
	related_module_name VARCHAR(100) NOT NULL, 
	aggregate_function VARCHAR(40) NOT NULL, 
	aggregate_field VARCHAR(120), 
	filter_json JSON, 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_rollup_fields_id ON customization_rollup_fields (id);

CREATE INDEX ix_customization_rollup_fields_field_api_name ON customization_rollup_fields (field_api_name);

CREATE INDEX ix_customization_rollup_fields_module_name ON customization_rollup_fields (module_name);

CREATE TABLE customization_records (
	id SERIAL NOT NULL, 
	module_api_name VARCHAR(100) NOT NULL, 
	owner_user_id INTEGER, 
	values_json JSON NOT NULL, 
	created_by INTEGER, 
	updated_by INTEGER, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_records_created_at ON customization_records (created_at);

CREATE INDEX ix_customization_records_module_api_name ON customization_records (module_api_name);

CREATE INDEX ix_customization_records_owner_user_id ON customization_records (owner_user_id);

CREATE INDEX ix_customization_records_deleted_at ON customization_records (deleted_at);

CREATE INDEX ix_customization_records_id ON customization_records (id);

CREATE TABLE customization_audit_logs (
	id SERIAL NOT NULL, 
	entity_type VARCHAR(100) NOT NULL, 
	entity_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	actor_user_id INTEGER, 
	before_json JSON, 
	after_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_customization_audit_logs_action ON customization_audit_logs (action);

CREATE INDEX ix_customization_audit_logs_actor_user_id ON customization_audit_logs (actor_user_id);

CREATE INDEX ix_customization_audit_logs_entity_type ON customization_audit_logs (entity_type);

CREATE INDEX ix_customization_audit_logs_entity_id ON customization_audit_logs (entity_id);

CREATE INDEX ix_customization_audit_logs_id ON customization_audit_logs (id);

CREATE INDEX ix_customization_audit_logs_created_at ON customization_audit_logs (created_at);

CREATE TABLE communication_email_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	subject VARCHAR(240) NOT NULL, 
	body_html TEXT, 
	body_text TEXT, 
	module_name VARCHAR(80) NOT NULL, 
	template_type VARCHAR(60), 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_communication_email_templates_name ON communication_email_templates (name);

CREATE INDEX ix_communication_email_templates_active ON communication_email_templates (active);

CREATE INDEX ix_communication_email_templates_id ON communication_email_templates (id);

CREATE INDEX ix_communication_email_templates_module_name ON communication_email_templates (module_name);

CREATE INDEX ix_communication_email_templates_created_at ON communication_email_templates (created_at);

CREATE INDEX ix_communication_email_templates_template_type ON communication_email_templates (template_type);

CREATE TABLE communication_email_messages (
	id SERIAL NOT NULL, 
	related_record_type VARCHAR(80) NOT NULL, 
	related_record_id INTEGER NOT NULL, 
	to_email VARCHAR(180) NOT NULL, 
	cc TEXT, 
	bcc TEXT, 
	subject VARCHAR(240) NOT NULL, 
	body TEXT NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	provider_message_id VARCHAR(180), 
	error_message TEXT, 
	sent_by INTEGER, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(sent_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_communication_email_messages_id ON communication_email_messages (id);

CREATE INDEX ix_communication_email_messages_provider_message_id ON communication_email_messages (provider_message_id);

CREATE INDEX ix_communication_email_messages_sent_at ON communication_email_messages (sent_at);

CREATE INDEX ix_communication_email_messages_to_email ON communication_email_messages (to_email);

CREATE INDEX ix_communication_email_messages_status ON communication_email_messages (status);

CREATE INDEX ix_communication_email_messages_created_at ON communication_email_messages (created_at);

CREATE INDEX ix_communication_email_messages_related_record_type ON communication_email_messages (related_record_type);

CREATE INDEX ix_communication_email_messages_related_record_id ON communication_email_messages (related_record_id);

CREATE INDEX ix_communication_email_messages_sent_by ON communication_email_messages (sent_by);

CREATE TABLE communication_whatsapp_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	template_key VARCHAR(140) NOT NULL, 
	body_text TEXT NOT NULL, 
	provider_status VARCHAR(80), 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_communication_whatsapp_templates_name ON communication_whatsapp_templates (name);

CREATE INDEX ix_communication_whatsapp_templates_provider_status ON communication_whatsapp_templates (provider_status);

CREATE INDEX ix_communication_whatsapp_templates_template_key ON communication_whatsapp_templates (template_key);

CREATE INDEX ix_communication_whatsapp_templates_id ON communication_whatsapp_templates (id);

CREATE INDEX ix_communication_whatsapp_templates_created_at ON communication_whatsapp_templates (created_at);

CREATE INDEX ix_communication_whatsapp_templates_active ON communication_whatsapp_templates (active);

CREATE TABLE communication_timeline_events (
	id SERIAL NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	record_id INTEGER NOT NULL, 
	channel VARCHAR(40) NOT NULL, 
	event_type VARCHAR(80) NOT NULL, 
	subject VARCHAR(240), 
	summary TEXT, 
	metadata_json JSON, 
	actor_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_communication_timeline_events_id ON communication_timeline_events (id);

CREATE INDEX ix_communication_timeline_events_created_at ON communication_timeline_events (created_at);

CREATE INDEX ix_communication_timeline_events_channel ON communication_timeline_events (channel);

CREATE INDEX ix_communication_timeline_events_event_type ON communication_timeline_events (event_type);

CREATE INDEX ix_communication_timeline_events_record_type ON communication_timeline_events (record_type);

CREATE INDEX ix_communication_timeline_events_record_id ON communication_timeline_events (record_id);

CREATE TABLE analytics_reports (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	description TEXT, 
	module_name VARCHAR(100) NOT NULL, 
	report_type VARCHAR(40) NOT NULL, 
	data_source_json JSON, 
	fields_json JSON, 
	filters_json JSON, 
	grouping_json JSON, 
	sorting_json JSON, 
	visibility VARCHAR(40), 
	owner_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_analytics_reports_id ON analytics_reports (id);

CREATE INDEX ix_analytics_reports_module_name ON analytics_reports (module_name);

CREATE INDEX ix_analytics_reports_owner_id ON analytics_reports (owner_id);

CREATE INDEX ix_analytics_reports_name ON analytics_reports (name);

CREATE INDEX ix_analytics_reports_visibility ON analytics_reports (visibility);

CREATE INDEX ix_analytics_reports_created_at ON analytics_reports (created_at);

CREATE INDEX ix_analytics_reports_report_type ON analytics_reports (report_type);

CREATE TABLE analytics_dashboards (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	description TEXT, 
	visibility VARCHAR(40), 
	owner_id INTEGER, 
	filters_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_analytics_dashboards_visibility ON analytics_dashboards (visibility);

CREATE INDEX ix_analytics_dashboards_created_at ON analytics_dashboards (created_at);

CREATE INDEX ix_analytics_dashboards_name ON analytics_dashboards (name);

CREATE INDEX ix_analytics_dashboards_owner_id ON analytics_dashboards (owner_id);

CREATE INDEX ix_analytics_dashboards_id ON analytics_dashboards (id);

CREATE TABLE analytics_anomaly_rules (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	rule_json JSON, 
	active INTEGER, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_analytics_anomaly_rules_created_at ON analytics_anomaly_rules (created_at);

CREATE INDEX ix_analytics_anomaly_rules_name ON analytics_anomaly_rules (name);

CREATE INDEX ix_analytics_anomaly_rules_module_name ON analytics_anomaly_rules (module_name);

CREATE INDEX ix_analytics_anomaly_rules_id ON analytics_anomaly_rules (id);

CREATE INDEX ix_analytics_anomaly_rules_active ON analytics_anomaly_rules (active);

CREATE TABLE ai_provider_settings (
	id SERIAL NOT NULL, 
	provider_name VARCHAR(80) NOT NULL, 
	model_name VARCHAR(120) NOT NULL, 
	enabled BOOLEAN, 
	masked_api_key_reference VARCHAR(180), 
	data_sharing_allowed BOOLEAN, 
	max_tokens INTEGER, 
	temperature FLOAT, 
	created_by INTEGER, 
	updated_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_provider_settings_enabled ON ai_provider_settings (enabled);

CREATE INDEX ix_ai_provider_settings_id ON ai_provider_settings (id);

CREATE INDEX ix_ai_provider_settings_created_at ON ai_provider_settings (created_at);

CREATE INDEX ix_ai_provider_settings_provider_name ON ai_provider_settings (provider_name);

CREATE INDEX ix_ai_provider_settings_data_sharing_allowed ON ai_provider_settings (data_sharing_allowed);

CREATE INDEX ix_ai_provider_settings_created_by ON ai_provider_settings (created_by);

CREATE TABLE ai_prompt_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	use_case VARCHAR(80) NOT NULL, 
	module_name VARCHAR(80) NOT NULL, 
	system_prompt TEXT NOT NULL, 
	user_prompt_template TEXT NOT NULL, 
	output_schema_json JSON, 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_prompt_templates_name ON ai_prompt_templates (name);

CREATE INDEX ix_ai_prompt_templates_module_name ON ai_prompt_templates (module_name);

CREATE INDEX ix_ai_prompt_templates_created_at ON ai_prompt_templates (created_at);

CREATE INDEX ix_ai_prompt_templates_id ON ai_prompt_templates (id);

CREATE INDEX ix_ai_prompt_templates_created_by ON ai_prompt_templates (created_by);

CREATE INDEX ix_ai_prompt_templates_use_case ON ai_prompt_templates (use_case);

CREATE INDEX ix_ai_prompt_templates_active ON ai_prompt_templates (active);

CREATE TABLE admin_manual_record_shares (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	record_id INTEGER NOT NULL, 
	share_with_type VARCHAR(40) NOT NULL, 
	share_with_id INTEGER NOT NULL, 
	access_level VARCHAR(20), 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_admin_manual_share UNIQUE (module_name, record_id, share_with_type, share_with_id)
);

CREATE INDEX ix_admin_manual_record_shares_id ON admin_manual_record_shares (id);

CREATE INDEX ix_admin_manual_record_shares_access_level ON admin_manual_record_shares (access_level);

CREATE INDEX ix_admin_manual_record_shares_record_id ON admin_manual_record_shares (record_id);

CREATE INDEX ix_admin_manual_record_shares_share_with_id ON admin_manual_record_shares (share_with_id);

CREATE INDEX ix_admin_manual_record_shares_module_name ON admin_manual_record_shares (module_name);

CREATE INDEX ix_admin_manual_record_shares_share_with_type ON admin_manual_record_shares (share_with_type);

CREATE INDEX ix_admin_manual_record_shares_active ON admin_manual_record_shares (active);

CREATE TABLE admin_audit_logs (
	id SERIAL NOT NULL, 
	actor_user_id INTEGER, 
	event_type VARCHAR(100) NOT NULL, 
	module_name VARCHAR(100), 
	resource_type VARCHAR(100), 
	resource_id INTEGER, 
	status VARCHAR(30), 
	detail_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_admin_audit_logs_id ON admin_audit_logs (id);

CREATE INDEX ix_admin_audit_logs_resource_id ON admin_audit_logs (resource_id);

CREATE INDEX ix_admin_audit_logs_created_at ON admin_audit_logs (created_at);

CREATE INDEX ix_admin_audit_logs_module_name ON admin_audit_logs (module_name);

CREATE INDEX ix_admin_audit_logs_resource_type ON admin_audit_logs (resource_type);

CREATE INDEX ix_admin_audit_logs_actor_user_id ON admin_audit_logs (actor_user_id);

CREATE INDEX ix_admin_audit_logs_event_type ON admin_audit_logs (event_type);

CREATE INDEX ix_admin_audit_logs_status ON admin_audit_logs (status);

CREATE TABLE admin_import_jobs (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	filename VARCHAR(240) NOT NULL, 
	status VARCHAR(30), 
	total_rows INTEGER, 
	success_rows INTEGER, 
	failed_rows INTEGER, 
	duplicate_rows INTEGER, 
	mapping_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_admin_import_jobs_created_by ON admin_import_jobs (created_by);

CREATE INDEX ix_admin_import_jobs_module_name ON admin_import_jobs (module_name);

CREATE INDEX ix_admin_import_jobs_status ON admin_import_jobs (status);

CREATE INDEX ix_admin_import_jobs_id ON admin_import_jobs (id);

CREATE TABLE admin_merge_logs (
	id SERIAL NOT NULL, 
	module_name VARCHAR(100) NOT NULL, 
	winner_record_id INTEGER NOT NULL, 
	loser_record_ids_json JSON, 
	merged_by INTEGER, 
	detail_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(merged_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_admin_merge_logs_module_name ON admin_merge_logs (module_name);

CREATE INDEX ix_admin_merge_logs_id ON admin_merge_logs (id);

CREATE TABLE admin_backup_requests (
	id SERIAL NOT NULL, 
	scope VARCHAR(100), 
	status VARCHAR(30), 
	requested_by INTEGER, 
	requested_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	detail_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_admin_backup_requests_id ON admin_backup_requests (id);

CREATE INDEX ix_admin_backup_requests_status ON admin_backup_requests (status);

CREATE TABLE portal_users (
	id SERIAL NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	display_name VARCHAR(160) NOT NULL, 
	portal_type VARCHAR(30) NOT NULL, 
	role_id INTEGER, 
	status VARCHAR(30), 
	password_hash VARCHAR(255), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(role_id) REFERENCES portal_roles (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_portal_users_role_id ON portal_users (role_id);

CREATE INDEX ix_portal_users_created_by ON portal_users (created_by);

CREATE UNIQUE INDEX ix_portal_users_email ON portal_users (email);

CREATE INDEX ix_portal_users_status ON portal_users (status);

CREATE INDEX ix_portal_users_portal_type ON portal_users (portal_type);

CREATE INDEX ix_portal_users_created_at ON portal_users (created_at);

CREATE INDEX ix_portal_users_id ON portal_users (id);

CREATE TABLE developer_api_keys (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	key_prefix VARCHAR(20) NOT NULL, 
	key_hash VARCHAR(255) NOT NULL, 
	scopes_json JSON, 
	status VARCHAR(30), 
	created_by INTEGER, 
	revoked_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	last_used_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(revoked_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX ix_developer_api_keys_key_hash ON developer_api_keys (key_hash);

CREATE INDEX ix_developer_api_keys_status ON developer_api_keys (status);

CREATE INDEX ix_developer_api_keys_name ON developer_api_keys (name);

CREATE INDEX ix_developer_api_keys_key_prefix ON developer_api_keys (key_prefix);

CREATE INDEX ix_developer_api_keys_created_at ON developer_api_keys (created_at);

CREATE INDEX ix_developer_api_keys_id ON developer_api_keys (id);

CREATE INDEX ix_developer_api_keys_created_by ON developer_api_keys (created_by);

CREATE TABLE developer_webhooks (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	target_url VARCHAR(500) NOT NULL, 
	events_json JSON, 
	secret_hash VARCHAR(255), 
	status VARCHAR(30), 
	retry_enabled BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_developer_webhooks_id ON developer_webhooks (id);

CREATE INDEX ix_developer_webhooks_status ON developer_webhooks (status);

CREATE INDEX ix_developer_webhooks_created_at ON developer_webhooks (created_at);

CREATE INDEX ix_developer_webhooks_name ON developer_webhooks (name);

CREATE INDEX ix_developer_webhooks_created_by ON developer_webhooks (created_by);

CREATE TABLE developer_apps (
	id SERIAL NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	description TEXT, 
	owner_user_id INTEGER, 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_developer_apps_owner_user_id ON developer_apps (owner_user_id);

CREATE INDEX ix_developer_apps_name ON developer_apps (name);

CREATE INDEX ix_developer_apps_status ON developer_apps (status);

CREATE INDEX ix_developer_apps_id ON developer_apps (id);

CREATE TABLE marketplace_apps (
	id SERIAL NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	category VARCHAR(80), 
	description TEXT, 
	internal_only BOOLEAN, 
	configuration_schema_json JSON, 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_marketplace_apps_category ON marketplace_apps (category);

CREATE INDEX ix_marketplace_apps_status ON marketplace_apps (status);

CREATE INDEX ix_marketplace_apps_name ON marketplace_apps (name);

CREATE INDEX ix_marketplace_apps_internal_only ON marketplace_apps (internal_only);

CREATE INDEX ix_marketplace_apps_id ON marketplace_apps (id);

CREATE TABLE sandbox_environments (
	id SERIAL NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	source_environment VARCHAR(80), 
	status VARCHAR(30), 
	access_url_placeholder VARCHAR(500), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	refreshed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_sandbox_environments_name ON sandbox_environments (name);

CREATE INDEX ix_sandbox_environments_id ON sandbox_environments (id);

CREATE INDEX ix_sandbox_environments_created_at ON sandbox_environments (created_at);

CREATE INDEX ix_sandbox_environments_status ON sandbox_environments (status);

CREATE INDEX ix_sandbox_environments_created_by ON sandbox_environments (created_by);

CREATE TABLE tenant_company_settings (
	id SERIAL NOT NULL, 
	company_name VARCHAR(180) NOT NULL, 
	logo_url VARCHAR(500), 
	fiscal_year_start_month INTEGER, 
	base_currency VARCHAR(12), 
	timezone VARCHAR(80), 
	tax_defaults_json JSON, 
	business_hours_json JSON, 
	numbering_settings_json JSON, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_tenant_company_settings_id ON tenant_company_settings (id);

CREATE TABLE tenant_feature_flags (
	id SERIAL NOT NULL, 
	feature_key VARCHAR(120) NOT NULL, 
	enabled BOOLEAN, 
	upgrade_message VARCHAR(255), 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_tenant_feature_flags_enabled ON tenant_feature_flags (enabled);

CREATE UNIQUE INDEX ix_tenant_feature_flags_feature_key ON tenant_feature_flags (feature_key);

CREATE INDEX ix_tenant_feature_flags_id ON tenant_feature_flags (id);

CREATE TABLE mobile_sales_visit_checkins (
	id SERIAL NOT NULL, 
	lead_id INTEGER, 
	deal_id INTEGER, 
	customer_name VARCHAR(180) NOT NULL, 
	latitude VARCHAR(40), 
	longitude VARCHAR(40), 
	notes TEXT, 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_mobile_sales_visit_checkins_lead_id ON mobile_sales_visit_checkins (lead_id);

CREATE INDEX ix_mobile_sales_visit_checkins_deal_id ON mobile_sales_visit_checkins (deal_id);

CREATE INDEX ix_mobile_sales_visit_checkins_id ON mobile_sales_visit_checkins (id);

CREATE INDEX ix_mobile_sales_visit_checkins_created_at ON mobile_sales_visit_checkins (created_at);

CREATE INDEX ix_mobile_sales_visit_checkins_status ON mobile_sales_visit_checkins (status);

CREATE INDEX ix_mobile_sales_visit_checkins_created_by ON mobile_sales_visit_checkins (created_by);

CREATE TABLE bos_enabled_modules (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	module_key VARCHAR(80) NOT NULL, 
	display_name VARCHAR(160) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	is_financial_backbone BOOLEAN NOT NULL, 
	enabled_by INTEGER, 
	disabled_by INTEGER, 
	enabled_at TIMESTAMP WITH TIME ZONE, 
	disabled_at TIMESTAMP WITH TIME ZONE, 
	metadata_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_bos_enabled_module_company_key UNIQUE (company_id, module_key), 
	FOREIGN KEY(disabled_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(enabled_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_bos_enabled_modules_id ON bos_enabled_modules (id);

CREATE INDEX ix_bos_enabled_modules_enabled ON bos_enabled_modules (enabled);

CREATE INDEX ix_bos_enabled_modules_company_id ON bos_enabled_modules (company_id);

CREATE INDEX ix_bos_enabled_modules_module_key ON bos_enabled_modules (module_key);

CREATE TABLE bos_lifecycle_events (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	module_key VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(120) NOT NULL, 
	entity_id VARCHAR(80) NOT NULL, 
	event_name VARCHAR(120) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	message TEXT, 
	source_module VARCHAR(80), 
	target_module VARCHAR(80), 
	actor_user_id INTEGER, 
	evidence_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_bos_lifecycle_events_company_id ON bos_lifecycle_events (company_id);

CREATE INDEX ix_bos_lifecycle_events_entity_id ON bos_lifecycle_events (entity_id);

CREATE INDEX ix_bos_lifecycle_events_source_module ON bos_lifecycle_events (source_module);

CREATE INDEX ix_bos_lifecycle_events_id ON bos_lifecycle_events (id);

CREATE INDEX ix_bos_lifecycle_events_module_key ON bos_lifecycle_events (module_key);

CREATE INDEX ix_bos_lifecycle_events_event_name ON bos_lifecycle_events (event_name);

CREATE INDEX ix_bos_lifecycle_events_target_module ON bos_lifecycle_events (target_module);

CREATE INDEX ix_bos_lifecycle_events_entity_type ON bos_lifecycle_events (entity_type);

CREATE INDEX ix_bos_lifecycle_events_status ON bos_lifecycle_events (status);

CREATE INDEX ix_bos_lifecycle_events_created_at ON bos_lifecycle_events (created_at);

CREATE TABLE ai_agents (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	code VARCHAR(120) NOT NULL, 
	module VARCHAR(40) NOT NULL, 
	description TEXT, 
	system_prompt TEXT NOT NULL, 
	model VARCHAR(80), 
	temperature FLOAT, 
	is_active BOOLEAN, 
	requires_approval BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX ix_ai_agents_code ON ai_agents (code);

CREATE INDEX ix_ai_agents_name ON ai_agents (name);

CREATE INDEX ix_ai_agents_id ON ai_agents (id);

CREATE INDEX ix_ai_agents_module ON ai_agents (module);

CREATE INDEX ix_ai_agents_is_active ON ai_agents (is_active);

CREATE TABLE ai_security_settings (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	ai_enabled BOOLEAN, 
	crm_ai_enabled BOOLEAN, 
	pms_ai_enabled BOOLEAN, 
	hrms_ai_enabled BOOLEAN, 
	cross_ai_enabled BOOLEAN, 
	emergency_message TEXT, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_ai_security_settings_company_id ON ai_security_settings (company_id);

CREATE INDEX ix_ai_security_settings_id ON ai_security_settings (id);

CREATE TABLE biometric_import_batches (
	id SERIAL NOT NULL, 
	device_id INTEGER, 
	source_filename VARCHAR(250), 
	imported_rows INTEGER, 
	skipped_rows INTEGER, 
	error_rows INTEGER, 
	status VARCHAR(30), 
	error_report_json TEXT, 
	imported_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(device_id) REFERENCES biometric_devices (id) ON DELETE SET NULL, 
	FOREIGN KEY(imported_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_biometric_import_batches_device_id ON biometric_import_batches (device_id);

CREATE INDEX ix_biometric_import_batches_id ON biometric_import_batches (id);

CREATE INDEX ix_biometric_import_batches_status ON biometric_import_batches (status);

CREATE TABLE attendance_month_locks (
	id SERIAL NOT NULL, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	status VARCHAR(20), 
	reason TEXT, 
	locked_by INTEGER, 
	locked_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	unlocked_by INTEGER, 
	unlocked_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unlocked_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(locked_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_attendance_month_locks_status ON attendance_month_locks (status);

CREATE INDEX ix_attendance_month_locks_id ON attendance_month_locks (id);

CREATE INDEX ix_attendance_month_locks_month ON attendance_month_locks (month);

CREATE INDEX ix_attendance_month_locks_year ON attendance_month_locks (year);

CREATE TABLE statutory_compliance_calendar (
	id SERIAL NOT NULL, 
	statutory_type VARCHAR(50), 
	due_date DATE NOT NULL, 
	period_start DATE, 
	period_end DATE, 
	description VARCHAR(500), 
	status VARCHAR(30), 
	filed_at TIMESTAMP WITH TIME ZONE, 
	filed_by INTEGER, 
	remarks TEXT, 
	company_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id), 
	FOREIGN KEY(filed_by) REFERENCES users (id)
);

CREATE INDEX ix_statutory_compliance_calendar_status ON statutory_compliance_calendar (status);

CREATE INDEX ix_statutory_compliance_calendar_statutory_type ON statutory_compliance_calendar (statutory_type);

CREATE INDEX ix_statutory_compliance_calendar_due_date ON statutory_compliance_calendar (due_date);

CREATE TABLE statutory_template_files (
	id SERIAL NOT NULL, 
	template_type VARCHAR(50) NOT NULL, 
	format_version VARCHAR(30), 
	file_url VARCHAR(500) NOT NULL, 
	status VARCHAR(30), 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_statutory_template_files_status ON statutory_template_files (status);

CREATE INDEX ix_statutory_template_files_id ON statutory_template_files (id);

CREATE INDEX ix_statutory_template_files_template_type ON statutory_template_files (template_type);

CREATE TABLE salary_revision_batches (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	effective_from DATE NOT NULL, 
	status VARCHAR(30), 
	total_rows INTEGER, 
	applied_rows INTEGER, 
	created_by INTEGER, 
	applied_by INTEGER, 
	applied_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(applied_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_salary_revision_batches_id ON salary_revision_batches (id);

CREATE INDEX ix_salary_revision_batches_status ON salary_revision_batches (status);

CREATE TABLE payroll_exchange_rates (
	id SERIAL NOT NULL, 
	from_currency VARCHAR(3) NOT NULL, 
	to_currency VARCHAR(3) NOT NULL, 
	rate NUMERIC(14, 6) NOT NULL, 
	effective_date DATE NOT NULL, 
	source VARCHAR(80), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_exchange_rates_effective_date ON payroll_exchange_rates (effective_date);

CREATE INDEX ix_payroll_exchange_rates_from_currency ON payroll_exchange_rates (from_currency);

CREATE INDEX ix_payroll_exchange_rates_to_currency ON payroll_exchange_rates (to_currency);

CREATE INDEX ix_payroll_exchange_rates_id ON payroll_exchange_rates (id);

CREATE TABLE payroll_report_definitions (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	report_type VARCHAR(80) NOT NULL, 
	filters_json JSON, 
	columns_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_report_definitions_report_type ON payroll_report_definitions (report_type);

CREATE INDEX ix_payroll_report_definitions_id ON payroll_report_definitions (id);

CREATE TABLE onboarding_templates (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(150) NOT NULL, 
	description TEXT, 
	applicable_for VARCHAR(30), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	created_by INTEGER, 
	applicable_designation_ids TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_onboarding_templates_organization_id ON onboarding_templates (organization_id);

CREATE INDEX ix_onboarding_templates_is_active ON onboarding_templates (is_active);

CREATE INDEX ix_onboarding_templates_id ON onboarding_templates (id);

CREATE INDEX ix_onboarding_templates_applicable_for ON onboarding_templates (applicable_for);

CREATE TABLE appraisal_cycles (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(150) NOT NULL, 
	cycle_type VARCHAR(20), 
	review_period_start DATE, 
	review_period_end DATE, 
	start_date DATE, 
	end_date DATE, 
	self_review_deadline DATE, 
	manager_review_deadline DATE, 
	status VARCHAR(20), 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_appraisal_cycles_id ON appraisal_cycles (id);

CREATE INDEX ix_appraisal_cycles_organization_id ON appraisal_cycles (organization_id);

CREATE TABLE helpdesk_knowledge_articles (
	id SERIAL NOT NULL, 
	category_id INTEGER, 
	title VARCHAR(250) NOT NULL, 
	body TEXT NOT NULL, 
	keywords TEXT, 
	version VARCHAR(20), 
	is_published BOOLEAN, 
	created_by INTEGER, 
	published_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES helpdesk_categories (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_helpdesk_knowledge_articles_title ON helpdesk_knowledge_articles (title);

CREATE INDEX ix_helpdesk_knowledge_articles_id ON helpdesk_knowledge_articles (id);

CREATE INDEX ix_helpdesk_knowledge_articles_is_published ON helpdesk_knowledge_articles (is_published);

CREATE INDEX ix_helpdesk_knowledge_articles_category_id ON helpdesk_knowledge_articles (category_id);

CREATE TABLE helpdesk_escalation_rules (
	id SERIAL NOT NULL, 
	category_id INTEGER, 
	priority VARCHAR(20), 
	escalate_after_hours INTEGER, 
	escalate_to_user_id INTEGER, 
	escalation_team VARCHAR(120), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(escalate_to_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(category_id) REFERENCES helpdesk_categories (id) ON DELETE CASCADE
);

CREATE INDEX ix_helpdesk_escalation_rules_category_id ON helpdesk_escalation_rules (category_id);

CREATE INDEX ix_helpdesk_escalation_rules_id ON helpdesk_escalation_rules (id);

CREATE INDEX ix_helpdesk_escalation_rules_priority ON helpdesk_escalation_rules (priority);

CREATE INDEX ix_helpdesk_escalation_rules_is_active ON helpdesk_escalation_rules (is_active);

CREATE TABLE company_policy_versions (
	id SERIAL NOT NULL, 
	policy_id INTEGER NOT NULL, 
	version VARCHAR(20) NOT NULL, 
	content TEXT, 
	document_url VARCHAR(500), 
	effective_date TIMESTAMP WITH TIME ZONE, 
	change_summary TEXT, 
	published_by INTEGER, 
	published_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(published_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(policy_id) REFERENCES company_policies (id) ON DELETE CASCADE
);

CREATE INDEX ix_company_policy_versions_policy_id ON company_policy_versions (policy_id);

CREATE INDEX ix_company_policy_versions_id ON company_policy_versions (id);

CREATE TABLE custom_field_values (
	id SERIAL NOT NULL, 
	definition_id INTEGER NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	value_text TEXT, 
	value_json JSON, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(definition_id) REFERENCES custom_field_definitions (id) ON DELETE CASCADE
);

CREATE INDEX ix_custom_field_values_entity_type ON custom_field_values (entity_type);

CREATE INDEX ix_custom_field_values_definition_id ON custom_field_values (definition_id);

CREATE INDEX ix_custom_field_values_id ON custom_field_values (id);

CREATE INDEX ix_custom_field_values_entity_id ON custom_field_values (entity_id);

CREATE TABLE custom_form_definitions (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	module VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	description TEXT, 
	trigger_event VARCHAR(120), 
	visible_to_roles VARCHAR(250), 
	editable_by_roles VARCHAR(250), 
	allow_multiple_submissions BOOLEAN, 
	workflow_required BOOLEAN, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_custom_form_definitions_module ON custom_form_definitions (module);

CREATE INDEX ix_custom_form_definitions_is_active ON custom_form_definitions (is_active);

CREATE INDEX ix_custom_form_definitions_id ON custom_form_definitions (id);

CREATE INDEX ix_custom_form_definitions_entity_type ON custom_form_definitions (entity_type);

CREATE UNIQUE INDEX ix_custom_form_definitions_code ON custom_form_definitions (code);

CREATE TABLE report_definitions (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	module VARCHAR(80) NOT NULL, 
	field_catalog_json JSON, 
	selected_fields_json JSON, 
	filters_json JSON, 
	schedule_cron VARCHAR(80), 
	export_format VARCHAR(20), 
	visible_to_roles VARCHAR(250), 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_report_definitions_id ON report_definitions (id);

CREATE INDEX ix_report_definitions_module ON report_definitions (module);

CREATE INDEX ix_report_definitions_is_active ON report_definitions (is_active);

CREATE UNIQUE INDEX ix_report_definitions_code ON report_definitions (code);

CREATE TABLE integration_credentials (
	id SERIAL NOT NULL, 
	provider VARCHAR(100) NOT NULL, 
	credential_name VARCHAR(150) NOT NULL, 
	auth_type VARCHAR(50), 
	secret_ref VARCHAR(255) NOT NULL, 
	scopes VARCHAR(500), 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_integration_credentials_status ON integration_credentials (status);

CREATE INDEX ix_integration_credentials_id ON integration_credentials (id);

CREATE INDEX ix_integration_credentials_provider ON integration_credentials (provider);

CREATE TABLE webhook_subscriptions (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	event_type VARCHAR(120) NOT NULL, 
	target_url VARCHAR(500) NOT NULL, 
	secret_ref VARCHAR(255), 
	is_active BOOLEAN, 
	retry_policy_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_webhook_subscriptions_event_type ON webhook_subscriptions (event_type);

CREATE INDEX ix_webhook_subscriptions_id ON webhook_subscriptions (id);

CREATE INDEX ix_webhook_subscriptions_is_active ON webhook_subscriptions (is_active);

CREATE TABLE legal_holds (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	module VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(80), 
	entity_id INTEGER, 
	reason TEXT, 
	status VARCHAR(30), 
	placed_by INTEGER, 
	placed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	released_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(placed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_legal_holds_status ON legal_holds (status);

CREATE INDEX ix_legal_holds_module ON legal_holds (module);

CREATE INDEX ix_legal_holds_id ON legal_holds (id);

CREATE TABLE domain_pack_registry (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	pack_key VARCHAR(80) NOT NULL, 
	pack_name VARCHAR(150) NOT NULL, 
	status VARCHAR(30), 
	config_json JSON, 
	enabled_by INTEGER, 
	enabled_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	disabled_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(enabled_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_domain_pack_registry_status ON domain_pack_registry (status);

CREATE UNIQUE INDEX idx_domain_pack_company_key ON domain_pack_registry (company_id, pack_key);

CREATE INDEX ix_domain_pack_registry_company_id ON domain_pack_registry (company_id);

CREATE INDEX ix_domain_pack_registry_pack_key ON domain_pack_registry (pack_key);

CREATE INDEX ix_domain_pack_registry_id ON domain_pack_registry (id);

CREATE TABLE manufacturing_contract_labor_batches (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	vendor_name VARCHAR(180) NOT NULL, 
	batch_code VARCHAR(80) NOT NULL, 
	work_order_number VARCHAR(100), 
	start_date DATE NOT NULL, 
	end_date DATE, 
	headcount INTEGER, 
	compliance_status VARCHAR(40), 
	document_url VARCHAR(500), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_manufacturing_contract_labor_batches_id ON manufacturing_contract_labor_batches (id);

CREATE INDEX ix_manufacturing_contract_labor_batches_compliance_status ON manufacturing_contract_labor_batches (compliance_status);

CREATE INDEX ix_manufacturing_contract_labor_batches_batch_code ON manufacturing_contract_labor_batches (batch_code);

CREATE INDEX ix_manufacturing_contract_labor_batches_start_date ON manufacturing_contract_labor_batches (start_date);

CREATE INDEX ix_manufacturing_contract_labor_batches_company_id ON manufacturing_contract_labor_batches (company_id);

CREATE INDEX ix_manufacturing_contract_labor_batches_vendor_name ON manufacturing_contract_labor_batches (vendor_name);

CREATE TABLE learning_courses (
	id SERIAL NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	title VARCHAR(220) NOT NULL, 
	description TEXT, 
	category VARCHAR(100), 
	delivery_mode VARCHAR(40), 
	duration_hours NUMERIC(6, 2), 
	content_standard VARCHAR(30), 
	scorm_package_url VARCHAR(500), 
	scorm_version VARCHAR(40), 
	xapi_activity_id VARCHAR(300), 
	xapi_launch_url VARCHAR(500), 
	external_launch_url VARCHAR(500), 
	completion_callback_url VARCHAR(500), 
	metadata_json JSON, 
	is_mandatory BOOLEAN, 
	is_active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX ix_learning_courses_code ON learning_courses (code);

CREATE INDEX ix_learning_courses_is_active ON learning_courses (is_active);

CREATE INDEX ix_learning_courses_id ON learning_courses (id);

CREATE TABLE engagement_surveys (
	id SERIAL NOT NULL, 
	title VARCHAR(220) NOT NULL, 
	survey_type VARCHAR(40), 
	question TEXT, 
	options_json JSON, 
	start_date DATE, 
	end_date DATE, 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_engagement_surveys_id ON engagement_surveys (id);

CREATE INDEX ix_engagement_surveys_status ON engagement_surveys (status);

CREATE TABLE whatsapp_ess_configs (
	id SERIAL NOT NULL, 
	provider VARCHAR(80), 
	business_phone_number VARCHAR(30) NOT NULL, 
	webhook_url VARCHAR(500), 
	access_token_ref VARCHAR(200), 
	app_secret_ref VARCHAR(200), 
	verify_token_ref VARCHAR(200), 
	default_language VARCHAR(20), 
	is_active BOOLEAN, 
	opt_in_required BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_whatsapp_ess_configs_is_active ON whatsapp_ess_configs (is_active);

CREATE INDEX ix_whatsapp_ess_configs_id ON whatsapp_ess_configs (id);

CREATE TABLE tds_return_filings (
	id SERIAL NOT NULL, 
	legal_entity_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	quarter VARCHAR(10) NOT NULL, 
	form_type VARCHAR(20), 
	due_date DATE, 
	status VARCHAR(30), 
	return_file_url VARCHAR(500), 
	fvu_file_url VARCHAR(500), 
	acknowledgement_number VARCHAR(100), 
	filed_at TIMESTAMP WITH TIME ZONE, 
	filed_by INTEGER, 
	total_tax_deducted NUMERIC(14, 2), 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(filed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE CASCADE
);

CREATE INDEX ix_tds_return_filings_financial_year ON tds_return_filings (financial_year);

CREATE INDEX ix_tds_return_filings_id ON tds_return_filings (id);

CREATE INDEX ix_tds_return_filings_status ON tds_return_filings (status);

CREATE INDEX ix_tds_return_filings_legal_entity_id ON tds_return_filings (legal_entity_id);

CREATE INDEX ix_tds_return_filings_quarter ON tds_return_filings (quarter);

CREATE INDEX ix_tds_return_filings_form_type ON tds_return_filings (form_type);

CREATE TABLE statutory_portal_submissions (
	id SERIAL NOT NULL, 
	legal_entity_id INTEGER NOT NULL, 
	portal_type VARCHAR(30) NOT NULL, 
	period_month INTEGER NOT NULL, 
	period_year INTEGER NOT NULL, 
	submission_type VARCHAR(50) NOT NULL, 
	due_date DATE, 
	status VARCHAR(30), 
	upload_file_url VARCHAR(500), 
	challan_file_url VARCHAR(500), 
	acknowledgement_number VARCHAR(100), 
	payment_reference VARCHAR(100), 
	total_amount NUMERIC(14, 2), 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	submitted_by INTEGER, 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE CASCADE, 
	FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_statutory_portal_submissions_portal_type ON statutory_portal_submissions (portal_type);

CREATE INDEX ix_statutory_portal_submissions_id ON statutory_portal_submissions (id);

CREATE INDEX ix_statutory_portal_submissions_legal_entity_id ON statutory_portal_submissions (legal_entity_id);

CREATE INDEX ix_statutory_portal_submissions_status ON statutory_portal_submissions (status);

CREATE TABLE statutory_compliance_events (
	id SERIAL NOT NULL, 
	legal_entity_id INTEGER NOT NULL, 
	compliance_type VARCHAR(40) NOT NULL, 
	period_month INTEGER, 
	period_year INTEGER, 
	financial_year VARCHAR(20), 
	due_date DATE NOT NULL, 
	owner_user_id INTEGER, 
	status VARCHAR(30), 
	source_entity_type VARCHAR(80), 
	source_entity_id INTEGER, 
	alert_status VARCHAR(30), 
	reminder_sent_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_statutory_compliance_events_id ON statutory_compliance_events (id);

CREATE INDEX ix_statutory_compliance_events_legal_entity_id ON statutory_compliance_events (legal_entity_id);

CREATE INDEX ix_statutory_compliance_events_due_date ON statutory_compliance_events (due_date);

CREATE INDEX ix_statutory_compliance_events_compliance_type ON statutory_compliance_events (compliance_type);

CREATE INDEX ix_statutory_compliance_events_status ON statutory_compliance_events (status);

CREATE TABLE benefit_enrollment_windows (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	plan_type VARCHAR(50), 
	description TEXT, 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_benefit_enrollment_windows_plan_type ON benefit_enrollment_windows (plan_type);

CREATE INDEX ix_benefit_enrollment_windows_status ON benefit_enrollment_windows (status);

CREATE INDEX ix_benefit_enrollment_windows_id ON benefit_enrollment_windows (id);

CREATE INDEX ix_benefit_enrollment_windows_end_date ON benefit_enrollment_windows (end_date);

CREATE INDEX ix_benefit_enrollment_windows_start_date ON benefit_enrollment_windows (start_date);

CREATE TABLE crm_accounts (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	account_number VARCHAR(60), 
	account_name VARCHAR(180) NOT NULL, 
	legal_name VARCHAR(180), 
	industry VARCHAR(120), 
	website VARCHAR(200), 
	phone VARCHAR(40), 
	billing_address TEXT, 
	shipping_address TEXT, 
	country VARCHAR(100), 
	tax_registration_number VARCHAR(80), 
	owner_id INTEGER, 
	account_status VARCHAR(40), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_crm_account_org_number UNIQUE (organization_id, account_number), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_accounts_id ON crm_accounts (id);

CREATE INDEX ix_crm_accounts_industry ON crm_accounts (industry);

CREATE INDEX ix_crm_accounts_owner_id ON crm_accounts (owner_id);

CREATE INDEX ix_crm_accounts_account_name ON crm_accounts (account_name);

CREATE INDEX ix_crm_accounts_country ON crm_accounts (country);

CREATE INDEX ix_crm_accounts_account_status ON crm_accounts (account_status);

CREATE INDEX ix_crm_accounts_organization_id ON crm_accounts (organization_id);

CREATE INDEX ix_crm_accounts_account_number ON crm_accounts (account_number);

CREATE INDEX ix_crm_accounts_tax_registration_number ON crm_accounts (tax_registration_number);

CREATE TABLE crm_lead_scoring_rules (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	field VARCHAR(100) NOT NULL, 
	operator VARCHAR(40) NOT NULL, 
	value VARCHAR(240), 
	points INTEGER NOT NULL, 
	is_active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_lead_scoring_rule_org_name UNIQUE (organization_id, name)
);

CREATE INDEX ix_crm_lead_scoring_rules_operator ON crm_lead_scoring_rules (operator);

CREATE INDEX ix_crm_lead_scoring_rules_id ON crm_lead_scoring_rules (id);

CREATE INDEX ix_crm_lead_scoring_rules_field ON crm_lead_scoring_rules (field);

CREATE INDEX ix_crm_lead_scoring_rules_organization_id ON crm_lead_scoring_rules (organization_id);

CREATE INDEX ix_crm_lead_scoring_rules_is_active ON crm_lead_scoring_rules (is_active);

CREATE INDEX ix_crm_lead_scoring_rules_name ON crm_lead_scoring_rules (name);

CREATE TABLE crm_pipelines (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	description TEXT, 
	is_default BOOLEAN, 
	active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_pipelines_is_default ON crm_pipelines (is_default);

CREATE INDEX ix_crm_pipelines_active ON crm_pipelines (active);

CREATE INDEX ix_crm_pipelines_organization_id ON crm_pipelines (organization_id);

CREATE INDEX ix_crm_pipelines_id ON crm_pipelines (id);

CREATE TABLE crm_products (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	product_code VARCHAR(80), 
	name VARCHAR(180) NOT NULL, 
	sku VARCHAR(80), 
	category VARCHAR(120), 
	description TEXT, 
	unit_of_measure VARCHAR(40), 
	list_price NUMERIC(14, 2), 
	cost_price NUMERIC(14, 2), 
	unit_price NUMERIC(12, 2), 
	currency VARCHAR(10), 
	tax_rate NUMERIC(5, 2), 
	image_url VARCHAR(500), 
	active BOOLEAN, 
	status VARCHAR(30), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_product_org_sku UNIQUE (organization_id, sku)
);

CREATE INDEX ix_crm_products_product_code ON crm_products (product_code);

CREATE INDEX ix_crm_products_sku ON crm_products (sku);

CREATE INDEX ix_crm_products_organization_id ON crm_products (organization_id);

CREATE INDEX ix_crm_products_name ON crm_products (name);

CREATE INDEX ix_crm_products_active ON crm_products (active);

CREATE INDEX ix_crm_products_id ON crm_products (id);

CREATE INDEX ix_crm_products_category ON crm_products (category);

CREATE INDEX ix_crm_products_status ON crm_products (status);

CREATE TABLE crm_services (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	service_code VARCHAR(80) NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	category VARCHAR(120), 
	description TEXT, 
	billing_type VARCHAR(30), 
	default_rate NUMERIC(14, 2), 
	default_cost NUMERIC(14, 2), 
	tax_rate NUMERIC(5, 2), 
	active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_service_org_code UNIQUE (organization_id, service_code)
);

CREATE INDEX ix_crm_services_category ON crm_services (category);

CREATE INDEX ix_crm_services_organization_id ON crm_services (organization_id);

CREATE INDEX ix_crm_services_billing_type ON crm_services (billing_type);

CREATE INDEX ix_crm_services_id ON crm_services (id);

CREATE INDEX ix_crm_services_name ON crm_services (name);

CREATE INDEX ix_crm_services_active ON crm_services (active);

CREATE INDEX ix_crm_services_service_code ON crm_services (service_code);

CREATE TABLE crm_price_books (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	currency VARCHAR(10), 
	region VARCHAR(120), 
	customer_segment VARCHAR(120), 
	effective_from DATE, 
	effective_to DATE, 
	active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_crm_price_book_scope UNIQUE (organization_id, name, currency, region, customer_segment), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_price_books_id ON crm_price_books (id);

CREATE INDEX ix_crm_price_books_customer_segment ON crm_price_books (customer_segment);

CREATE INDEX ix_crm_price_books_active ON crm_price_books (active);

CREATE INDEX ix_crm_price_books_currency ON crm_price_books (currency);

CREATE INDEX ix_crm_price_books_region ON crm_price_books (region);

CREATE INDEX ix_crm_price_books_effective_from ON crm_price_books (effective_from);

CREATE INDEX ix_crm_price_books_name ON crm_price_books (name);

CREATE INDEX ix_crm_price_books_effective_to ON crm_price_books (effective_to);

CREATE INDEX ix_crm_price_books_organization_id ON crm_price_books (organization_id);

CREATE TABLE crm_cpq_rules (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	rule_type VARCHAR(40) NOT NULL, 
	condition_json JSON, 
	action_json JSON, 
	active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_cpq_rules_organization_id ON crm_cpq_rules (organization_id);

CREATE INDEX ix_crm_cpq_rules_name ON crm_cpq_rules (name);

CREATE INDEX ix_crm_cpq_rules_active ON crm_cpq_rules (active);

CREATE INDEX ix_crm_cpq_rules_id ON crm_cpq_rules (id);

CREATE INDEX ix_crm_cpq_rules_rule_type ON crm_cpq_rules (rule_type);

CREATE TABLE crm_guided_selling_flows (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	question_json JSON, 
	recommendation_json JSON, 
	active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_guided_selling_flows_id ON crm_guided_selling_flows (id);

CREATE INDEX ix_crm_guided_selling_flows_organization_id ON crm_guided_selling_flows (organization_id);

CREATE INDEX ix_crm_guided_selling_flows_name ON crm_guided_selling_flows (name);

CREATE INDEX ix_crm_guided_selling_flows_active ON crm_guided_selling_flows (active);

CREATE TABLE crm_timeline_events (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	record_type VARCHAR(40) NOT NULL, 
	record_id INTEGER NOT NULL, 
	event_type VARCHAR(80) NOT NULL, 
	title VARCHAR(220) NOT NULL, 
	description TEXT, 
	metadata_json JSON, 
	actor_user_id INTEGER, 
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_timeline_events_record_type ON crm_timeline_events (record_type);

CREATE INDEX ix_crm_timeline_events_occurred_at ON crm_timeline_events (occurred_at);

CREATE INDEX ix_crm_timeline_events_organization_id ON crm_timeline_events (organization_id);

CREATE INDEX ix_crm_timeline_events_actor_user_id ON crm_timeline_events (actor_user_id);

CREATE INDEX ix_crm_timeline_events_record_id ON crm_timeline_events (record_id);

CREATE INDEX ix_crm_timeline_events_event_type ON crm_timeline_events (event_type);

CREATE INDEX ix_crm_timeline_events_id ON crm_timeline_events (id);

CREATE TABLE crm_enrichment_logs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	entity_type VARCHAR(40) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	provider VARCHAR(80) NOT NULL, 
	old_values_json JSON, 
	new_values_json JSON, 
	applied_fields_json JSON, 
	status VARCHAR(30), 
	created_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_by_user_id INTEGER, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_enrichment_logs_id ON crm_enrichment_logs (id);

CREATE INDEX ix_crm_enrichment_logs_status ON crm_enrichment_logs (status);

CREATE INDEX ix_crm_enrichment_logs_entity_id ON crm_enrichment_logs (entity_id);

CREATE INDEX ix_crm_enrichment_logs_provider ON crm_enrichment_logs (provider);

CREATE INDEX ix_crm_enrichment_logs_organization_id ON crm_enrichment_logs (organization_id);

CREATE INDEX ix_crm_enrichment_logs_entity_type ON crm_enrichment_logs (entity_type);

CREATE INDEX ix_crm_enrichment_logs_created_at ON crm_enrichment_logs (created_at);

CREATE TABLE crm_email_templates (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	subject VARCHAR(220) NOT NULL, 
	body TEXT NOT NULL, 
	entity_type VARCHAR(40), 
	is_active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_email_template_org_name UNIQUE (organization_id, name)
);

CREATE INDEX ix_crm_email_templates_name ON crm_email_templates (name);

CREATE INDEX ix_crm_email_templates_is_active ON crm_email_templates (is_active);

CREATE INDEX ix_crm_email_templates_organization_id ON crm_email_templates (organization_id);

CREATE INDEX ix_crm_email_templates_entity_type ON crm_email_templates (entity_type);

CREATE INDEX ix_crm_email_templates_id ON crm_email_templates (id);

CREATE TABLE crm_message_templates (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	body TEXT NOT NULL, 
	entity_type VARCHAR(40), 
	is_active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_message_template_org_name_channel UNIQUE (organization_id, name, channel), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_message_templates_organization_id ON crm_message_templates (organization_id);

CREATE INDEX ix_crm_message_templates_name ON crm_message_templates (name);

CREATE INDEX ix_crm_message_templates_id ON crm_message_templates (id);

CREATE INDEX ix_crm_message_templates_is_active ON crm_message_templates (is_active);

CREATE INDEX ix_crm_message_templates_channel ON crm_message_templates (channel);

CREATE INDEX ix_crm_message_templates_entity_type ON crm_message_templates (entity_type);

CREATE TABLE calendar_integrations (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	user_id INTEGER NOT NULL, 
	provider VARCHAR(40) NOT NULL, 
	access_token_encrypted TEXT, 
	refresh_token_encrypted TEXT, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	is_active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_calendar_integrations_is_active ON calendar_integrations (is_active);

CREATE INDEX ix_calendar_integrations_provider ON calendar_integrations (provider);

CREATE INDEX ix_calendar_integrations_created_at ON calendar_integrations (created_at);

CREATE INDEX ix_calendar_integrations_organization_id ON calendar_integrations (organization_id);

CREATE INDEX ix_calendar_integrations_user_id ON calendar_integrations (user_id);

CREATE INDEX ix_calendar_integrations_id ON calendar_integrations (id);

CREATE TABLE crm_campaigns (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	campaign_type VARCHAR(50) NOT NULL, 
	status VARCHAR(30), 
	start_date DATE, 
	end_date DATE, 
	budget_amount NUMERIC(12, 2), 
	actual_cost NUMERIC(12, 2), 
	expected_revenue NUMERIC(12, 2), 
	description TEXT, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_campaigns_id ON crm_campaigns (id);

CREATE INDEX ix_crm_campaigns_organization_id ON crm_campaigns (organization_id);

CREATE INDEX ix_crm_campaigns_status ON crm_campaigns (status);

CREATE INDEX ix_crm_campaigns_campaign_type ON crm_campaigns (campaign_type);

CREATE INDEX ix_crm_campaigns_owner_user_id ON crm_campaigns (owner_user_id);

CREATE INDEX ix_crm_campaigns_name ON crm_campaigns (name);

CREATE TABLE crm_territories (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	manager_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	code VARCHAR(40), 
	region VARCHAR(120), 
	country VARCHAR(100), 
	state VARCHAR(100), 
	city VARCHAR(100), 
	product_line VARCHAR(120), 
	service_line VARCHAR(120), 
	description TEXT, 
	rules_json JSON, 
	priority INTEGER, 
	is_active BOOLEAN, 
	active BOOLEAN, 
	status VARCHAR(30), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(manager_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_territory_org_name UNIQUE (organization_id, name)
);

CREATE INDEX ix_crm_territories_name ON crm_territories (name);

CREATE INDEX ix_crm_territories_region ON crm_territories (region);

CREATE INDEX ix_crm_territories_product_line ON crm_territories (product_line);

CREATE INDEX ix_crm_territories_is_active ON crm_territories (is_active);

CREATE INDEX ix_crm_territories_organization_id ON crm_territories (organization_id);

CREATE INDEX ix_crm_territories_owner_user_id ON crm_territories (owner_user_id);

CREATE INDEX ix_crm_territories_state ON crm_territories (state);

CREATE INDEX ix_crm_territories_service_line ON crm_territories (service_line);

CREATE INDEX ix_crm_territories_active ON crm_territories (active);

CREATE INDEX ix_crm_territories_id ON crm_territories (id);

CREATE INDEX ix_crm_territories_manager_id ON crm_territories (manager_id);

CREATE INDEX ix_crm_territories_code ON crm_territories (code);

CREATE INDEX ix_crm_territories_city ON crm_territories (city);

CREATE INDEX ix_crm_territories_priority ON crm_territories (priority);

CREATE INDEX ix_crm_territories_status ON crm_territories (status);

CREATE TABLE crm_teams (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	team_type VARCHAR(60), 
	description TEXT, 
	status VARCHAR(30), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_crm_team_org_name UNIQUE (organization_id, name), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_teams_organization_id ON crm_teams (organization_id);

CREATE INDEX ix_crm_teams_status ON crm_teams (status);

CREATE INDEX ix_crm_teams_owner_user_id ON crm_teams (owner_user_id);

CREATE INDEX ix_crm_teams_team_type ON crm_teams (team_type);

CREATE INDEX ix_crm_teams_id ON crm_teams (id);

CREATE INDEX ix_crm_teams_name ON crm_teams (name);

CREATE TABLE crm_sales_targets (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	period_type VARCHAR(20) NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	target_owner_type VARCHAR(20) NOT NULL, 
	target_owner_id INTEGER, 
	target_amount NUMERIC(14, 2) NOT NULL, 
	currency VARCHAR(10), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_sales_targets_id ON crm_sales_targets (id);

CREATE INDEX ix_crm_sales_targets_target_owner_type ON crm_sales_targets (target_owner_type);

CREATE INDEX ix_crm_sales_targets_currency ON crm_sales_targets (currency);

CREATE INDEX ix_crm_sales_targets_organization_id ON crm_sales_targets (organization_id);

CREATE INDEX ix_crm_sales_targets_period_start ON crm_sales_targets (period_start);

CREATE INDEX ix_crm_sales_targets_period_end ON crm_sales_targets (period_end);

CREATE INDEX ix_crm_sales_targets_period_type ON crm_sales_targets (period_type);

CREATE INDEX ix_crm_sales_targets_target_owner_id ON crm_sales_targets (target_owner_id);

CREATE TABLE crm_lost_reasons (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	description TEXT, 
	active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_lost_reason_org_name UNIQUE (organization_id, name), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_lost_reasons_name ON crm_lost_reasons (name);

CREATE INDEX ix_crm_lost_reasons_organization_id ON crm_lost_reasons (organization_id);

CREATE INDEX ix_crm_lost_reasons_active ON crm_lost_reasons (active);

CREATE INDEX ix_crm_lost_reasons_id ON crm_lost_reasons (id);

CREATE TABLE crm_custom_fields (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	entity VARCHAR(80) NOT NULL, 
	field_key VARCHAR(100) NOT NULL, 
	field_name VARCHAR(160), 
	label VARCHAR(160) NOT NULL, 
	field_type VARCHAR(40), 
	options_json JSON, 
	is_required BOOLEAN, 
	is_unique BOOLEAN, 
	is_visible BOOLEAN, 
	is_filterable BOOLEAN, 
	is_active BOOLEAN, 
	position INTEGER, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_custom_field_org_entity_key UNIQUE (organization_id, entity, field_key)
);

CREATE INDEX ix_crm_custom_fields_organization_id ON crm_custom_fields (organization_id);

CREATE INDEX ix_crm_custom_fields_field_type ON crm_custom_fields (field_type);

CREATE INDEX ix_crm_custom_fields_is_filterable ON crm_custom_fields (is_filterable);

CREATE INDEX ix_crm_custom_fields_id ON crm_custom_fields (id);

CREATE INDEX ix_crm_custom_fields_entity ON crm_custom_fields (entity);

CREATE INDEX ix_crm_custom_fields_is_unique ON crm_custom_fields (is_unique);

CREATE INDEX ix_crm_custom_fields_is_active ON crm_custom_fields (is_active);

CREATE INDEX ix_crm_custom_fields_field_key ON crm_custom_fields (field_key);

CREATE INDEX ix_crm_custom_fields_is_visible ON crm_custom_fields (is_visible);

CREATE TABLE crm_webhooks (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	url VARCHAR(500) NOT NULL, 
	secret VARCHAR(160) NOT NULL, 
	events JSON, 
	is_active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_webhooks_name ON crm_webhooks (name);

CREATE INDEX ix_crm_webhooks_created_at ON crm_webhooks (created_at);

CREATE INDEX ix_crm_webhooks_organization_id ON crm_webhooks (organization_id);

CREATE INDEX ix_crm_webhooks_is_active ON crm_webhooks (is_active);

CREATE INDEX ix_crm_webhooks_id ON crm_webhooks (id);

CREATE TABLE crm_approval_workflows (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	entity_type VARCHAR(40) NOT NULL, 
	trigger_type VARCHAR(80) NOT NULL, 
	conditions JSON, 
	is_active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_approval_workflows_id ON crm_approval_workflows (id);

CREATE INDEX ix_crm_approval_workflows_is_active ON crm_approval_workflows (is_active);

CREATE INDEX ix_crm_approval_workflows_name ON crm_approval_workflows (name);

CREATE INDEX ix_crm_approval_workflows_trigger_type ON crm_approval_workflows (trigger_type);

CREATE INDEX ix_crm_approval_workflows_organization_id ON crm_approval_workflows (organization_id);

CREATE INDEX ix_crm_approval_workflows_entity_type ON crm_approval_workflows (entity_type);

CREATE TABLE pms_workspace_members (
	id SERIAL NOT NULL, 
	workspace_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES pms_workspaces (id) ON DELETE CASCADE, 
	CONSTRAINT uq_pms_workspace_member UNIQUE (workspace_id, user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_workspace_members_user_id ON pms_workspace_members (user_id);

CREATE INDEX ix_pms_workspace_members_workspace_id ON pms_workspace_members (workspace_id);

CREATE TABLE pms_timesheets (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	user_id INTEGER NOT NULL, 
	week_start_date DATE NOT NULL, 
	status VARCHAR(30), 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	approved_by_user_id INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	rejection_reason TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pms_timesheet_user_week UNIQUE (organization_id, user_id, week_start_date), 
	FOREIGN KEY(approved_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_timesheets_organization_id ON pms_timesheets (organization_id);

CREATE INDEX ix_pms_timesheets_approved_by_user_id ON pms_timesheets (approved_by_user_id);

CREATE INDEX ix_pms_timesheets_id ON pms_timesheets (id);

CREATE INDEX ix_pms_timesheets_status ON pms_timesheets (status);

CREATE INDEX ix_pms_timesheets_user_id ON pms_timesheets (user_id);

CREATE INDEX ix_pms_timesheets_week_start_date ON pms_timesheets (week_start_date);

CREATE TABLE pms_user_capacity (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	user_id INTEGER NOT NULL, 
	week_start_date DATE NOT NULL, 
	capacity_hours NUMERIC(8, 2) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pms_user_capacity_week UNIQUE (organization_id, user_id, week_start_date), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_user_capacity_id ON pms_user_capacity (id);

CREATE INDEX ix_pms_user_capacity_organization_id ON pms_user_capacity (organization_id);

CREATE INDEX ix_pms_user_capacity_user_id ON pms_user_capacity (user_id);

CREATE INDEX ix_pms_user_capacity_week_start_date ON pms_user_capacity (week_start_date);

CREATE TABLE srm_sales_orders (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	order_number VARCHAR(80) NOT NULL, 
	status VARCHAR(40), 
	crm_deal_id INTEGER, 
	crm_quote_id INTEGER, 
	crm_company_id INTEGER, 
	crm_contact_id INTEGER, 
	customer_id INTEGER, 
	assigned_user_id INTEGER, 
	created_by INTEGER, 
	approved_by INTEGER, 
	approval_request_id INTEGER, 
	title VARCHAR(220) NOT NULL, 
	currency VARCHAR(10), 
	subtotal NUMERIC(14, 2), 
	discount_amount NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	total_amount NUMERIC(14, 2), 
	expected_start_date DATE, 
	expected_end_date DATE, 
	terms TEXT, 
	metadata_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_sales_order_org_number UNIQUE (organization_id, order_number), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_sales_orders_organization_id ON srm_sales_orders (organization_id);

CREATE INDEX ix_srm_sales_orders_order_number ON srm_sales_orders (order_number);

CREATE INDEX ix_srm_sales_orders_crm_company_id ON srm_sales_orders (crm_company_id);

CREATE INDEX ix_srm_sales_orders_customer_id ON srm_sales_orders (customer_id);

CREATE INDEX ix_srm_sales_orders_approved_by ON srm_sales_orders (approved_by);

CREATE INDEX ix_srm_sales_orders_id ON srm_sales_orders (id);

CREATE INDEX ix_srm_sales_orders_crm_quote_id ON srm_sales_orders (crm_quote_id);

CREATE INDEX ix_srm_sales_orders_crm_contact_id ON srm_sales_orders (crm_contact_id);

CREATE INDEX ix_srm_sales_orders_assigned_user_id ON srm_sales_orders (assigned_user_id);

CREATE INDEX ix_srm_sales_orders_approval_request_id ON srm_sales_orders (approval_request_id);

CREATE INDEX ix_srm_sales_orders_status ON srm_sales_orders (status);

CREATE INDEX ix_srm_sales_orders_crm_deal_id ON srm_sales_orders (crm_deal_id);

CREATE INDEX ix_srm_sales_orders_created_by ON srm_sales_orders (created_by);

CREATE INDEX ix_srm_sales_orders_created_at ON srm_sales_orders (created_at);

CREATE TABLE srm_pos_sessions (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	session_number VARCHAR(80) NOT NULL, 
	status VARCHAR(40), 
	branch VARCHAR(160), 
	register_name VARCHAR(160), 
	cashier_user_id INTEGER, 
	opening_cash NUMERIC(14, 2), 
	expected_cash NUMERIC(14, 2), 
	counted_cash NUMERIC(14, 2), 
	cash_variance NUMERIC(14, 2), 
	opened_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	closed_at TIMESTAMP WITH TIME ZONE, 
	notes TEXT, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_pos_session_org_number UNIQUE (organization_id, session_number), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(cashier_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_pos_sessions_status ON srm_pos_sessions (status);

CREATE INDEX ix_srm_pos_sessions_opened_at ON srm_pos_sessions (opened_at);

CREATE INDEX ix_srm_pos_sessions_created_at ON srm_pos_sessions (created_at);

CREATE INDEX ix_srm_pos_sessions_organization_id ON srm_pos_sessions (organization_id);

CREATE INDEX ix_srm_pos_sessions_session_number ON srm_pos_sessions (session_number);

CREATE INDEX ix_srm_pos_sessions_closed_at ON srm_pos_sessions (closed_at);

CREATE INDEX ix_srm_pos_sessions_id ON srm_pos_sessions (id);

CREATE INDEX ix_srm_pos_sessions_cashier_user_id ON srm_pos_sessions (cashier_user_id);

CREATE INDEX ix_srm_pos_sessions_created_by ON srm_pos_sessions (created_by);

CREATE TABLE srm_product_categories (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	parent_category_id INTEGER, 
	category_code VARCHAR(80) NOT NULL, 
	category_name VARCHAR(180) NOT NULL, 
	description TEXT, 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_category_id) REFERENCES srm_product_categories (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_product_category_org_code UNIQUE (organization_id, category_code)
);

CREATE INDEX ix_srm_product_categories_id ON srm_product_categories (id);

CREATE INDEX ix_srm_product_categories_active ON srm_product_categories (active);

CREATE INDEX ix_srm_product_categories_created_at ON srm_product_categories (created_at);

CREATE INDEX ix_srm_product_categories_parent_category_id ON srm_product_categories (parent_category_id);

CREATE INDEX ix_srm_product_categories_category_name ON srm_product_categories (category_name);

CREATE INDEX ix_srm_product_categories_organization_id ON srm_product_categories (organization_id);

CREATE INDEX ix_srm_product_categories_category_code ON srm_product_categories (category_code);

CREATE INDEX ix_srm_product_categories_created_by ON srm_product_categories (created_by);

CREATE TABLE srm_warehouses (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	warehouse_code VARCHAR(80) NOT NULL, 
	warehouse_name VARCHAR(180) NOT NULL, 
	branch VARCHAR(160), 
	address TEXT, 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_warehouse_org_code UNIQUE (organization_id, warehouse_code), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_warehouses_created_by ON srm_warehouses (created_by);

CREATE INDEX ix_srm_warehouses_warehouse_code ON srm_warehouses (warehouse_code);

CREATE INDEX ix_srm_warehouses_warehouse_name ON srm_warehouses (warehouse_name);

CREATE INDEX ix_srm_warehouses_created_at ON srm_warehouses (created_at);

CREATE INDEX ix_srm_warehouses_id ON srm_warehouses (id);

CREATE INDEX ix_srm_warehouses_active ON srm_warehouses (active);

CREATE INDEX ix_srm_warehouses_organization_id ON srm_warehouses (organization_id);

CREATE INDEX ix_srm_warehouses_branch ON srm_warehouses (branch);

CREATE TABLE srm_purchase_orders (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	po_number VARCHAR(80) NOT NULL, 
	vendor_id INTEGER, 
	vendor_name VARCHAR(220), 
	status VARCHAR(40), 
	order_date DATE NOT NULL, 
	expected_date DATE, 
	subtotal NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	total_amount NUMERIC(14, 2), 
	notes TEXT, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_purchase_order_org_number UNIQUE (organization_id, po_number)
);

CREATE INDEX ix_srm_purchase_orders_id ON srm_purchase_orders (id);

CREATE INDEX ix_srm_purchase_orders_vendor_name ON srm_purchase_orders (vendor_name);

CREATE INDEX ix_srm_purchase_orders_order_date ON srm_purchase_orders (order_date);

CREATE INDEX ix_srm_purchase_orders_created_at ON srm_purchase_orders (created_at);

CREATE INDEX ix_srm_purchase_orders_po_number ON srm_purchase_orders (po_number);

CREATE INDEX ix_srm_purchase_orders_vendor_id ON srm_purchase_orders (vendor_id);

CREATE INDEX ix_srm_purchase_orders_expected_date ON srm_purchase_orders (expected_date);

CREATE INDEX ix_srm_purchase_orders_organization_id ON srm_purchase_orders (organization_id);

CREATE INDEX ix_srm_purchase_orders_status ON srm_purchase_orders (status);

CREATE INDEX ix_srm_purchase_orders_created_by ON srm_purchase_orders (created_by);

CREATE TABLE srm_price_lists (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	price_list_code VARCHAR(80) NOT NULL, 
	price_list_name VARCHAR(180) NOT NULL, 
	channel VARCHAR(80), 
	customer_type VARCHAR(80), 
	currency VARCHAR(10), 
	effective_from DATE, 
	effective_to DATE, 
	priority INTEGER, 
	active BOOLEAN, 
	notes TEXT, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_price_list_org_code UNIQUE (organization_id, price_list_code)
);

CREATE INDEX ix_srm_price_lists_organization_id ON srm_price_lists (organization_id);

CREATE INDEX ix_srm_price_lists_price_list_name ON srm_price_lists (price_list_name);

CREATE INDEX ix_srm_price_lists_effective_to ON srm_price_lists (effective_to);

CREATE INDEX ix_srm_price_lists_created_by ON srm_price_lists (created_by);

CREATE INDEX ix_srm_price_lists_id ON srm_price_lists (id);

CREATE INDEX ix_srm_price_lists_price_list_code ON srm_price_lists (price_list_code);

CREATE INDEX ix_srm_price_lists_customer_type ON srm_price_lists (customer_type);

CREATE INDEX ix_srm_price_lists_priority ON srm_price_lists (priority);

CREATE INDEX ix_srm_price_lists_created_at ON srm_price_lists (created_at);

CREATE INDEX ix_srm_price_lists_channel ON srm_price_lists (channel);

CREATE INDEX ix_srm_price_lists_effective_from ON srm_price_lists (effective_from);

CREATE INDEX ix_srm_price_lists_active ON srm_price_lists (active);

CREATE TABLE srm_receipts (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	receipt_number VARCHAR(80) NOT NULL, 
	customer_id INTEGER, 
	status VARCHAR(40), 
	receipt_date DATE, 
	payment_method VARCHAR(60), 
	reference_number VARCHAR(120), 
	currency VARCHAR(10), 
	amount NUMERIC(14, 2), 
	unallocated_amount NUMERIC(14, 2), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_receipt_org_number UNIQUE (organization_id, receipt_number)
);

CREATE INDEX ix_srm_receipts_created_at ON srm_receipts (created_at);

CREATE INDEX ix_srm_receipts_organization_id ON srm_receipts (organization_id);

CREATE INDEX ix_srm_receipts_receipt_date ON srm_receipts (receipt_date);

CREATE INDEX ix_srm_receipts_id ON srm_receipts (id);

CREATE INDEX ix_srm_receipts_customer_id ON srm_receipts (customer_id);

CREATE INDEX ix_srm_receipts_status ON srm_receipts (status);

CREATE INDEX ix_srm_receipts_receipt_number ON srm_receipts (receipt_number);

CREATE TABLE srm_audit_logs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	actor_user_id INTEGER, 
	before_json JSON, 
	after_json JSON, 
	ip_address VARCHAR(80), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_audit_logs_entity_id ON srm_audit_logs (entity_id);

CREATE INDEX ix_srm_audit_logs_action ON srm_audit_logs (action);

CREATE INDEX ix_srm_audit_logs_id ON srm_audit_logs (id);

CREATE INDEX ix_srm_audit_logs_entity_type ON srm_audit_logs (entity_type);

CREATE INDEX ix_srm_audit_logs_created_at ON srm_audit_logs (created_at);

CREATE INDEX ix_srm_audit_logs_organization_id ON srm_audit_logs (organization_id);

CREATE INDEX ix_srm_audit_logs_actor_user_id ON srm_audit_logs (actor_user_id);

CREATE TABLE srm_settings (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	key VARCHAR(120) NOT NULL, 
	value_json JSON, 
	is_active BOOLEAN, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_setting_org_key UNIQUE (organization_id, key), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_settings_is_active ON srm_settings (is_active);

CREATE INDEX ix_srm_settings_organization_id ON srm_settings (organization_id);

CREATE INDEX ix_srm_settings_key ON srm_settings (key);

CREATE INDEX ix_srm_settings_id ON srm_settings (id);

CREATE TABLE fam_opening_balances (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	financial_year_id INTEGER NOT NULL, 
	ledger_id INTEGER NOT NULL, 
	debit_amount NUMERIC(14, 2), 
	credit_amount NUMERIC(14, 2), 
	narration TEXT, 
	posted BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_fam_opening_balance UNIQUE (company_id, financial_year_id, ledger_id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(financial_year_id) REFERENCES fam_financial_years (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_opening_balances_financial_year_id ON fam_opening_balances (financial_year_id);

CREATE INDEX ix_fam_opening_balances_posted ON fam_opening_balances (posted);

CREATE INDEX ix_fam_opening_balances_id ON fam_opening_balances (id);

CREATE INDEX ix_fam_opening_balances_ledger_id ON fam_opening_balances (ledger_id);

CREATE INDEX ix_fam_opening_balances_company_id ON fam_opening_balances (company_id);

CREATE TABLE fam_audit_logs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	module_name VARCHAR(80), 
	record_type VARCHAR(80) NOT NULL, 
	record_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	old_value_json JSON, 
	new_value_json JSON, 
	performed_by INTEGER, 
	performed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	ip_address VARCHAR(80), 
	user_agent TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(performed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_audit_logs_id ON fam_audit_logs (id);

CREATE INDEX ix_fam_audit_logs_record_id ON fam_audit_logs (record_id);

CREATE INDEX ix_fam_audit_logs_performed_by ON fam_audit_logs (performed_by);

CREATE INDEX ix_fam_audit_logs_module_name ON fam_audit_logs (module_name);

CREATE INDEX ix_fam_audit_logs_record_type ON fam_audit_logs (record_type);

CREATE INDEX ix_fam_audit_logs_performed_at ON fam_audit_logs (performed_at);

CREATE INDEX ix_fam_audit_logs_company_id ON fam_audit_logs (company_id);

CREATE INDEX ix_fam_audit_logs_action ON fam_audit_logs (action);

CREATE TABLE fam_vouchers (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	financial_year_id INTEGER NOT NULL, 
	accounting_period_id INTEGER, 
	branch_id INTEGER, 
	voucher_type_id INTEGER NOT NULL, 
	voucher_number VARCHAR(80) NOT NULL, 
	voucher_date DATE NOT NULL, 
	reference_number VARCHAR(120), 
	reference_date DATE, 
	narration TEXT, 
	total_debit NUMERIC(14, 2), 
	total_credit NUMERIC(14, 2), 
	status VARCHAR(20), 
	source_module VARCHAR(40), 
	source_record_type VARCHAR(80), 
	source_record_id VARCHAR(120), 
	posted_by INTEGER, 
	posted_at TIMESTAMP WITH TIME ZONE, 
	cancelled_by INTEGER, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	cancellation_reason TEXT, 
	reversed_voucher_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reversed_voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_voucher_company_number UNIQUE (company_id, voucher_number), 
	FOREIGN KEY(posted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES fam_branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(financial_year_id) REFERENCES fam_financial_years (id) ON DELETE RESTRICT, 
	FOREIGN KEY(accounting_period_id) REFERENCES fam_accounting_periods (id) ON DELETE RESTRICT, 
	FOREIGN KEY(cancelled_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_type_id) REFERENCES fam_voucher_types (id) ON DELETE RESTRICT
);

CREATE INDEX ix_fam_vouchers_posted_by ON fam_vouchers (posted_by);

CREATE INDEX ix_fam_vouchers_reversed_voucher_id ON fam_vouchers (reversed_voucher_id);

CREATE INDEX ix_fam_vouchers_company_id ON fam_vouchers (company_id);

CREATE INDEX ix_fam_vouchers_voucher_type_id ON fam_vouchers (voucher_type_id);

CREATE INDEX ix_fam_vouchers_reference_number ON fam_vouchers (reference_number);

CREATE INDEX ix_fam_vouchers_source_record_type ON fam_vouchers (source_record_type);

CREATE INDEX ix_fam_vouchers_posted_at ON fam_vouchers (posted_at);

CREATE INDEX ix_fam_vouchers_id ON fam_vouchers (id);

CREATE INDEX ix_fam_vouchers_branch_id ON fam_vouchers (branch_id);

CREATE INDEX ix_fam_vouchers_voucher_number ON fam_vouchers (voucher_number);

CREATE INDEX ix_fam_vouchers_status ON fam_vouchers (status);

CREATE INDEX ix_fam_vouchers_source_record_id ON fam_vouchers (source_record_id);

CREATE INDEX ix_fam_vouchers_cancelled_by ON fam_vouchers (cancelled_by);

CREATE INDEX ix_fam_vouchers_financial_year_id ON fam_vouchers (financial_year_id);

CREATE INDEX ix_fam_vouchers_accounting_period_id ON fam_vouchers (accounting_period_id);

CREATE INDEX ix_fam_vouchers_voucher_date ON fam_vouchers (voucher_date);

CREATE INDEX ix_fam_vouchers_source_module ON fam_vouchers (source_module);

CREATE TABLE fam_party_contacts (
	id SERIAL NOT NULL, 
	party_id INTEGER NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	email VARCHAR(180), 
	phone VARCHAR(60), 
	designation VARCHAR(120), 
	is_primary BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(party_id) REFERENCES fam_parties (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_party_contacts_party_id ON fam_party_contacts (party_id);

CREATE INDEX ix_fam_party_contacts_is_primary ON fam_party_contacts (is_primary);

CREATE INDEX ix_fam_party_contacts_id ON fam_party_contacts (id);

CREATE TABLE fam_party_credit_terms (
	id SERIAL NOT NULL, 
	party_id INTEGER NOT NULL, 
	terms_name VARCHAR(120) NOT NULL, 
	days INTEGER, 
	discount_percentage NUMERIC(6, 2), 
	active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(party_id) REFERENCES fam_parties (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_party_credit_terms_party_id ON fam_party_credit_terms (party_id);

CREATE INDEX ix_fam_party_credit_terms_active ON fam_party_credit_terms (active);

CREATE INDEX ix_fam_party_credit_terms_id ON fam_party_credit_terms (id);

CREATE TABLE fam_bank_statements (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	bank_account_id INTEGER NOT NULL, 
	statement_period_start DATE NOT NULL, 
	statement_period_end DATE NOT NULL, 
	imported_file_name VARCHAR(220) NOT NULL, 
	imported_file_hash VARCHAR(128) NOT NULL, 
	status VARCHAR(30), 
	imported_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(imported_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(bank_account_id) REFERENCES fam_bank_accounts (id) ON DELETE CASCADE, 
	CONSTRAINT uq_fam_bank_statement_file_hash UNIQUE (company_id, bank_account_id, imported_file_hash)
);

CREATE INDEX ix_fam_bank_statements_statement_period_end ON fam_bank_statements (statement_period_end);

CREATE INDEX ix_fam_bank_statements_created_at ON fam_bank_statements (created_at);

CREATE INDEX ix_fam_bank_statements_company_id ON fam_bank_statements (company_id);

CREATE INDEX ix_fam_bank_statements_bank_account_id ON fam_bank_statements (bank_account_id);

CREATE INDEX ix_fam_bank_statements_status ON fam_bank_statements (status);

CREATE INDEX ix_fam_bank_statements_id ON fam_bank_statements (id);

CREATE INDEX ix_fam_bank_statements_imported_file_hash ON fam_bank_statements (imported_file_hash);

CREATE INDEX ix_fam_bank_statements_imported_by ON fam_bank_statements (imported_by);

CREATE INDEX ix_fam_bank_statements_statement_period_start ON fam_bank_statements (statement_period_start);

CREATE TABLE fam_gst_return_periods (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	period_month INTEGER NOT NULL, 
	period_year INTEGER NOT NULL, 
	return_type VARCHAR(20) NOT NULL, 
	status VARCHAR(30), 
	prepared_by INTEGER, 
	prepared_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(prepared_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_gst_return_period UNIQUE (company_id, period_month, period_year, return_type)
);

CREATE INDEX ix_fam_gst_return_periods_period_month ON fam_gst_return_periods (period_month);

CREATE INDEX ix_fam_gst_return_periods_prepared_by ON fam_gst_return_periods (prepared_by);

CREATE INDEX ix_fam_gst_return_periods_status ON fam_gst_return_periods (status);

CREATE INDEX ix_fam_gst_return_periods_prepared_at ON fam_gst_return_periods (prepared_at);

CREATE INDEX ix_fam_gst_return_periods_period_year ON fam_gst_return_periods (period_year);

CREATE INDEX ix_fam_gst_return_periods_return_type ON fam_gst_return_periods (return_type);

CREATE INDEX ix_fam_gst_return_periods_created_at ON fam_gst_return_periods (created_at);

CREATE INDEX ix_fam_gst_return_periods_company_id ON fam_gst_return_periods (company_id);

CREATE INDEX ix_fam_gst_return_periods_id ON fam_gst_return_periods (id);

CREATE TABLE fam_gst_audit_logs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	record_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	old_value_json JSON, 
	new_value_json JSON, 
	performed_by INTEGER, 
	performed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(performed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_gst_audit_logs_company_id ON fam_gst_audit_logs (company_id);

CREATE INDEX ix_fam_gst_audit_logs_performed_by ON fam_gst_audit_logs (performed_by);

CREATE INDEX ix_fam_gst_audit_logs_id ON fam_gst_audit_logs (id);

CREATE INDEX ix_fam_gst_audit_logs_record_id ON fam_gst_audit_logs (record_id);

CREATE INDEX ix_fam_gst_audit_logs_action ON fam_gst_audit_logs (action);

CREATE INDEX ix_fam_gst_audit_logs_record_type ON fam_gst_audit_logs (record_type);

CREATE INDEX ix_fam_gst_audit_logs_performed_at ON fam_gst_audit_logs (performed_at);

CREATE TABLE fam_purchase_audit_logs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	record_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	old_value_json JSON, 
	new_value_json JSON, 
	performed_by INTEGER, 
	performed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(performed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_purchase_audit_logs_id ON fam_purchase_audit_logs (id);

CREATE INDEX ix_fam_purchase_audit_logs_record_type ON fam_purchase_audit_logs (record_type);

CREATE INDEX ix_fam_purchase_audit_logs_performed_at ON fam_purchase_audit_logs (performed_at);

CREATE INDEX ix_fam_purchase_audit_logs_company_id ON fam_purchase_audit_logs (company_id);

CREATE INDEX ix_fam_purchase_audit_logs_performed_by ON fam_purchase_audit_logs (performed_by);

CREATE INDEX ix_fam_purchase_audit_logs_record_id ON fam_purchase_audit_logs (record_id);

CREATE INDEX ix_fam_purchase_audit_logs_action ON fam_purchase_audit_logs (action);

CREATE TABLE fam_stock_items (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	stock_group_id INTEGER, 
	unit_id INTEGER, 
	default_warehouse_id INTEGER, 
	inventory_ledger_id INTEGER, 
	purchase_ledger_id INTEGER, 
	sales_ledger_id INTEGER, 
	cogs_ledger_id INTEGER, 
	adjustment_gain_ledger_id INTEGER, 
	adjustment_loss_ledger_id INTEGER, 
	grni_ledger_id INTEGER, 
	cost_center_id INTEGER, 
	branch_id INTEGER, 
	valuation_method VARCHAR(40), 
	sku VARCHAR(80) NOT NULL, 
	item_name VARCHAR(220) NOT NULL, 
	barcode VARCHAR(120), 
	description TEXT, 
	hsn_code VARCHAR(30), 
	gst_rate_id INTEGER, 
	purchase_rate NUMERIC(14, 2), 
	sales_rate NUMERIC(14, 2), 
	current_quantity NUMERIC(14, 3), 
	average_cost NUMERIC(14, 4), 
	reorder_level NUMERIC(14, 3), 
	min_stock NUMERIC(14, 3), 
	max_stock NUMERIC(14, 3), 
	track_inventory BOOLEAN, 
	batch_tracking BOOLEAN, 
	serial_tracking BOOLEAN, 
	expiry_tracking BOOLEAN, 
	active BOOLEAN, 
	source_app_reference VARCHAR(120), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(adjustment_gain_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES fam_branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(sales_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(grni_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(inventory_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(unit_id) REFERENCES fam_units_of_measure (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_stock_item_company_sku UNIQUE (company_id, sku), 
	FOREIGN KEY(adjustment_loss_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(gst_rate_id) REFERENCES fam_gst_rates (id) ON DELETE SET NULL, 
	FOREIGN KEY(cogs_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(cost_center_id) REFERENCES fam_cost_centers (id) ON DELETE SET NULL, 
	FOREIGN KEY(purchase_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(default_warehouse_id) REFERENCES fam_warehouses (id) ON DELETE SET NULL, 
	FOREIGN KEY(stock_group_id) REFERENCES fam_stock_groups (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_stock_items_inventory_ledger_id ON fam_stock_items (inventory_ledger_id);

CREATE INDEX ix_fam_stock_items_barcode ON fam_stock_items (barcode);

CREATE INDEX ix_fam_stock_items_purchase_ledger_id ON fam_stock_items (purchase_ledger_id);

CREATE INDEX ix_fam_stock_items_hsn_code ON fam_stock_items (hsn_code);

CREATE INDEX ix_fam_stock_items_sales_ledger_id ON fam_stock_items (sales_ledger_id);

CREATE INDEX ix_fam_stock_items_gst_rate_id ON fam_stock_items (gst_rate_id);

CREATE INDEX ix_fam_stock_items_cogs_ledger_id ON fam_stock_items (cogs_ledger_id);

CREATE INDEX ix_fam_stock_items_track_inventory ON fam_stock_items (track_inventory);

CREATE INDEX ix_fam_stock_items_adjustment_gain_ledger_id ON fam_stock_items (adjustment_gain_ledger_id);

CREATE INDEX ix_fam_stock_items_active ON fam_stock_items (active);

CREATE INDEX ix_fam_stock_items_adjustment_loss_ledger_id ON fam_stock_items (adjustment_loss_ledger_id);

CREATE INDEX ix_fam_stock_items_source_app_reference ON fam_stock_items (source_app_reference);

CREATE INDEX ix_fam_stock_items_grni_ledger_id ON fam_stock_items (grni_ledger_id);

CREATE INDEX ix_fam_stock_items_created_by ON fam_stock_items (created_by);

CREATE INDEX ix_fam_stock_items_id ON fam_stock_items (id);

CREATE INDEX ix_fam_stock_items_cost_center_id ON fam_stock_items (cost_center_id);

CREATE INDEX ix_fam_stock_items_created_at ON fam_stock_items (created_at);

CREATE INDEX ix_fam_stock_items_unit_id ON fam_stock_items (unit_id);

CREATE INDEX ix_fam_stock_items_branch_id ON fam_stock_items (branch_id);

CREATE INDEX ix_fam_stock_items_company_id ON fam_stock_items (company_id);

CREATE INDEX ix_fam_stock_items_valuation_method ON fam_stock_items (valuation_method);

CREATE INDEX ix_fam_stock_items_default_warehouse_id ON fam_stock_items (default_warehouse_id);

CREATE INDEX ix_fam_stock_items_sku ON fam_stock_items (sku);

CREATE INDEX ix_fam_stock_items_stock_group_id ON fam_stock_items (stock_group_id);

CREATE INDEX ix_fam_stock_items_item_name ON fam_stock_items (item_name);

CREATE TABLE fam_inventory_ai_logs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	prompt TEXT NOT NULL, 
	context_json JSON, 
	response_json JSON, 
	confidence NUMERIC(7, 3), 
	evidence_json JSON, 
	provider VARCHAR(80), 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_inventory_ai_logs_created_by ON fam_inventory_ai_logs (created_by);

CREATE INDEX ix_fam_inventory_ai_logs_created_at ON fam_inventory_ai_logs (created_at);

CREATE INDEX ix_fam_inventory_ai_logs_status ON fam_inventory_ai_logs (status);

CREATE INDEX ix_fam_inventory_ai_logs_company_id ON fam_inventory_ai_logs (company_id);

CREATE INDEX ix_fam_inventory_ai_logs_id ON fam_inventory_ai_logs (id);

CREATE TABLE fam_inventory_reports (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	report_type VARCHAR(80) NOT NULL, 
	filters_json JSON, 
	result_json JSON, 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_inventory_reports_company_id ON fam_inventory_reports (company_id);

CREATE INDEX ix_fam_inventory_reports_generated_by ON fam_inventory_reports (generated_by);

CREATE INDEX ix_fam_inventory_reports_generated_at ON fam_inventory_reports (generated_at);

CREATE INDEX ix_fam_inventory_reports_report_type ON fam_inventory_reports (report_type);

CREATE INDEX ix_fam_inventory_reports_id ON fam_inventory_reports (id);

CREATE TABLE fam_inventory_control_settings (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	setting_key VARCHAR(120) NOT NULL, 
	setting_value_json JSON, 
	description TEXT, 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_inventory_control_setting UNIQUE (company_id, setting_key), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_inventory_control_settings_setting_key ON fam_inventory_control_settings (setting_key);

CREATE INDEX ix_fam_inventory_control_settings_updated_by ON fam_inventory_control_settings (updated_by);

CREATE INDEX ix_fam_inventory_control_settings_company_id ON fam_inventory_control_settings (company_id);

CREATE INDEX ix_fam_inventory_control_settings_id ON fam_inventory_control_settings (id);

CREATE INDEX ix_fam_inventory_control_settings_updated_at ON fam_inventory_control_settings (updated_at);

CREATE TABLE fam_import_jobs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	import_type VARCHAR(80) NOT NULL, 
	file_name VARCHAR(220) NOT NULL, 
	file_content TEXT, 
	status VARCHAR(30), 
	mapping_json JSON, 
	validation_result_json JSON, 
	error_json JSON, 
	row_count INTEGER, 
	created_by INTEGER, 
	posted_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	posted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(posted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_import_jobs_company_id ON fam_import_jobs (company_id);

CREATE INDEX ix_fam_import_jobs_created_by ON fam_import_jobs (created_by);

CREATE INDEX ix_fam_import_jobs_created_at ON fam_import_jobs (created_at);

CREATE INDEX ix_fam_import_jobs_import_type ON fam_import_jobs (import_type);

CREATE INDEX ix_fam_import_jobs_status ON fam_import_jobs (status);

CREATE INDEX ix_fam_import_jobs_posted_at ON fam_import_jobs (posted_at);

CREATE INDEX ix_fam_import_jobs_id ON fam_import_jobs (id);

CREATE INDEX ix_fam_import_jobs_posted_by ON fam_import_jobs (posted_by);

CREATE TABLE fam_export_jobs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	export_type VARCHAR(80) NOT NULL, 
	export_format VARCHAR(20), 
	status VARCHAR(30), 
	file_name VARCHAR(220), 
	file_content TEXT, 
	result_json JSON, 
	error_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_export_jobs_created_at ON fam_export_jobs (created_at);

CREATE INDEX ix_fam_export_jobs_company_id ON fam_export_jobs (company_id);

CREATE INDEX ix_fam_export_jobs_created_by ON fam_export_jobs (created_by);

CREATE INDEX ix_fam_export_jobs_export_format ON fam_export_jobs (export_format);

CREATE INDEX ix_fam_export_jobs_status ON fam_export_jobs (status);

CREATE INDEX ix_fam_export_jobs_id ON fam_export_jobs (id);

CREATE INDEX ix_fam_export_jobs_export_type ON fam_export_jobs (export_type);

CREATE TABLE fam_integrity_runs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	status VARCHAR(30), 
	result_json JSON, 
	run_by INTEGER, 
	run_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(run_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_integrity_runs_run_by ON fam_integrity_runs (run_by);

CREATE INDEX ix_fam_integrity_runs_run_at ON fam_integrity_runs (run_at);

CREATE INDEX ix_fam_integrity_runs_company_id ON fam_integrity_runs (company_id);

CREATE INDEX ix_fam_integrity_runs_status ON fam_integrity_runs (status);

CREATE INDEX ix_fam_integrity_runs_id ON fam_integrity_runs (id);

CREATE TABLE fam_period_close_runs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	financial_year_id INTEGER, 
	accounting_period_id INTEGER, 
	status VARCHAR(30), 
	checklist_json JSON, 
	locked_period_id INTEGER, 
	approval_note TEXT, 
	run_by INTEGER, 
	run_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	locked_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(run_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(accounting_period_id) REFERENCES fam_accounting_periods (id) ON DELETE SET NULL, 
	FOREIGN KEY(locked_period_id) REFERENCES fam_accounting_periods (id) ON DELETE SET NULL, 
	FOREIGN KEY(financial_year_id) REFERENCES fam_financial_years (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_period_close_runs_financial_year_id ON fam_period_close_runs (financial_year_id);

CREATE INDEX ix_fam_period_close_runs_run_by ON fam_period_close_runs (run_by);

CREATE INDEX ix_fam_period_close_runs_id ON fam_period_close_runs (id);

CREATE INDEX ix_fam_period_close_runs_locked_period_id ON fam_period_close_runs (locked_period_id);

CREATE INDEX ix_fam_period_close_runs_run_at ON fam_period_close_runs (run_at);

CREATE INDEX ix_fam_period_close_runs_company_id ON fam_period_close_runs (company_id);

CREATE INDEX ix_fam_period_close_runs_accounting_period_id ON fam_period_close_runs (accounting_period_id);

CREATE INDEX ix_fam_period_close_runs_status ON fam_period_close_runs (status);

CREATE INDEX ix_fam_period_close_runs_locked_at ON fam_period_close_runs (locked_at);

CREATE TABLE fam_ai_accounting_logs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	request_type VARCHAR(80) NOT NULL, 
	prompt TEXT, 
	context_json JSON, 
	response_json JSON, 
	confidence NUMERIC(7, 3), 
	evidence_json JSON, 
	provider VARCHAR(80), 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_ai_accounting_logs_id ON fam_ai_accounting_logs (id);

CREATE INDEX ix_fam_ai_accounting_logs_request_type ON fam_ai_accounting_logs (request_type);

CREATE INDEX ix_fam_ai_accounting_logs_company_id ON fam_ai_accounting_logs (company_id);

CREATE INDEX ix_fam_ai_accounting_logs_created_at ON fam_ai_accounting_logs (created_at);

CREATE INDEX ix_fam_ai_accounting_logs_status ON fam_ai_accounting_logs (status);

CREATE INDEX ix_fam_ai_accounting_logs_created_by ON fam_ai_accounting_logs (created_by);

CREATE TABLE cost_centers (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	company_id INTEGER NOT NULL, 
	organization_id INTEGER, 
	business_unit_id INTEGER, 
	owner_employee_id INTEGER, 
	budget_amount NUMERIC(14, 2), 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_cost_centers_id ON cost_centers (id);

CREATE INDEX ix_cost_centers_business_unit_id ON cost_centers (business_unit_id);

CREATE UNIQUE INDEX ix_cost_centers_code ON cost_centers (code);

CREATE INDEX ix_cost_centers_organization_id ON cost_centers (organization_id);

CREATE INDEX ix_cost_centers_name ON cost_centers (name);

CREATE INDEX ix_cost_centers_company_id ON cost_centers (company_id);

CREATE INDEX ix_cost_centers_is_active ON cost_centers (is_active);

CREATE TABLE work_locations (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	company_id INTEGER NOT NULL, 
	organization_id INTEGER, 
	branch_id INTEGER, 
	location_type VARCHAR(50), 
	address TEXT, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	description TEXT, 
	latitude NUMERIC(10, 7), 
	longitude NUMERIC(10, 7), 
	radius_meters INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_work_locations_name ON work_locations (name);

CREATE INDEX ix_work_locations_organization_id ON work_locations (organization_id);

CREATE INDEX ix_work_locations_company_id ON work_locations (company_id);

CREATE INDEX ix_work_locations_branch_id ON work_locations (branch_id);

CREATE INDEX ix_work_locations_id ON work_locations (id);

CREATE UNIQUE INDEX ix_work_locations_code ON work_locations (code);

CREATE INDEX ix_work_locations_is_active ON work_locations (is_active);

CREATE TABLE job_profiles (
	id SERIAL NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	job_family_id INTEGER, 
	grade_band_id INTEGER, 
	description TEXT, 
	responsibilities TEXT, 
	required_skills_json JSON, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_family_id) REFERENCES job_families (id) ON DELETE SET NULL, 
	FOREIGN KEY(grade_band_id) REFERENCES grade_bands (id) ON DELETE SET NULL
);

CREATE INDEX ix_job_profiles_title ON job_profiles (title);

CREATE INDEX ix_job_profiles_is_active ON job_profiles (is_active);

CREATE UNIQUE INDEX ix_job_profiles_code ON job_profiles (code);

CREATE INDEX ix_job_profiles_grade_band_id ON job_profiles (grade_band_id);

CREATE INDEX ix_job_profiles_id ON job_profiles (id);

CREATE INDEX ix_job_profiles_job_family_id ON job_profiles (job_family_id);

CREATE TABLE departments (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(20), 
	organization_id INTEGER, 
	branch_id INTEGER NOT NULL, 
	head_employee_id INTEGER, 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE CASCADE
);

CREATE INDEX ix_departments_id ON departments (id);

CREATE INDEX ix_departments_name ON departments (name);

CREATE INDEX ix_departments_organization_id ON departments (organization_id);

CREATE TABLE common_profiles (
	id SERIAL NOT NULL, 
	person_id INTEGER NOT NULL, 
	preferred_display_name VARCHAR(180), 
	profile_photo_url VARCHAR(500), 
	bio TEXT, 
	timezone VARCHAR(80), 
	locale VARCHAR(20), 
	directory_visibility VARCHAR(20), 
	skills_json JSON, 
	profile_data_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_id) REFERENCES common_people (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_common_profiles_person_id ON common_profiles (person_id);

CREATE INDEX ix_common_profiles_id ON common_profiles (id);

CREATE INDEX ix_common_profiles_directory_visibility ON common_profiles (directory_visibility);

CREATE TABLE approval_comments (
	id SERIAL NOT NULL, 
	request_id INTEGER NOT NULL, 
	author_user_id INTEGER, 
	comment TEXT NOT NULL, 
	is_internal BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(request_id) REFERENCES approval_requests (id) ON DELETE CASCADE
);

CREATE INDEX ix_approval_comments_request_id ON approval_comments (request_id);

CREATE INDEX ix_approval_comments_id ON approval_comments (id);

CREATE TABLE approval_history (
	id SERIAL NOT NULL, 
	request_id INTEGER NOT NULL, 
	event_type VARCHAR(60) NOT NULL, 
	actor_user_id INTEGER, 
	before_status VARCHAR(30), 
	after_status VARCHAR(30), 
	reason TEXT, 
	details_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES approval_requests (id) ON DELETE CASCADE, 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_approval_history_event_type ON approval_history (event_type);

CREATE INDEX ix_approval_history_id ON approval_history (id);

CREATE INDEX ix_approval_history_created_at ON approval_history (created_at);

CREATE INDEX ix_approval_history_request_id ON approval_history (request_id);

CREATE TABLE notification_delivery_logs (
	id SERIAL NOT NULL, 
	notification_id INTEGER NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	recipient VARCHAR(200), 
	status VARCHAR(30), 
	provider_message_id VARCHAR(200), 
	error_message TEXT, 
	attempted_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	delivered_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(notification_id) REFERENCES notifications (id) ON DELETE CASCADE
);

CREATE INDEX ix_notification_delivery_logs_id ON notification_delivery_logs (id);

CREATE INDEX ix_notification_delivery_logs_notification_id ON notification_delivery_logs (notification_id);

CREATE INDEX idx_notification_delivery_channel_status ON notification_delivery_logs (channel, status, attempted_at);

CREATE TABLE workflow_step_definitions (
	id SERIAL NOT NULL, 
	workflow_id INTEGER NOT NULL, 
	step_order INTEGER NOT NULL, 
	step_type VARCHAR(40), 
	approver_type VARCHAR(40), 
	approver_value VARCHAR(120), 
	condition_expression TEXT, 
	skip_if_condition TEXT, 
	timeout_hours INTEGER, 
	reminder_hours INTEGER, 
	timeout_action VARCHAR(40), 
	escalation_user_id INTEGER, 
	escalation_role VARCHAR(120), 
	action_type VARCHAR(80), 
	action_config JSON, 
	delegation_type VARCHAR(40), 
	delegation_value VARCHAR(120), 
	delegation_starts_at TIMESTAMP WITH TIME ZONE, 
	delegation_ends_at TIMESTAMP WITH TIME ZONE, 
	metadata_json JSON, 
	is_required BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(escalation_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(workflow_id) REFERENCES workflow_definitions (id) ON DELETE CASCADE
);

CREATE INDEX ix_workflow_step_definitions_id ON workflow_step_definitions (id);

CREATE INDEX ix_workflow_step_definitions_workflow_id ON workflow_step_definitions (workflow_id);

CREATE TABLE workflow_instances (
	id SERIAL NOT NULL, 
	workflow_id INTEGER, 
	module VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	requester_user_id INTEGER, 
	context_json JSON, 
	status VARCHAR(30), 
	current_step_order INTEGER, 
	started_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES workflow_definitions (id) ON DELETE SET NULL, 
	FOREIGN KEY(requester_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_workflow_instances_entity_id ON workflow_instances (entity_id);

CREATE INDEX ix_workflow_instances_status ON workflow_instances (status);

CREATE INDEX ix_workflow_instances_id ON workflow_instances (id);

CREATE INDEX ix_workflow_instances_module ON workflow_instances (module);

CREATE INDEX ix_workflow_instances_workflow_id ON workflow_instances (workflow_id);

CREATE TABLE automation_triggers (
	id SERIAL NOT NULL, 
	workflow_id INTEGER NOT NULL, 
	trigger_type VARCHAR(80) NOT NULL, 
	config_json JSON, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES automation_workflows (id) ON DELETE CASCADE
);

CREATE INDEX ix_automation_triggers_trigger_type ON automation_triggers (trigger_type);

CREATE INDEX ix_automation_triggers_workflow_id ON automation_triggers (workflow_id);

CREATE INDEX ix_automation_triggers_is_active ON automation_triggers (is_active);

CREATE INDEX ix_automation_triggers_id ON automation_triggers (id);

CREATE TABLE automation_conditions (
	id SERIAL NOT NULL, 
	workflow_id INTEGER NOT NULL, 
	condition_json JSON NOT NULL, 
	order_index INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES automation_workflows (id) ON DELETE CASCADE
);

CREATE INDEX ix_automation_conditions_workflow_id ON automation_conditions (workflow_id);

CREATE INDEX ix_automation_conditions_id ON automation_conditions (id);

CREATE TABLE automation_actions (
	id SERIAL NOT NULL, 
	workflow_id INTEGER NOT NULL, 
	action_type VARCHAR(80) NOT NULL, 
	action_json JSON NOT NULL, 
	order_index INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES automation_workflows (id) ON DELETE CASCADE
);

CREATE INDEX ix_automation_actions_action_type ON automation_actions (action_type);

CREATE INDEX ix_automation_actions_id ON automation_actions (id);

CREATE INDEX ix_automation_actions_workflow_id ON automation_actions (workflow_id);

CREATE TABLE automation_execution_logs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	workflow_id INTEGER, 
	module_name VARCHAR(60) NOT NULL, 
	record_type VARCHAR(80), 
	record_id INTEGER, 
	trigger_type VARCHAR(80), 
	status VARCHAR(30) NOT NULL, 
	depth INTEGER, 
	request_json JSON, 
	result_json JSON, 
	error_message TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(workflow_id) REFERENCES automation_workflows (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_execution_logs_created_at ON automation_execution_logs (created_at);

CREATE INDEX ix_automation_execution_logs_module_name ON automation_execution_logs (module_name);

CREATE INDEX ix_automation_execution_logs_record_id ON automation_execution_logs (record_id);

CREATE INDEX ix_automation_execution_logs_status ON automation_execution_logs (status);

CREATE INDEX ix_automation_execution_logs_id ON automation_execution_logs (id);

CREATE INDEX ix_automation_execution_logs_record_type ON automation_execution_logs (record_type);

CREATE INDEX ix_automation_execution_logs_created_by ON automation_execution_logs (created_by);

CREATE INDEX ix_automation_execution_logs_organization_id ON automation_execution_logs (organization_id);

CREATE INDEX ix_automation_execution_logs_workflow_id ON automation_execution_logs (workflow_id);

CREATE INDEX ix_automation_execution_logs_trigger_type ON automation_execution_logs (trigger_type);

CREATE TABLE automation_blueprint_stages (
	id SERIAL NOT NULL, 
	blueprint_id INTEGER NOT NULL, 
	stage_key VARCHAR(80) NOT NULL, 
	label VARCHAR(160) NOT NULL, 
	order_index INTEGER, 
	required_fields_json JSON, 
	requires_approval BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(blueprint_id) REFERENCES automation_blueprints (id) ON DELETE CASCADE, 
	CONSTRAINT uq_automation_blueprint_stage_key UNIQUE (blueprint_id, stage_key)
);

CREATE INDEX ix_automation_blueprint_stages_id ON automation_blueprint_stages (id);

CREATE INDEX ix_automation_blueprint_stages_blueprint_id ON automation_blueprint_stages (blueprint_id);

CREATE INDEX ix_automation_blueprint_stages_stage_key ON automation_blueprint_stages (stage_key);

CREATE TABLE automation_blueprint_transitions (
	id SERIAL NOT NULL, 
	blueprint_id INTEGER NOT NULL, 
	from_stage_key VARCHAR(80) NOT NULL, 
	to_stage_key VARCHAR(80) NOT NULL, 
	required_fields_json JSON, 
	requires_approval BOOLEAN, 
	automation_workflow_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(blueprint_id) REFERENCES automation_blueprints (id) ON DELETE CASCADE, 
	CONSTRAINT uq_automation_blueprint_transition UNIQUE (blueprint_id, from_stage_key, to_stage_key), 
	FOREIGN KEY(automation_workflow_id) REFERENCES automation_workflows (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_blueprint_transitions_blueprint_id ON automation_blueprint_transitions (blueprint_id);

CREATE INDEX ix_automation_blueprint_transitions_from_stage_key ON automation_blueprint_transitions (from_stage_key);

CREATE INDEX ix_automation_blueprint_transitions_id ON automation_blueprint_transitions (id);

CREATE INDEX ix_automation_blueprint_transitions_to_stage_key ON automation_blueprint_transitions (to_stage_key);

CREATE TABLE automation_approval_steps (
	id SERIAL NOT NULL, 
	rule_id INTEGER NOT NULL, 
	step_order INTEGER, 
	approver_role VARCHAR(80), 
	approver_user_id INTEGER, 
	escalation_hours INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(approver_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(rule_id) REFERENCES automation_approval_rules (id) ON DELETE CASCADE
);

CREATE INDEX ix_automation_approval_steps_rule_id ON automation_approval_steps (rule_id);

CREATE INDEX ix_automation_approval_steps_approver_role ON automation_approval_steps (approver_role);

CREATE INDEX ix_automation_approval_steps_id ON automation_approval_steps (id);

CREATE INDEX ix_automation_approval_steps_approver_user_id ON automation_approval_steps (approver_user_id);

CREATE TABLE automation_approval_requests (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	rule_id INTEGER, 
	module_name VARCHAR(60) NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	record_id INTEGER NOT NULL, 
	status VARCHAR(30), 
	current_step INTEGER, 
	submitted_by INTEGER, 
	decided_by INTEGER, 
	decision_comment TEXT, 
	history_json JSON, 
	payload_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(decided_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(rule_id) REFERENCES automation_approval_rules (id) ON DELETE SET NULL
);

CREATE INDEX ix_automation_approval_requests_module_name ON automation_approval_requests (module_name);

CREATE INDEX ix_automation_approval_requests_record_id ON automation_approval_requests (record_id);

CREATE INDEX ix_automation_approval_requests_created_at ON automation_approval_requests (created_at);

CREATE INDEX ix_automation_approval_requests_organization_id ON automation_approval_requests (organization_id);

CREATE INDEX ix_automation_approval_requests_rule_id ON automation_approval_requests (rule_id);

CREATE INDEX ix_automation_approval_requests_status ON automation_approval_requests (status);

CREATE INDEX ix_automation_approval_requests_id ON automation_approval_requests (id);

CREATE INDEX ix_automation_approval_requests_record_type ON automation_approval_requests (record_type);

CREATE INDEX ix_automation_approval_requests_submitted_by ON automation_approval_requests (submitted_by);

CREATE TABLE automation_cadence_steps (
	id SERIAL NOT NULL, 
	cadence_id INTEGER NOT NULL, 
	step_order INTEGER, 
	step_type VARCHAR(40) NOT NULL, 
	delay_hours INTEGER, 
	payload_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(cadence_id) REFERENCES automation_cadences (id) ON DELETE CASCADE
);

CREATE INDEX ix_automation_cadence_steps_id ON automation_cadence_steps (id);

CREATE INDEX ix_automation_cadence_steps_cadence_id ON automation_cadence_steps (cadence_id);

CREATE INDEX ix_automation_cadence_steps_step_type ON automation_cadence_steps (step_type);

CREATE TABLE customization_field_options (
	id SERIAL NOT NULL, 
	field_id INTEGER NOT NULL, 
	value VARCHAR(160) NOT NULL, 
	label VARCHAR(160) NOT NULL, 
	color VARCHAR(40), 
	order_index INTEGER, 
	active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(field_id) REFERENCES customization_fields (id) ON DELETE CASCADE
);

CREATE INDEX ix_customization_field_options_active ON customization_field_options (active);

CREATE INDEX ix_customization_field_options_id ON customization_field_options (id);

CREATE INDEX ix_customization_field_options_field_id ON customization_field_options (field_id);

CREATE TABLE customization_layout_sections (
	id SERIAL NOT NULL, 
	layout_id INTEGER NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	order_index INTEGER, 
	visible BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(layout_id) REFERENCES customization_layouts (id) ON DELETE CASCADE
);

CREATE INDEX ix_customization_layout_sections_layout_id ON customization_layout_sections (layout_id);

CREATE INDEX ix_customization_layout_sections_id ON customization_layout_sections (id);

CREATE TABLE customization_global_picklist_values (
	id SERIAL NOT NULL, 
	picklist_id INTEGER NOT NULL, 
	value VARCHAR(160) NOT NULL, 
	label VARCHAR(160) NOT NULL, 
	order_index INTEGER, 
	active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(picklist_id) REFERENCES customization_global_picklists (id) ON DELETE CASCADE
);

CREATE INDEX ix_customization_global_picklist_values_id ON customization_global_picklist_values (id);

CREATE INDEX ix_customization_global_picklist_values_picklist_id ON customization_global_picklist_values (picklist_id);

CREATE TABLE customization_record_values (
	id SERIAL NOT NULL, 
	record_id INTEGER NOT NULL, 
	field_id INTEGER NOT NULL, 
	value_json JSON, 
	value_text TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_customization_record_field UNIQUE (record_id, field_id), 
	FOREIGN KEY(record_id) REFERENCES customization_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(field_id) REFERENCES customization_fields (id) ON DELETE CASCADE
);

CREATE INDEX ix_customization_record_values_field_id ON customization_record_values (field_id);

CREATE INDEX ix_customization_record_values_id ON customization_record_values (id);

CREATE INDEX ix_customization_record_values_record_id ON customization_record_values (record_id);

CREATE TABLE communication_email_attachments (
	id SERIAL NOT NULL, 
	message_id INTEGER NOT NULL, 
	file_name VARCHAR(240) NOT NULL, 
	file_url TEXT, 
	mime_type VARCHAR(120), 
	size_bytes INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(message_id) REFERENCES communication_email_messages (id) ON DELETE CASCADE
);

CREATE INDEX ix_communication_email_attachments_id ON communication_email_attachments (id);

CREATE INDEX ix_communication_email_attachments_message_id ON communication_email_attachments (message_id);

CREATE TABLE communication_auto_response_rules (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	trigger_type VARCHAR(80), 
	template_id INTEGER, 
	active BOOLEAN, 
	condition_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(template_id) REFERENCES communication_email_templates (id) ON DELETE SET NULL
);

CREATE INDEX ix_communication_auto_response_rules_name ON communication_auto_response_rules (name);

CREATE INDEX ix_communication_auto_response_rules_active ON communication_auto_response_rules (active);

CREATE INDEX ix_communication_auto_response_rules_created_at ON communication_auto_response_rules (created_at);

CREATE INDEX ix_communication_auto_response_rules_id ON communication_auto_response_rules (id);

CREATE INDEX ix_communication_auto_response_rules_trigger_type ON communication_auto_response_rules (trigger_type);

CREATE TABLE communication_campaigns (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	type VARCHAR(40) NOT NULL, 
	segment_json JSON, 
	template_id INTEGER, 
	status VARCHAR(40) NOT NULL, 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	sent_count INTEGER, 
	failed_count INTEGER, 
	blocked_count INTEGER, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(template_id) REFERENCES communication_email_templates (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_communication_campaigns_id ON communication_campaigns (id);

CREATE INDEX ix_communication_campaigns_status ON communication_campaigns (status);

CREATE INDEX ix_communication_campaigns_scheduled_at ON communication_campaigns (scheduled_at);

CREATE INDEX ix_communication_campaigns_type ON communication_campaigns (type);

CREATE INDEX ix_communication_campaigns_name ON communication_campaigns (name);

CREATE INDEX ix_communication_campaigns_created_at ON communication_campaigns (created_at);

CREATE TABLE analytics_report_fields (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	field_name VARCHAR(120) NOT NULL, 
	label VARCHAR(160), 
	order_index INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES analytics_reports (id) ON DELETE CASCADE
);

CREATE INDEX ix_analytics_report_fields_report_id ON analytics_report_fields (report_id);

CREATE INDEX ix_analytics_report_fields_id ON analytics_report_fields (id);

CREATE TABLE analytics_report_filters (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	field_name VARCHAR(120) NOT NULL, 
	operator VARCHAR(40), 
	value_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES analytics_reports (id) ON DELETE CASCADE
);

CREATE INDEX ix_analytics_report_filters_id ON analytics_report_filters (id);

CREATE INDEX ix_analytics_report_filters_report_id ON analytics_report_filters (report_id);

CREATE TABLE analytics_report_sorts (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	field_name VARCHAR(120) NOT NULL, 
	direction VARCHAR(10), 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES analytics_reports (id) ON DELETE CASCADE
);

CREATE INDEX ix_analytics_report_sorts_id ON analytics_report_sorts (id);

CREATE INDEX ix_analytics_report_sorts_report_id ON analytics_report_sorts (report_id);

CREATE TABLE analytics_report_joins (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	source_module VARCHAR(100) NOT NULL, 
	target_module VARCHAR(100) NOT NULL, 
	join_config_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES analytics_reports (id) ON DELETE CASCADE
);

CREATE INDEX ix_analytics_report_joins_id ON analytics_report_joins (id);

CREATE INDEX ix_analytics_report_joins_report_id ON analytics_report_joins (report_id);

CREATE TABLE analytics_dashboard_widgets (
	id SERIAL NOT NULL, 
	dashboard_id INTEGER NOT NULL, 
	widget_type VARCHAR(40) NOT NULL, 
	title VARCHAR(180) NOT NULL, 
	config_json JSON, 
	position_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(dashboard_id) REFERENCES analytics_dashboards (id) ON DELETE CASCADE
);

CREATE INDEX ix_analytics_dashboard_widgets_widget_type ON analytics_dashboard_widgets (widget_type);

CREATE INDEX ix_analytics_dashboard_widgets_id ON analytics_dashboard_widgets (id);

CREATE INDEX ix_analytics_dashboard_widgets_dashboard_id ON analytics_dashboard_widgets (dashboard_id);

CREATE TABLE analytics_scheduled_reports (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	frequency VARCHAR(40), 
	recipients_json JSON, 
	active INTEGER, 
	next_run_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES analytics_reports (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_analytics_scheduled_reports_report_id ON analytics_scheduled_reports (report_id);

CREATE INDEX ix_analytics_scheduled_reports_id ON analytics_scheduled_reports (id);

CREATE INDEX ix_analytics_scheduled_reports_active ON analytics_scheduled_reports (active);

CREATE INDEX ix_analytics_scheduled_reports_name ON analytics_scheduled_reports (name);

CREATE INDEX ix_analytics_scheduled_reports_created_by ON analytics_scheduled_reports (created_by);

CREATE INDEX ix_analytics_scheduled_reports_frequency ON analytics_scheduled_reports (frequency);

CREATE INDEX ix_analytics_scheduled_reports_next_run_at ON analytics_scheduled_reports (next_run_at);

CREATE INDEX ix_analytics_scheduled_reports_created_at ON analytics_scheduled_reports (created_at);

CREATE TABLE analytics_report_runs (
	id SERIAL NOT NULL, 
	report_id INTEGER, 
	status VARCHAR(40), 
	row_count INTEGER, 
	run_by INTEGER, 
	parameters_json JSON, 
	result_preview_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(run_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(report_id) REFERENCES analytics_reports (id) ON DELETE SET NULL
);

CREATE INDEX ix_analytics_report_runs_id ON analytics_report_runs (id);

CREATE INDEX ix_analytics_report_runs_status ON analytics_report_runs (status);

CREATE INDEX ix_analytics_report_runs_report_id ON analytics_report_runs (report_id);

CREATE INDEX ix_analytics_report_runs_run_by ON analytics_report_runs (run_by);

CREATE INDEX ix_analytics_report_runs_created_at ON analytics_report_runs (created_at);

CREATE TABLE analytics_exports (
	id SERIAL NOT NULL, 
	report_id INTEGER, 
	requested_by INTEGER, 
	export_type VARCHAR(20) NOT NULL, 
	status VARCHAR(40), 
	file_path_or_reference TEXT, 
	row_count INTEGER, 
	error_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(report_id) REFERENCES analytics_reports (id) ON DELETE SET NULL
);

CREATE INDEX ix_analytics_exports_report_id ON analytics_exports (report_id);

CREATE INDEX ix_analytics_exports_created_at ON analytics_exports (created_at);

CREATE INDEX ix_analytics_exports_id ON analytics_exports (id);

CREATE INDEX ix_analytics_exports_export_type ON analytics_exports (export_type);

CREATE INDEX ix_analytics_exports_status ON analytics_exports (status);

CREATE INDEX ix_analytics_exports_requested_by ON analytics_exports (requested_by);

CREATE INDEX ix_analytics_exports_completed_at ON analytics_exports (completed_at);

CREATE TABLE ai_prompt_runs (
	id SERIAL NOT NULL, 
	use_case VARCHAR(80) NOT NULL, 
	provider VARCHAR(80), 
	model VARCHAR(120), 
	record_type VARCHAR(80), 
	record_id INTEGER, 
	input_token_estimate INTEGER, 
	output_token_estimate INTEGER, 
	status VARCHAR(40), 
	error_message TEXT, 
	prompt_template_id INTEGER, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(prompt_template_id) REFERENCES ai_prompt_templates (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_prompt_runs_record_type ON ai_prompt_runs (record_type);

CREATE INDEX ix_ai_prompt_runs_record_id ON ai_prompt_runs (record_id);

CREATE INDEX ix_ai_prompt_runs_use_case ON ai_prompt_runs (use_case);

CREATE INDEX ix_ai_prompt_runs_provider ON ai_prompt_runs (provider);

CREATE INDEX ix_ai_prompt_runs_created_by ON ai_prompt_runs (created_by);

CREATE INDEX ix_ai_prompt_runs_id ON ai_prompt_runs (id);

CREATE INDEX ix_ai_prompt_runs_status ON ai_prompt_runs (status);

CREATE INDEX ix_ai_prompt_runs_created_at ON ai_prompt_runs (created_at);

CREATE TABLE admin_import_job_rows (
	id SERIAL NOT NULL, 
	import_job_id INTEGER NOT NULL, 
	row_number INTEGER NOT NULL, 
	raw_json JSON, 
	mapped_json JSON, 
	status VARCHAR(30), 
	error_message TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(import_job_id) REFERENCES admin_import_jobs (id) ON DELETE CASCADE
);

CREATE INDEX ix_admin_import_job_rows_id ON admin_import_job_rows (id);

CREATE INDEX ix_admin_import_job_rows_status ON admin_import_job_rows (status);

CREATE INDEX ix_admin_import_job_rows_import_job_id ON admin_import_job_rows (import_job_id);

CREATE TABLE portal_access_grants (
	id SERIAL NOT NULL, 
	portal_user_id INTEGER NOT NULL, 
	resource_type VARCHAR(80) NOT NULL, 
	resource_id INTEGER NOT NULL, 
	permissions_json JSON, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_portal_grant_resource UNIQUE (portal_user_id, resource_type, resource_id), 
	FOREIGN KEY(portal_user_id) REFERENCES portal_users (id) ON DELETE CASCADE
);

CREATE INDEX ix_portal_access_grants_portal_user_id ON portal_access_grants (portal_user_id);

CREATE INDEX ix_portal_access_grants_resource_id ON portal_access_grants (resource_id);

CREATE INDEX ix_portal_access_grants_id ON portal_access_grants (id);

CREATE INDEX ix_portal_access_grants_resource_type ON portal_access_grants (resource_type);

CREATE INDEX ix_portal_access_grants_active ON portal_access_grants (active);

CREATE TABLE portal_sessions (
	id SERIAL NOT NULL, 
	portal_user_id INTEGER NOT NULL, 
	session_token_hash VARCHAR(255) NOT NULL, 
	status VARCHAR(30), 
	ip_address VARCHAR(80), 
	user_agent TEXT, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	last_seen_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(portal_user_id) REFERENCES portal_users (id) ON DELETE CASCADE
);

CREATE INDEX ix_portal_sessions_id ON portal_sessions (id);

CREATE INDEX ix_portal_sessions_status ON portal_sessions (status);

CREATE UNIQUE INDEX ix_portal_sessions_session_token_hash ON portal_sessions (session_token_hash);

CREATE INDEX ix_portal_sessions_portal_user_id ON portal_sessions (portal_user_id);

CREATE INDEX ix_portal_sessions_expires_at ON portal_sessions (expires_at);

CREATE TABLE portal_customer_links (
	id SERIAL NOT NULL, 
	portal_user_id INTEGER NOT NULL, 
	customer_id INTEGER NOT NULL, 
	crm_account_id INTEGER, 
	crm_contact_id INTEGER, 
	srm_customer_id INTEGER, 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(portal_user_id) REFERENCES portal_users (id) ON DELETE CASCADE
);

CREATE INDEX ix_portal_customer_links_id ON portal_customer_links (id);

CREATE INDEX ix_portal_customer_links_portal_user_id ON portal_customer_links (portal_user_id);

CREATE INDEX ix_portal_customer_links_srm_customer_id ON portal_customer_links (srm_customer_id);

CREATE INDEX ix_portal_customer_links_customer_id ON portal_customer_links (customer_id);

CREATE INDEX ix_portal_customer_links_crm_contact_id ON portal_customer_links (crm_contact_id);

CREATE INDEX ix_portal_customer_links_crm_account_id ON portal_customer_links (crm_account_id);

CREATE INDEX ix_portal_customer_links_active ON portal_customer_links (active);

CREATE TABLE portal_partner_links (
	id SERIAL NOT NULL, 
	portal_user_id INTEGER NOT NULL, 
	partner_id INTEGER NOT NULL, 
	partner_name VARCHAR(180), 
	active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(portal_user_id) REFERENCES portal_users (id) ON DELETE CASCADE
);

CREATE INDEX ix_portal_partner_links_id ON portal_partner_links (id);

CREATE INDEX ix_portal_partner_links_active ON portal_partner_links (active);

CREATE INDEX ix_portal_partner_links_portal_user_id ON portal_partner_links (portal_user_id);

CREATE INDEX ix_portal_partner_links_partner_id ON portal_partner_links (partner_id);

CREATE TABLE portal_activity_logs (
	id SERIAL NOT NULL, 
	portal_user_id INTEGER, 
	portal_type VARCHAR(30) NOT NULL, 
	event_type VARCHAR(80) NOT NULL, 
	resource_type VARCHAR(80), 
	resource_id INTEGER, 
	status VARCHAR(30), 
	detail_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(portal_user_id) REFERENCES portal_users (id) ON DELETE SET NULL
);

CREATE INDEX ix_portal_activity_logs_resource_id ON portal_activity_logs (resource_id);

CREATE INDEX ix_portal_activity_logs_created_at ON portal_activity_logs (created_at);

CREATE INDEX ix_portal_activity_logs_event_type ON portal_activity_logs (event_type);

CREATE INDEX ix_portal_activity_logs_resource_type ON portal_activity_logs (resource_type);

CREATE INDEX ix_portal_activity_logs_id ON portal_activity_logs (id);

CREATE INDEX ix_portal_activity_logs_portal_type ON portal_activity_logs (portal_type);

CREATE INDEX ix_portal_activity_logs_status ON portal_activity_logs (status);

CREATE INDEX ix_portal_activity_logs_portal_user_id ON portal_activity_logs (portal_user_id);

CREATE TABLE developer_webhook_deliveries (
	id SERIAL NOT NULL, 
	webhook_id INTEGER NOT NULL, 
	event_type VARCHAR(100) NOT NULL, 
	payload_json JSON, 
	status VARCHAR(30), 
	attempt_count INTEGER, 
	next_retry_at TIMESTAMP WITH TIME ZONE, 
	response_status INTEGER, 
	response_body TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	delivered_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(webhook_id) REFERENCES developer_webhooks (id) ON DELETE CASCADE
);

CREATE INDEX ix_developer_webhook_deliveries_webhook_id ON developer_webhook_deliveries (webhook_id);

CREATE INDEX ix_developer_webhook_deliveries_status ON developer_webhook_deliveries (status);

CREATE INDEX ix_developer_webhook_deliveries_next_retry_at ON developer_webhook_deliveries (next_retry_at);

CREATE INDEX ix_developer_webhook_deliveries_event_type ON developer_webhook_deliveries (event_type);

CREATE INDEX ix_developer_webhook_deliveries_id ON developer_webhook_deliveries (id);

CREATE INDEX ix_developer_webhook_deliveries_created_at ON developer_webhook_deliveries (created_at);

CREATE TABLE developer_api_logs (
	id SERIAL NOT NULL, 
	api_key_id INTEGER, 
	key_prefix VARCHAR(20), 
	endpoint VARCHAR(240) NOT NULL, 
	method VARCHAR(12) NOT NULL, 
	status_code INTEGER NOT NULL, 
	actor_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(api_key_id) REFERENCES developer_api_keys (id) ON DELETE SET NULL, 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_developer_api_logs_endpoint ON developer_api_logs (endpoint);

CREATE INDEX ix_developer_api_logs_status_code ON developer_api_logs (status_code);

CREATE INDEX ix_developer_api_logs_api_key_id ON developer_api_logs (api_key_id);

CREATE INDEX ix_developer_api_logs_key_prefix ON developer_api_logs (key_prefix);

CREATE INDEX ix_developer_api_logs_created_at ON developer_api_logs (created_at);

CREATE INDEX ix_developer_api_logs_id ON developer_api_logs (id);

CREATE INDEX ix_developer_api_logs_actor_user_id ON developer_api_logs (actor_user_id);

CREATE TABLE marketplace_installs (
	id SERIAL NOT NULL, 
	app_id INTEGER NOT NULL, 
	status VARCHAR(30), 
	configuration_json JSON, 
	installed_by INTEGER, 
	installed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	uninstalled_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(app_id) REFERENCES marketplace_apps (id) ON DELETE CASCADE, 
	CONSTRAINT uq_marketplace_app_status UNIQUE (app_id, status), 
	FOREIGN KEY(installed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_marketplace_installs_status ON marketplace_installs (status);

CREATE INDEX ix_marketplace_installs_id ON marketplace_installs (id);

CREATE INDEX ix_marketplace_installs_installed_at ON marketplace_installs (installed_at);

CREATE INDEX ix_marketplace_installs_app_id ON marketplace_installs (app_id);

CREATE INDEX ix_marketplace_installs_installed_by ON marketplace_installs (installed_by);

CREATE TABLE sandbox_copy_jobs (
	id SERIAL NOT NULL, 
	sandbox_id INTEGER NOT NULL, 
	copy_type VARCHAR(80), 
	status VARCHAR(30), 
	detail_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sandbox_id) REFERENCES sandbox_environments (id) ON DELETE CASCADE
);

CREATE INDEX ix_sandbox_copy_jobs_status ON sandbox_copy_jobs (status);

CREATE INDEX ix_sandbox_copy_jobs_id ON sandbox_copy_jobs (id);

CREATE INDEX ix_sandbox_copy_jobs_created_at ON sandbox_copy_jobs (created_at);

CREATE INDEX ix_sandbox_copy_jobs_sandbox_id ON sandbox_copy_jobs (sandbox_id);

CREATE TABLE ai_agent_tools (
	id SERIAL NOT NULL, 
	agent_id INTEGER NOT NULL, 
	tool_name VARCHAR(120) NOT NULL, 
	tool_description TEXT, 
	input_schema_json JSON NOT NULL, 
	module VARCHAR(40) NOT NULL, 
	permission_required VARCHAR(120), 
	risk_level VARCHAR(30), 
	requires_approval BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_agent_tools_id ON ai_agent_tools (id);

CREATE INDEX ix_ai_agent_tools_is_active ON ai_agent_tools (is_active);

CREATE INDEX ix_ai_agent_tools_agent_id ON ai_agent_tools (agent_id);

CREATE INDEX ix_ai_agent_tools_module ON ai_agent_tools (module);

CREATE INDEX ix_ai_agent_tools_risk_level ON ai_agent_tools (risk_level);

CREATE INDEX ix_ai_agent_tools_tool_name ON ai_agent_tools (tool_name);

CREATE TABLE ai_conversations (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	agent_id INTEGER, 
	module VARCHAR(40) NOT NULL, 
	title VARCHAR(220) NOT NULL, 
	related_entity_type VARCHAR(80), 
	related_entity_id VARCHAR(80), 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_conversations_user_id ON ai_conversations (user_id);

CREATE INDEX ix_ai_conversations_agent_id ON ai_conversations (agent_id);

CREATE INDEX ix_ai_conversations_status ON ai_conversations (status);

CREATE INDEX ix_ai_conversations_id ON ai_conversations (id);

CREATE INDEX ix_ai_conversations_related_entity_id ON ai_conversations (related_entity_id);

CREATE INDEX ix_ai_conversations_module ON ai_conversations (module);

CREATE INDEX ix_ai_conversations_related_entity_type ON ai_conversations (related_entity_type);

CREATE TABLE ai_audit_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	agent_id INTEGER, 
	module VARCHAR(40) NOT NULL, 
	action VARCHAR(140) NOT NULL, 
	related_entity_type VARCHAR(80), 
	related_entity_id VARCHAR(80), 
	input_json JSON, 
	output_json JSON, 
	status VARCHAR(30), 
	ip_address VARCHAR(64), 
	user_agent TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_audit_logs_module ON ai_audit_logs (module);

CREATE INDEX ix_ai_audit_logs_action ON ai_audit_logs (action);

CREATE INDEX ix_ai_audit_logs_id ON ai_audit_logs (id);

CREATE INDEX ix_ai_audit_logs_agent_id ON ai_audit_logs (agent_id);

CREATE INDEX ix_ai_audit_logs_related_entity_id ON ai_audit_logs (related_entity_id);

CREATE INDEX ix_ai_audit_logs_user_id ON ai_audit_logs (user_id);

CREATE INDEX ix_ai_audit_logs_related_entity_type ON ai_audit_logs (related_entity_type);

CREATE INDEX ix_ai_audit_logs_status ON ai_audit_logs (status);

CREATE TABLE ai_agent_settings (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	agent_id INTEGER NOT NULL, 
	is_enabled BOOLEAN, 
	auto_action_enabled BOOLEAN, 
	approval_required BOOLEAN, 
	data_access_scope VARCHAR(80), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_agent_settings_agent_id ON ai_agent_settings (agent_id);

CREATE INDEX ix_ai_agent_settings_company_id ON ai_agent_settings (company_id);

CREATE INDEX ix_ai_agent_settings_is_enabled ON ai_agent_settings (is_enabled);

CREATE INDEX ix_ai_agent_settings_id ON ai_agent_settings (id);

CREATE TABLE ai_usage_limits (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	user_id INTEGER, 
	agent_id INTEGER, 
	module VARCHAR(40), 
	limit_type VARCHAR(40) NOT NULL, 
	max_requests INTEGER NOT NULL, 
	period VARCHAR(20) NOT NULL, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_usage_limits_user_id ON ai_usage_limits (user_id);

CREATE INDEX ix_ai_usage_limits_module ON ai_usage_limits (module);

CREATE INDEX ix_ai_usage_limits_id ON ai_usage_limits (id);

CREATE INDEX ix_ai_usage_limits_agent_id ON ai_usage_limits (agent_id);

CREATE INDEX ix_ai_usage_limits_period ON ai_usage_limits (period);

CREATE INDEX ix_ai_usage_limits_company_id ON ai_usage_limits (company_id);

CREATE INDEX ix_ai_usage_limits_limit_type ON ai_usage_limits (limit_type);

CREATE INDEX ix_ai_usage_limits_is_active ON ai_usage_limits (is_active);

CREATE TABLE ai_usage_events (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	user_id INTEGER, 
	agent_id INTEGER, 
	module VARCHAR(40), 
	event_type VARCHAR(40) NOT NULL, 
	token_input INTEGER, 
	token_output INTEGER, 
	estimated_cost NUMERIC(12, 6), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_usage_events_company_id ON ai_usage_events (company_id);

CREATE INDEX ix_ai_usage_events_user_id ON ai_usage_events (user_id);

CREATE INDEX ix_ai_usage_events_created_at ON ai_usage_events (created_at);

CREATE INDEX ix_ai_usage_events_id ON ai_usage_events (id);

CREATE INDEX ix_ai_usage_events_event_type ON ai_usage_events (event_type);

CREATE INDEX ix_ai_usage_events_agent_id ON ai_usage_events (agent_id);

CREATE INDEX ix_ai_usage_events_module ON ai_usage_events (module);

CREATE TABLE ai_agent_permissions (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	agent_id INTEGER NOT NULL, 
	role_id INTEGER, 
	user_id INTEGER, 
	can_use BOOLEAN, 
	can_configure BOOLEAN, 
	can_approve_actions BOOLEAN, 
	can_view_logs BOOLEAN, 
	can_export_conversations BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE CASCADE, 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_agent_permissions_company_id ON ai_agent_permissions (company_id);

CREATE INDEX ix_ai_agent_permissions_agent_id ON ai_agent_permissions (agent_id);

CREATE INDEX ix_ai_agent_permissions_user_id ON ai_agent_permissions (user_id);

CREATE INDEX ix_ai_agent_permissions_id ON ai_agent_permissions (id);

CREATE INDEX ix_ai_agent_permissions_role_id ON ai_agent_permissions (role_id);

CREATE TABLE payroll_pay_groups (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	description TEXT, 
	pay_frequency VARCHAR(30), 
	legal_entity_id INTEGER, 
	branch_id INTEGER, 
	state VARCHAR(100), 
	pay_cycle_day INTEGER, 
	pay_date_rule VARCHAR(80), 
	attendance_cutoff_day INTEGER, 
	reimbursement_cutoff_day INTEGER, 
	tax_deduction_frequency VARCHAR(30), 
	default_tax_regime VARCHAR(40), 
	rounding_policy VARCHAR(60), 
	include_weekends_in_lop BOOLEAN, 
	working_pattern VARCHAR(40), 
	working_days_per_week INTEGER, 
	weekly_off_weekdays JSON, 
	is_default BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	UNIQUE (code), 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_pay_groups_id ON payroll_pay_groups (id);

CREATE INDEX ix_payroll_pay_groups_is_default ON payroll_pay_groups (is_default);

CREATE INDEX ix_payroll_pay_groups_legal_entity_id ON payroll_pay_groups (legal_entity_id);

CREATE INDEX ix_payroll_pay_groups_branch_id ON payroll_pay_groups (branch_id);

CREATE TABLE onboarding_template_tasks (
	id SERIAL NOT NULL, 
	template_id INTEGER NOT NULL, 
	task_name VARCHAR(200) NOT NULL, 
	description TEXT, 
	category VARCHAR(50), 
	due_day_offset INTEGER, 
	assigned_to_role VARCHAR(50), 
	is_mandatory BOOLEAN, 
	order_index INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(template_id) REFERENCES onboarding_templates (id) ON DELETE CASCADE
);

CREATE INDEX ix_onboarding_template_tasks_category ON onboarding_template_tasks (category);

CREATE INDEX ix_onboarding_template_tasks_assigned_to_role ON onboarding_template_tasks (assigned_to_role);

CREATE INDEX ix_onboarding_template_tasks_template_id ON onboarding_template_tasks (template_id);

CREATE INDEX ix_onboarding_template_tasks_id ON onboarding_template_tasks (id);

CREATE TABLE calibration_sessions (
	id SERIAL NOT NULL, 
	cycle_id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	facilitator_user_id INTEGER, 
	status VARCHAR(30), 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	notes TEXT, 
	audit_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cycle_id) REFERENCES appraisal_cycles (id) ON DELETE CASCADE, 
	FOREIGN KEY(facilitator_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_calibration_sessions_cycle_id ON calibration_sessions (cycle_id);

CREATE INDEX ix_calibration_sessions_id ON calibration_sessions (id);

CREATE INDEX ix_calibration_sessions_status ON calibration_sessions (status);

CREATE TABLE custom_form_fields (
	id SERIAL NOT NULL, 
	form_id INTEGER NOT NULL, 
	field_definition_id INTEGER NOT NULL, 
	section VARCHAR(120), 
	display_order INTEGER, 
	is_required_override BOOLEAN, 
	help_text TEXT, 
	visibility_condition_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(field_definition_id) REFERENCES custom_field_definitions (id) ON DELETE CASCADE, 
	FOREIGN KEY(form_id) REFERENCES custom_form_definitions (id) ON DELETE CASCADE
);

CREATE INDEX ix_custom_form_fields_id ON custom_form_fields (id);

CREATE INDEX ix_custom_form_fields_field_definition_id ON custom_form_fields (field_definition_id);

CREATE INDEX ix_custom_form_fields_form_id ON custom_form_fields (form_id);

CREATE TABLE custom_form_submissions (
	id SERIAL NOT NULL, 
	form_id INTEGER NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	status VARCHAR(30), 
	submitted_by INTEGER, 
	submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	values_json JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(form_id) REFERENCES custom_form_definitions (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_custom_form_submissions_id ON custom_form_submissions (id);

CREATE INDEX ix_custom_form_submissions_entity_type ON custom_form_submissions (entity_type);

CREATE INDEX ix_custom_form_submissions_entity_id ON custom_form_submissions (entity_id);

CREATE INDEX ix_custom_form_submissions_form_id ON custom_form_submissions (form_id);

CREATE INDEX ix_custom_form_submissions_status ON custom_form_submissions (status);

CREATE TABLE report_runs (
	id SERIAL NOT NULL, 
	report_definition_id INTEGER NOT NULL, 
	status VARCHAR(30), 
	row_count INTEGER, 
	file_url VARCHAR(500), 
	error_message TEXT, 
	requested_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(report_definition_id) REFERENCES report_definitions (id) ON DELETE CASCADE
);

CREATE INDEX ix_report_runs_status ON report_runs (status);

CREATE INDEX ix_report_runs_report_definition_id ON report_runs (report_definition_id);

CREATE INDEX ix_report_runs_id ON report_runs (id);

CREATE TABLE report_schedules (
	id SERIAL NOT NULL, 
	report_definition_id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	cron_expression VARCHAR(80) NOT NULL, 
	recipients_json JSON, 
	export_format VARCHAR(20), 
	status VARCHAR(30), 
	last_run_at TIMESTAMP WITH TIME ZONE, 
	next_run_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(report_definition_id) REFERENCES report_definitions (id) ON DELETE CASCADE
);

CREATE INDEX ix_report_schedules_status ON report_schedules (status);

CREATE INDEX ix_report_schedules_id ON report_schedules (id);

CREATE INDEX ix_report_schedules_report_definition_id ON report_schedules (report_definition_id);

CREATE TABLE integration_events (
	id SERIAL NOT NULL, 
	subscription_id INTEGER, 
	event_type VARCHAR(120) NOT NULL, 
	payload_json JSON, 
	status VARCHAR(30), 
	attempts INTEGER, 
	last_error TEXT, 
	next_retry_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(subscription_id) REFERENCES webhook_subscriptions (id) ON DELETE SET NULL
);

CREATE INDEX ix_integration_events_id ON integration_events (id);

CREATE INDEX idx_integration_event_type_status_retry ON integration_events (event_type, status, next_retry_at);

CREATE INDEX ix_integration_events_subscription_id ON integration_events (subscription_id);

CREATE INDEX ix_integration_events_event_type ON integration_events (event_type);

CREATE INDEX ix_integration_events_status ON integration_events (status);

CREATE TABLE whatsapp_ess_templates (
	id SERIAL NOT NULL, 
	config_id INTEGER NOT NULL, 
	template_name VARCHAR(120) NOT NULL, 
	intent VARCHAR(80) NOT NULL, 
	language VARCHAR(20), 
	body_text TEXT NOT NULL, 
	provider_template_id VARCHAR(150), 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(config_id) REFERENCES whatsapp_ess_configs (id) ON DELETE CASCADE
);

CREATE INDEX ix_whatsapp_ess_templates_status ON whatsapp_ess_templates (status);

CREATE INDEX ix_whatsapp_ess_templates_config_id ON whatsapp_ess_templates (config_id);

CREATE INDEX ix_whatsapp_ess_templates_id ON whatsapp_ess_templates (id);

CREATE INDEX ix_whatsapp_ess_templates_intent ON whatsapp_ess_templates (intent);

CREATE TABLE crm_companies (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	assigned_team_id INTEGER, 
	territory_id INTEGER, 
	parent_company_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	industry VARCHAR(120), 
	website VARCHAR(200), 
	phone VARCHAR(40), 
	email VARCHAR(150), 
	address TEXT, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	employee_count INTEGER, 
	annual_revenue NUMERIC(14, 2), 
	account_type VARCHAR(40), 
	status VARCHAR(40), 
	tags_text VARCHAR(500), 
	notes TEXT, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(territory_id) REFERENCES crm_territories (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(parent_company_id) REFERENCES crm_companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_companies_department_id ON crm_companies (department_id);

CREATE INDEX ix_crm_companies_name ON crm_companies (name);

CREATE INDEX ix_crm_companies_city ON crm_companies (city);

CREATE INDEX ix_crm_companies_id ON crm_companies (id);

CREATE INDEX ix_crm_companies_owner_user_id ON crm_companies (owner_user_id);

CREATE INDEX ix_crm_companies_territory_id ON crm_companies (territory_id);

CREATE INDEX ix_crm_companies_industry ON crm_companies (industry);

CREATE INDEX ix_crm_companies_account_type ON crm_companies (account_type);

CREATE INDEX ix_crm_companies_organization_id ON crm_companies (organization_id);

CREATE INDEX ix_crm_companies_assigned_team_id ON crm_companies (assigned_team_id);

CREATE INDEX ix_crm_companies_parent_company_id ON crm_companies (parent_company_id);

CREATE INDEX ix_crm_companies_email ON crm_companies (email);

CREATE INDEX ix_crm_companies_status ON crm_companies (status);

CREATE INDEX ix_crm_companies_branch_id ON crm_companies (branch_id);

CREATE TABLE crm_pipeline_stages (
	id SERIAL NOT NULL, 
	pipeline_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	probability INTEGER, 
	position INTEGER, 
	order_index INTEGER, 
	stage_type VARCHAR(20), 
	color VARCHAR(30), 
	active BOOLEAN, 
	is_won BOOLEAN, 
	is_lost BOOLEAN, 
	organization_id INTEGER, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_pipeline_stage_name UNIQUE (pipeline_id, name), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(pipeline_id) REFERENCES crm_pipelines (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_pipeline_stages_order_index ON crm_pipeline_stages (order_index);

CREATE INDEX ix_crm_pipeline_stages_active ON crm_pipeline_stages (active);

CREATE INDEX ix_crm_pipeline_stages_stage_type ON crm_pipeline_stages (stage_type);

CREATE INDEX ix_crm_pipeline_stages_organization_id ON crm_pipeline_stages (organization_id);

CREATE INDEX ix_crm_pipeline_stages_id ON crm_pipeline_stages (id);

CREATE INDEX ix_crm_pipeline_stages_pipeline_id ON crm_pipeline_stages (pipeline_id);

CREATE TABLE crm_price_book_items (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	price_book_id INTEGER NOT NULL, 
	item_type VARCHAR(30), 
	product_id INTEGER, 
	service_id INTEGER, 
	unit_price NUMERIC(14, 2), 
	cost_price NUMERIC(14, 2), 
	tax_rate NUMERIC(5, 2), 
	active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(service_id) REFERENCES crm_services (id) ON DELETE CASCADE, 
	FOREIGN KEY(price_book_id) REFERENCES crm_price_books (id) ON DELETE CASCADE, 
	CONSTRAINT uq_crm_price_book_item UNIQUE (price_book_id, item_type, product_id, service_id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(product_id) REFERENCES crm_products (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_price_book_items_price_book_id ON crm_price_book_items (price_book_id);

CREATE INDEX ix_crm_price_book_items_service_id ON crm_price_book_items (service_id);

CREATE INDEX ix_crm_price_book_items_organization_id ON crm_price_book_items (organization_id);

CREATE INDEX ix_crm_price_book_items_item_type ON crm_price_book_items (item_type);

CREATE INDEX ix_crm_price_book_items_active ON crm_price_book_items (active);

CREATE INDEX ix_crm_price_book_items_id ON crm_price_book_items (id);

CREATE INDEX ix_crm_price_book_items_product_id ON crm_price_book_items (product_id);

CREATE TABLE crm_messages (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	entity_type VARCHAR(40) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	"to" VARCHAR(40) NOT NULL, 
	body TEXT NOT NULL, 
	status VARCHAR(30), 
	provider VARCHAR(80) NOT NULL, 
	provider_message_id VARCHAR(160), 
	failure_reason TEXT, 
	template_id INTEGER, 
	sent_by_user_id INTEGER, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(template_id) REFERENCES crm_message_templates (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(sent_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_messages_entity_id ON crm_messages (entity_id);

CREATE INDEX ix_crm_messages_status ON crm_messages (status);

CREATE INDEX ix_crm_messages_sent_at ON crm_messages (sent_at);

CREATE INDEX ix_crm_messages_entity_type ON crm_messages (entity_type);

CREATE INDEX ix_crm_messages_channel ON crm_messages (channel);

CREATE INDEX ix_crm_messages_provider ON crm_messages (provider);

CREATE INDEX ix_crm_messages_created_at ON crm_messages (created_at);

CREATE INDEX ix_crm_messages_id ON crm_messages (id);

CREATE INDEX ix_crm_messages_organization_id ON crm_messages (organization_id);

CREATE INDEX ix_crm_messages_to ON crm_messages ("to");

CREATE INDEX ix_crm_messages_template_id ON crm_messages (template_id);

CREATE TABLE crm_territory_users (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	territory_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	created_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_by_user_id INTEGER, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(territory_id) REFERENCES crm_territories (id) ON DELETE CASCADE, 
	CONSTRAINT uq_crm_territory_user UNIQUE (territory_id, user_id)
);

CREATE INDEX ix_crm_territory_users_territory_id ON crm_territory_users (territory_id);

CREATE INDEX ix_crm_territory_users_user_id ON crm_territory_users (user_id);

CREATE INDEX ix_crm_territory_users_organization_id ON crm_territory_users (organization_id);

CREATE INDEX ix_crm_territory_users_id ON crm_territory_users (id);

CREATE TABLE crm_territory_assignments (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	territory_id INTEGER NOT NULL, 
	user_id INTEGER, 
	team_id INTEGER, 
	assignment_type VARCHAR(40), 
	active BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(territory_id) REFERENCES crm_territories (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_territory_assignment UNIQUE (territory_id, user_id, team_id, assignment_type), 
	FOREIGN KEY(team_id) REFERENCES crm_teams (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_territory_assignments_team_id ON crm_territory_assignments (team_id);

CREATE INDEX ix_crm_territory_assignments_active ON crm_territory_assignments (active);

CREATE INDEX ix_crm_territory_assignments_organization_id ON crm_territory_assignments (organization_id);

CREATE INDEX ix_crm_territory_assignments_user_id ON crm_territory_assignments (user_id);

CREATE INDEX ix_crm_territory_assignments_territory_id ON crm_territory_assignments (territory_id);

CREATE INDEX ix_crm_territory_assignments_id ON crm_territory_assignments (id);

CREATE INDEX ix_crm_territory_assignments_assignment_type ON crm_territory_assignments (assignment_type);

CREATE TABLE crm_owners (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	user_id INTEGER, 
	team_id INTEGER, 
	territory_id INTEGER, 
	full_name VARCHAR(180) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	phone VARCHAR(40), 
	role VARCHAR(80), 
	status VARCHAR(30), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(team_id) REFERENCES crm_teams (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_owner_org_email UNIQUE (organization_id, email), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(territory_id) REFERENCES crm_territories (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_owners_organization_id ON crm_owners (organization_id);

CREATE INDEX ix_crm_owners_user_id ON crm_owners (user_id);

CREATE INDEX ix_crm_owners_email ON crm_owners (email);

CREATE INDEX ix_crm_owners_id ON crm_owners (id);

CREATE INDEX ix_crm_owners_territory_id ON crm_owners (territory_id);

CREATE INDEX ix_crm_owners_role ON crm_owners (role);

CREATE INDEX ix_crm_owners_team_id ON crm_owners (team_id);

CREATE INDEX ix_crm_owners_full_name ON crm_owners (full_name);

CREATE INDEX ix_crm_owners_status ON crm_owners (status);

CREATE TABLE crm_forecast_snapshots (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	snapshot_name VARCHAR(180), 
	period_start DATE, 
	period_end DATE, 
	pipeline_id INTEGER, 
	owner_user_id INTEGER, 
	team_id INTEGER, 
	territory_id INTEGER, 
	currency VARCHAR(10), 
	pipeline_amount NUMERIC(14, 2), 
	weighted_amount NUMERIC(14, 2), 
	committed_amount NUMERIC(14, 2), 
	best_case_amount NUMERIC(14, 2), 
	upside_amount NUMERIC(14, 2), 
	closed_won_amount NUMERIC(14, 2), 
	invoiced_amount NUMERIC(14, 2), 
	collected_amount NUMERIC(14, 2), 
	scenarios_json JSON, 
	created_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_by_user_id INTEGER, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(territory_id) REFERENCES crm_territories (id) ON DELETE SET NULL, 
	FOREIGN KEY(pipeline_id) REFERENCES crm_pipelines (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_forecast_snapshots_period_end ON crm_forecast_snapshots (period_end);

CREATE INDEX ix_crm_forecast_snapshots_pipeline_id ON crm_forecast_snapshots (pipeline_id);

CREATE INDEX ix_crm_forecast_snapshots_currency ON crm_forecast_snapshots (currency);

CREATE INDEX ix_crm_forecast_snapshots_id ON crm_forecast_snapshots (id);

CREATE INDEX ix_crm_forecast_snapshots_period_start ON crm_forecast_snapshots (period_start);

CREATE INDEX ix_crm_forecast_snapshots_team_id ON crm_forecast_snapshots (team_id);

CREATE INDEX ix_crm_forecast_snapshots_organization_id ON crm_forecast_snapshots (organization_id);

CREATE INDEX ix_crm_forecast_snapshots_owner_user_id ON crm_forecast_snapshots (owner_user_id);

CREATE INDEX ix_crm_forecast_snapshots_territory_id ON crm_forecast_snapshots (territory_id);

CREATE TABLE crm_sales_performance_snapshots (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	team_id INTEGER, 
	territory_id INTEGER, 
	period_start DATE, 
	period_end DATE, 
	target_amount NUMERIC(14, 2), 
	pipeline_amount NUMERIC(14, 2), 
	weighted_amount NUMERIC(14, 2), 
	won_amount NUMERIC(14, 2), 
	lost_amount NUMERIC(14, 2), 
	invoiced_amount NUMERIC(14, 2), 
	collected_amount NUMERIC(14, 2), 
	activity_count INTEGER, 
	conversion_rate NUMERIC(6, 2), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(territory_id) REFERENCES crm_territories (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_sales_performance_snapshots_territory_id ON crm_sales_performance_snapshots (territory_id);

CREATE INDEX ix_crm_sales_performance_snapshots_id ON crm_sales_performance_snapshots (id);

CREATE INDEX ix_crm_sales_performance_snapshots_team_id ON crm_sales_performance_snapshots (team_id);

CREATE INDEX ix_crm_sales_performance_snapshots_period_start ON crm_sales_performance_snapshots (period_start);

CREATE INDEX ix_crm_sales_performance_snapshots_organization_id ON crm_sales_performance_snapshots (organization_id);

CREATE INDEX ix_crm_sales_performance_snapshots_owner_user_id ON crm_sales_performance_snapshots (owner_user_id);

CREATE INDEX ix_crm_sales_performance_snapshots_period_end ON crm_sales_performance_snapshots (period_end);

CREATE TABLE crm_custom_field_values (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	custom_field_id INTEGER NOT NULL, 
	entity VARCHAR(80) NOT NULL, 
	record_id INTEGER NOT NULL, 
	value_text TEXT, 
	value_number NUMERIC(18, 4), 
	value_date DATE, 
	value_datetime TIMESTAMP WITH TIME ZONE, 
	value_boolean BOOLEAN, 
	value_json JSON, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_crm_custom_field_value_record UNIQUE (organization_id, custom_field_id, entity, record_id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(custom_field_id) REFERENCES crm_custom_fields (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_custom_field_values_id ON crm_custom_field_values (id);

CREATE INDEX ix_crm_custom_field_values_custom_field_id ON crm_custom_field_values (custom_field_id);

CREATE INDEX ix_crm_custom_field_values_entity ON crm_custom_field_values (entity);

CREATE INDEX ix_crm_custom_field_values_organization_id ON crm_custom_field_values (organization_id);

CREATE INDEX ix_crm_custom_field_values_record_id ON crm_custom_field_values (record_id);

CREATE TABLE crm_webhook_deliveries (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	webhook_id INTEGER NOT NULL, 
	event_type VARCHAR(80) NOT NULL, 
	payload JSON, 
	status VARCHAR(30), 
	response_code INTEGER, 
	response_body TEXT, 
	attempt_count INTEGER, 
	next_retry_at TIMESTAMP WITH TIME ZONE, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(webhook_id) REFERENCES crm_webhooks (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_webhook_deliveries_organization_id ON crm_webhook_deliveries (organization_id);

CREATE INDEX ix_crm_webhook_deliveries_webhook_id ON crm_webhook_deliveries (webhook_id);

CREATE INDEX ix_crm_webhook_deliveries_created_at ON crm_webhook_deliveries (created_at);

CREATE INDEX ix_crm_webhook_deliveries_id ON crm_webhook_deliveries (id);

CREATE INDEX ix_crm_webhook_deliveries_status ON crm_webhook_deliveries (status);

CREATE INDEX ix_crm_webhook_deliveries_event_type ON crm_webhook_deliveries (event_type);

CREATE INDEX ix_crm_webhook_deliveries_next_retry_at ON crm_webhook_deliveries (next_retry_at);

CREATE TABLE crm_approval_steps (
	id SERIAL NOT NULL, 
	workflow_id INTEGER NOT NULL, 
	step_order INTEGER NOT NULL, 
	approver_type VARCHAR(30) NOT NULL, 
	approver_id INTEGER, 
	action_on_reject VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES crm_approval_workflows (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_approval_steps_workflow_id ON crm_approval_steps (workflow_id);

CREATE INDEX ix_crm_approval_steps_action_on_reject ON crm_approval_steps (action_on_reject);

CREATE INDEX ix_crm_approval_steps_approver_type ON crm_approval_steps (approver_type);

CREATE INDEX ix_crm_approval_steps_approver_id ON crm_approval_steps (approver_id);

CREATE INDEX ix_crm_approval_steps_id ON crm_approval_steps (id);

CREATE INDEX ix_crm_approval_steps_step_order ON crm_approval_steps (step_order);

CREATE TABLE crm_approval_requests (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	workflow_id INTEGER, 
	entity_type VARCHAR(40) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	submitted_by INTEGER, 
	submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(workflow_id) REFERENCES crm_approval_workflows (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_approval_requests_id ON crm_approval_requests (id);

CREATE INDEX ix_crm_approval_requests_status ON crm_approval_requests (status);

CREATE INDEX ix_crm_approval_requests_submitted_at ON crm_approval_requests (submitted_at);

CREATE INDEX ix_crm_approval_requests_entity_type ON crm_approval_requests (entity_type);

CREATE INDEX ix_crm_approval_requests_entity_id ON crm_approval_requests (entity_id);

CREATE INDEX ix_crm_approval_requests_organization_id ON crm_approval_requests (organization_id);

CREATE INDEX ix_crm_approval_requests_workflow_id ON crm_approval_requests (workflow_id);

CREATE INDEX ix_crm_approval_requests_submitted_by ON crm_approval_requests (submitted_by);

CREATE TABLE srm_sales_order_lines (
	id SERIAL NOT NULL, 
	sales_order_id INTEGER NOT NULL, 
	source_quote_line_id INTEGER, 
	product_id INTEGER, 
	item_code VARCHAR(80), 
	description TEXT, 
	service_type VARCHAR(80), 
	quantity NUMERIC(12, 2), 
	unit_price NUMERIC(14, 2), 
	discount_amount NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	line_total NUMERIC(14, 2), 
	pms_template_key VARCHAR(80), 
	metadata_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_sales_order_lines_id ON srm_sales_order_lines (id);

CREATE INDEX ix_srm_sales_order_lines_product_id ON srm_sales_order_lines (product_id);

CREATE INDEX ix_srm_sales_order_lines_item_code ON srm_sales_order_lines (item_code);

CREATE INDEX ix_srm_sales_order_lines_source_quote_line_id ON srm_sales_order_lines (source_quote_line_id);

CREATE INDEX ix_srm_sales_order_lines_sales_order_id ON srm_sales_order_lines (sales_order_id);

CREATE INDEX ix_srm_sales_order_lines_service_type ON srm_sales_order_lines (service_type);

CREATE TABLE srm_pos_cash_movements (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	session_id INTEGER NOT NULL, 
	movement_type VARCHAR(40), 
	amount NUMERIC(14, 2), 
	reason TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(session_id) REFERENCES srm_pos_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_pos_cash_movements_created_by ON srm_pos_cash_movements (created_by);

CREATE INDEX ix_srm_pos_cash_movements_session_id ON srm_pos_cash_movements (session_id);

CREATE INDEX ix_srm_pos_cash_movements_movement_type ON srm_pos_cash_movements (movement_type);

CREATE INDEX ix_srm_pos_cash_movements_id ON srm_pos_cash_movements (id);

CREATE INDEX ix_srm_pos_cash_movements_organization_id ON srm_pos_cash_movements (organization_id);

CREATE INDEX ix_srm_pos_cash_movements_created_at ON srm_pos_cash_movements (created_at);

CREATE TABLE srm_pos_cashier_closings (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	session_id INTEGER NOT NULL, 
	opening_cash NUMERIC(14, 2), 
	cash_sales NUMERIC(14, 2), 
	cash_in NUMERIC(14, 2), 
	cash_out NUMERIC(14, 2), 
	expected_cash NUMERIC(14, 2), 
	counted_cash NUMERIC(14, 2), 
	variance NUMERIC(14, 2), 
	notes TEXT, 
	closed_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(closed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(session_id) REFERENCES srm_pos_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_pos_cashier_closings_id ON srm_pos_cashier_closings (id);

CREATE INDEX ix_srm_pos_cashier_closings_session_id ON srm_pos_cashier_closings (session_id);

CREATE INDEX ix_srm_pos_cashier_closings_organization_id ON srm_pos_cashier_closings (organization_id);

CREATE INDEX ix_srm_pos_cashier_closings_closed_by ON srm_pos_cashier_closings (closed_by);

CREATE INDEX ix_srm_pos_cashier_closings_created_at ON srm_pos_cashier_closings (created_at);

CREATE TABLE srm_pos_held_bills (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	session_id INTEGER, 
	hold_number VARCHAR(80) NOT NULL, 
	status VARCHAR(40), 
	customer_id INTEGER, 
	customer_name VARCHAR(220), 
	notes TEXT, 
	cart_json JSON NOT NULL, 
	amount NUMERIC(14, 2), 
	item_count INTEGER, 
	created_by INTEGER, 
	recalled_by INTEGER, 
	recalled_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recalled_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(session_id) REFERENCES srm_pos_sessions (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_pos_held_bill_org_number UNIQUE (organization_id, hold_number), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_pos_held_bills_id ON srm_pos_held_bills (id);

CREATE INDEX ix_srm_pos_held_bills_status ON srm_pos_held_bills (status);

CREATE INDEX ix_srm_pos_held_bills_created_by ON srm_pos_held_bills (created_by);

CREATE INDEX ix_srm_pos_held_bills_deleted_at ON srm_pos_held_bills (deleted_at);

CREATE INDEX ix_srm_pos_held_bills_session_id ON srm_pos_held_bills (session_id);

CREATE INDEX ix_srm_pos_held_bills_hold_number ON srm_pos_held_bills (hold_number);

CREATE INDEX ix_srm_pos_held_bills_recalled_by ON srm_pos_held_bills (recalled_by);

CREATE INDEX ix_srm_pos_held_bills_created_at ON srm_pos_held_bills (created_at);

CREATE INDEX ix_srm_pos_held_bills_organization_id ON srm_pos_held_bills (organization_id);

CREATE INDEX ix_srm_pos_held_bills_customer_id ON srm_pos_held_bills (customer_id);

CREATE INDEX ix_srm_pos_held_bills_recalled_at ON srm_pos_held_bills (recalled_at);

CREATE TABLE srm_pos_returns (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	return_number VARCHAR(80) NOT NULL, 
	sales_order_id INTEGER, 
	session_id INTEGER, 
	customer_id INTEGER, 
	customer_name VARCHAR(220), 
	status VARCHAR(40), 
	refund_method VARCHAR(60), 
	refund_status VARCHAR(40), 
	subtotal NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	refund_amount NUMERIC(14, 2), 
	reason TEXT, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE SET NULL, 
	FOREIGN KEY(session_id) REFERENCES srm_pos_sessions (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_pos_return_org_number UNIQUE (organization_id, return_number), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_pos_returns_sales_order_id ON srm_pos_returns (sales_order_id);

CREATE INDEX ix_srm_pos_returns_customer_id ON srm_pos_returns (customer_id);

CREATE INDEX ix_srm_pos_returns_refund_status ON srm_pos_returns (refund_status);

CREATE INDEX ix_srm_pos_returns_organization_id ON srm_pos_returns (organization_id);

CREATE INDEX ix_srm_pos_returns_return_number ON srm_pos_returns (return_number);

CREATE INDEX ix_srm_pos_returns_status ON srm_pos_returns (status);

CREATE INDEX ix_srm_pos_returns_created_by ON srm_pos_returns (created_by);

CREATE INDEX ix_srm_pos_returns_session_id ON srm_pos_returns (session_id);

CREATE INDEX ix_srm_pos_returns_refund_method ON srm_pos_returns (refund_method);

CREATE INDEX ix_srm_pos_returns_created_at ON srm_pos_returns (created_at);

CREATE INDEX ix_srm_pos_returns_id ON srm_pos_returns (id);

CREATE TABLE srm_products (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	category_id INTEGER, 
	default_warehouse_id INTEGER, 
	sku VARCHAR(80) NOT NULL, 
	item_name VARCHAR(220) NOT NULL, 
	barcode VARCHAR(120), 
	description TEXT, 
	product_type VARCHAR(40), 
	category_name VARCHAR(180), 
	unit_code VARCHAR(40), 
	hsn_code VARCHAR(30), 
	gst_rate NUMERIC(6, 2), 
	purchase_rate NUMERIC(14, 2), 
	sales_rate NUMERIC(14, 2), 
	mrp NUMERIC(14, 2), 
	current_quantity NUMERIC(14, 3), 
	average_cost NUMERIC(14, 4), 
	reorder_level NUMERIC(14, 3), 
	min_stock NUMERIC(14, 3), 
	max_stock NUMERIC(14, 3), 
	track_inventory BOOLEAN, 
	batch_tracking BOOLEAN, 
	serial_tracking BOOLEAN, 
	expiry_tracking BOOLEAN, 
	active BOOLEAN, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_product_org_sku UNIQUE (organization_id, sku), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(category_id) REFERENCES srm_product_categories (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_product_org_barcode UNIQUE (organization_id, barcode), 
	FOREIGN KEY(default_warehouse_id) REFERENCES srm_warehouses (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_products_id ON srm_products (id);

CREATE INDEX ix_srm_products_category_id ON srm_products (category_id);

CREATE INDEX ix_srm_products_barcode ON srm_products (barcode);

CREATE INDEX ix_srm_products_category_name ON srm_products (category_name);

CREATE INDEX ix_srm_products_track_inventory ON srm_products (track_inventory);

CREATE INDEX ix_srm_products_created_at ON srm_products (created_at);

CREATE INDEX ix_srm_products_organization_id ON srm_products (organization_id);

CREATE INDEX ix_srm_products_item_name ON srm_products (item_name);

CREATE INDEX ix_srm_products_product_type ON srm_products (product_type);

CREATE INDEX ix_srm_products_unit_code ON srm_products (unit_code);

CREATE INDEX ix_srm_products_active ON srm_products (active);

CREATE INDEX ix_srm_products_default_warehouse_id ON srm_products (default_warehouse_id);

CREATE INDEX ix_srm_products_sku ON srm_products (sku);

CREATE INDEX ix_srm_products_hsn_code ON srm_products (hsn_code);

CREATE INDEX ix_srm_products_created_by ON srm_products (created_by);

CREATE TABLE srm_goods_receipts (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	grn_number VARCHAR(80) NOT NULL, 
	purchase_order_id INTEGER, 
	vendor_id INTEGER, 
	vendor_name VARCHAR(220), 
	status VARCHAR(40), 
	receipt_date DATE NOT NULL, 
	reference_number VARCHAR(120), 
	subtotal NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	total_amount NUMERIC(14, 2), 
	notes TEXT, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_goods_receipt_org_number UNIQUE (organization_id, grn_number), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(purchase_order_id) REFERENCES srm_purchase_orders (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_goods_receipts_vendor_name ON srm_goods_receipts (vendor_name);

CREATE INDEX ix_srm_goods_receipts_reference_number ON srm_goods_receipts (reference_number);

CREATE INDEX ix_srm_goods_receipts_purchase_order_id ON srm_goods_receipts (purchase_order_id);

CREATE INDEX ix_srm_goods_receipts_status ON srm_goods_receipts (status);

CREATE INDEX ix_srm_goods_receipts_created_by ON srm_goods_receipts (created_by);

CREATE INDEX ix_srm_goods_receipts_grn_number ON srm_goods_receipts (grn_number);

CREATE INDEX ix_srm_goods_receipts_vendor_id ON srm_goods_receipts (vendor_id);

CREATE INDEX ix_srm_goods_receipts_receipt_date ON srm_goods_receipts (receipt_date);

CREATE INDEX ix_srm_goods_receipts_created_at ON srm_goods_receipts (created_at);

CREATE INDEX ix_srm_goods_receipts_id ON srm_goods_receipts (id);

CREATE INDEX ix_srm_goods_receipts_organization_id ON srm_goods_receipts (organization_id);

CREATE TABLE srm_contracts (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	contract_number VARCHAR(80) NOT NULL, 
	sales_order_id INTEGER, 
	customer_id INTEGER, 
	title VARCHAR(220) NOT NULL, 
	status VARCHAR(40), 
	contract_type VARCHAR(80), 
	effective_date DATE, 
	expiry_date DATE, 
	contract_value NUMERIC(14, 2), 
	currency VARCHAR(10), 
	signed_by_customer_at TIMESTAMP WITH TIME ZONE, 
	signed_by_company_at TIMESTAMP WITH TIME ZONE, 
	terms TEXT, 
	created_by INTEGER, 
	approved_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_contract_org_number UNIQUE (organization_id, contract_number), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_contracts_organization_id ON srm_contracts (organization_id);

CREATE INDEX ix_srm_contracts_status ON srm_contracts (status);

CREATE INDEX ix_srm_contracts_created_at ON srm_contracts (created_at);

CREATE INDEX ix_srm_contracts_sales_order_id ON srm_contracts (sales_order_id);

CREATE INDEX ix_srm_contracts_customer_id ON srm_contracts (customer_id);

CREATE INDEX ix_srm_contracts_id ON srm_contracts (id);

CREATE INDEX ix_srm_contracts_contract_number ON srm_contracts (contract_number);

CREATE INDEX ix_srm_contracts_expiry_date ON srm_contracts (expiry_date);

CREATE TABLE fam_voucher_lines (
	id SERIAL NOT NULL, 
	voucher_id INTEGER NOT NULL, 
	line_number INTEGER NOT NULL, 
	ledger_id INTEGER NOT NULL, 
	debit_amount NUMERIC(14, 2), 
	credit_amount NUMERIC(14, 2), 
	narration TEXT, 
	cost_center_id INTEGER, 
	branch_id INTEGER, 
	party_id INTEGER, 
	tax_component_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(branch_id) REFERENCES fam_branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT, 
	FOREIGN KEY(cost_center_id) REFERENCES fam_cost_centers (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_voucher_lines_voucher_id ON fam_voucher_lines (voucher_id);

CREATE INDEX ix_fam_voucher_lines_party_id ON fam_voucher_lines (party_id);

CREATE INDEX ix_fam_voucher_lines_id ON fam_voucher_lines (id);

CREATE INDEX ix_fam_voucher_lines_cost_center_id ON fam_voucher_lines (cost_center_id);

CREATE INDEX ix_fam_voucher_lines_branch_id ON fam_voucher_lines (branch_id);

CREATE INDEX ix_fam_voucher_lines_ledger_id ON fam_voucher_lines (ledger_id);

CREATE INDEX ix_fam_voucher_lines_tax_component_id ON fam_voucher_lines (tax_component_id);

CREATE TABLE fam_voucher_audit_logs (
	id SERIAL NOT NULL, 
	voucher_id INTEGER NOT NULL, 
	action VARCHAR(80) NOT NULL, 
	old_value_json JSON, 
	new_value_json JSON, 
	performed_by INTEGER, 
	performed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE CASCADE, 
	FOREIGN KEY(performed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_voucher_audit_logs_voucher_id ON fam_voucher_audit_logs (voucher_id);

CREATE INDEX ix_fam_voucher_audit_logs_performed_by ON fam_voucher_audit_logs (performed_by);

CREATE INDEX ix_fam_voucher_audit_logs_performed_at ON fam_voucher_audit_logs (performed_at);

CREATE INDEX ix_fam_voucher_audit_logs_id ON fam_voucher_audit_logs (id);

CREATE INDEX ix_fam_voucher_audit_logs_action ON fam_voucher_audit_logs (action);

CREATE TABLE fam_posting_jobs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	source_module VARCHAR(40) NOT NULL, 
	source_record_type VARCHAR(80) NOT NULL, 
	source_record_id INTEGER NOT NULL, 
	posting_type VARCHAR(40) NOT NULL, 
	status VARCHAR(30), 
	error_message TEXT, 
	voucher_id INTEGER, 
	retry_count INTEGER, 
	posted_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_posting_job_source UNIQUE (company_id, source_module, source_record_type, source_record_id, posting_type)
);

CREATE INDEX ix_fam_posting_jobs_source_record_type ON fam_posting_jobs (source_record_type);

CREATE INDEX ix_fam_posting_jobs_source_record_id ON fam_posting_jobs (source_record_id);

CREATE INDEX ix_fam_posting_jobs_posted_at ON fam_posting_jobs (posted_at);

CREATE INDEX ix_fam_posting_jobs_id ON fam_posting_jobs (id);

CREATE INDEX ix_fam_posting_jobs_source_module ON fam_posting_jobs (source_module);

CREATE INDEX ix_fam_posting_jobs_status ON fam_posting_jobs (status);

CREATE INDEX ix_fam_posting_jobs_created_at ON fam_posting_jobs (created_at);

CREATE INDEX ix_fam_posting_jobs_company_id ON fam_posting_jobs (company_id);

CREATE INDEX ix_fam_posting_jobs_posting_type ON fam_posting_jobs (posting_type);

CREATE INDEX ix_fam_posting_jobs_voucher_id ON fam_posting_jobs (voucher_id);

CREATE TABLE fam_bank_statement_lines (
	id SERIAL NOT NULL, 
	statement_id INTEGER NOT NULL, 
	transaction_date DATE NOT NULL, 
	value_date DATE, 
	description TEXT NOT NULL, 
	reference_number VARCHAR(160), 
	debit_amount NUMERIC(14, 2), 
	credit_amount NUMERIC(14, 2), 
	balance NUMERIC(14, 2), 
	matched_status VARCHAR(30), 
	matched_voucher_id INTEGER, 
	line_hash VARCHAR(128) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_bank_statement_line_hash UNIQUE (statement_id, line_hash), 
	FOREIGN KEY(matched_voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL, 
	FOREIGN KEY(statement_id) REFERENCES fam_bank_statements (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_bank_statement_lines_value_date ON fam_bank_statement_lines (value_date);

CREATE INDEX ix_fam_bank_statement_lines_transaction_date ON fam_bank_statement_lines (transaction_date);

CREATE INDEX ix_fam_bank_statement_lines_matched_voucher_id ON fam_bank_statement_lines (matched_voucher_id);

CREATE INDEX ix_fam_bank_statement_lines_statement_id ON fam_bank_statement_lines (statement_id);

CREATE INDEX ix_fam_bank_statement_lines_id ON fam_bank_statement_lines (id);

CREATE INDEX ix_fam_bank_statement_lines_reference_number ON fam_bank_statement_lines (reference_number);

CREATE INDEX ix_fam_bank_statement_lines_line_hash ON fam_bank_statement_lines (line_hash);

CREATE INDEX ix_fam_bank_statement_lines_matched_status ON fam_bank_statement_lines (matched_status);

CREATE INDEX ix_fam_bank_statement_lines_created_at ON fam_bank_statement_lines (created_at);

CREATE TABLE fam_bank_reconciliation_sessions (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	bank_account_id INTEGER NOT NULL, 
	statement_id INTEGER NOT NULL, 
	book_balance NUMERIC(14, 2), 
	bank_statement_balance NUMERIC(14, 2), 
	unreconciled_count INTEGER, 
	status VARCHAR(30), 
	reconciled_by INTEGER, 
	reconciled_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(bank_account_id) REFERENCES fam_bank_accounts (id) ON DELETE CASCADE, 
	FOREIGN KEY(statement_id) REFERENCES fam_bank_statements (id) ON DELETE CASCADE, 
	FOREIGN KEY(reconciled_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_bank_reconciliation_sessions_status ON fam_bank_reconciliation_sessions (status);

CREATE INDEX ix_fam_bank_reconciliation_sessions_bank_account_id ON fam_bank_reconciliation_sessions (bank_account_id);

CREATE INDEX ix_fam_bank_reconciliation_sessions_reconciled_at ON fam_bank_reconciliation_sessions (reconciled_at);

CREATE INDEX ix_fam_bank_reconciliation_sessions_id ON fam_bank_reconciliation_sessions (id);

CREATE INDEX ix_fam_bank_reconciliation_sessions_reconciled_by ON fam_bank_reconciliation_sessions (reconciled_by);

CREATE INDEX ix_fam_bank_reconciliation_sessions_created_at ON fam_bank_reconciliation_sessions (created_at);

CREATE INDEX ix_fam_bank_reconciliation_sessions_company_id ON fam_bank_reconciliation_sessions (company_id);

CREATE INDEX ix_fam_bank_reconciliation_sessions_statement_id ON fam_bank_reconciliation_sessions (statement_id);

CREATE TABLE fam_gstr1_records (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	return_period_id INTEGER NOT NULL, 
	section VARCHAR(30) NOT NULL, 
	taxable_value NUMERIC(14, 2), 
	cgst_amount NUMERIC(14, 2), 
	sgst_amount NUMERIC(14, 2), 
	igst_amount NUMERIC(14, 2), 
	cess_amount NUMERIC(14, 2), 
	record_count INTEGER, 
	source_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(return_period_id) REFERENCES fam_gst_return_periods (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_gstr1_records_id ON fam_gstr1_records (id);

CREATE INDEX ix_fam_gstr1_records_section ON fam_gstr1_records (section);

CREATE INDEX ix_fam_gstr1_records_created_at ON fam_gstr1_records (created_at);

CREATE INDEX ix_fam_gstr1_records_return_period_id ON fam_gstr1_records (return_period_id);

CREATE INDEX ix_fam_gstr1_records_company_id ON fam_gstr1_records (company_id);

CREATE TABLE fam_gstr3b_records (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	return_period_id INTEGER NOT NULL, 
	section VARCHAR(30) NOT NULL, 
	taxable_value NUMERIC(14, 2), 
	cgst_amount NUMERIC(14, 2), 
	sgst_amount NUMERIC(14, 2), 
	igst_amount NUMERIC(14, 2), 
	cess_amount NUMERIC(14, 2), 
	source_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(return_period_id) REFERENCES fam_gst_return_periods (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_gstr3b_records_section ON fam_gstr3b_records (section);

CREATE INDEX ix_fam_gstr3b_records_created_at ON fam_gstr3b_records (created_at);

CREATE INDEX ix_fam_gstr3b_records_company_id ON fam_gstr3b_records (company_id);

CREATE INDEX ix_fam_gstr3b_records_return_period_id ON fam_gstr3b_records (return_period_id);

CREATE INDEX ix_fam_gstr3b_records_id ON fam_gstr3b_records (id);

CREATE TABLE fam_gst_reconciliation_items (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	return_period_id INTEGER, 
	source_type VARCHAR(40) NOT NULL, 
	source_record_id INTEGER, 
	mismatch_type VARCHAR(80) NOT NULL, 
	expected_amount NUMERIC(14, 2), 
	actual_amount NUMERIC(14, 2), 
	status VARCHAR(30), 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(return_period_id) REFERENCES fam_gst_return_periods (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_gst_reconciliation_items_return_period_id ON fam_gst_reconciliation_items (return_period_id);

CREATE INDEX ix_fam_gst_reconciliation_items_status ON fam_gst_reconciliation_items (status);

CREATE INDEX ix_fam_gst_reconciliation_items_id ON fam_gst_reconciliation_items (id);

CREATE INDEX ix_fam_gst_reconciliation_items_mismatch_type ON fam_gst_reconciliation_items (mismatch_type);

CREATE INDEX ix_fam_gst_reconciliation_items_created_at ON fam_gst_reconciliation_items (created_at);

CREATE INDEX ix_fam_gst_reconciliation_items_company_id ON fam_gst_reconciliation_items (company_id);

CREATE INDEX ix_fam_gst_reconciliation_items_source_type ON fam_gst_reconciliation_items (source_type);

CREATE INDEX ix_fam_gst_reconciliation_items_source_record_id ON fam_gst_reconciliation_items (source_record_id);

CREATE TABLE fam_einvoice_jobs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	voucher_id INTEGER NOT NULL, 
	action VARCHAR(30) NOT NULL, 
	status VARCHAR(30), 
	irn VARCHAR(120), 
	ack_number VARCHAR(120), 
	ack_date TIMESTAMP WITH TIME ZONE, 
	qr_code_payload TEXT, 
	provider_response_json JSON, 
	error_message TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_einvoice_jobs_id ON fam_einvoice_jobs (id);

CREATE INDEX ix_fam_einvoice_jobs_status ON fam_einvoice_jobs (status);

CREATE INDEX ix_fam_einvoice_jobs_created_at ON fam_einvoice_jobs (created_at);

CREATE INDEX ix_fam_einvoice_jobs_voucher_id ON fam_einvoice_jobs (voucher_id);

CREATE INDEX ix_fam_einvoice_jobs_irn ON fam_einvoice_jobs (irn);

CREATE INDEX ix_fam_einvoice_jobs_company_id ON fam_einvoice_jobs (company_id);

CREATE INDEX ix_fam_einvoice_jobs_action ON fam_einvoice_jobs (action);

CREATE INDEX ix_fam_einvoice_jobs_created_by ON fam_einvoice_jobs (created_by);

CREATE TABLE fam_ewaybill_jobs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	voucher_id INTEGER NOT NULL, 
	action VARCHAR(30) NOT NULL, 
	status VARCHAR(30), 
	transporter_details TEXT, 
	vehicle_number VARCHAR(40), 
	distance_km INTEGER, 
	supply_type VARCHAR(30), 
	document_type VARCHAR(30), 
	ewb_number VARCHAR(120), 
	ewb_date TIMESTAMP WITH TIME ZONE, 
	valid_until TIMESTAMP WITH TIME ZONE, 
	provider_response_json JSON, 
	error_message TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_ewaybill_jobs_id ON fam_ewaybill_jobs (id);

CREATE INDEX ix_fam_ewaybill_jobs_voucher_id ON fam_ewaybill_jobs (voucher_id);

CREATE INDEX ix_fam_ewaybill_jobs_ewb_number ON fam_ewaybill_jobs (ewb_number);

CREATE INDEX ix_fam_ewaybill_jobs_action ON fam_ewaybill_jobs (action);

CREATE INDEX ix_fam_ewaybill_jobs_created_by ON fam_ewaybill_jobs (created_by);

CREATE INDEX ix_fam_ewaybill_jobs_company_id ON fam_ewaybill_jobs (company_id);

CREATE INDEX ix_fam_ewaybill_jobs_status ON fam_ewaybill_jobs (status);

CREATE INDEX ix_fam_ewaybill_jobs_created_at ON fam_ewaybill_jobs (created_at);

CREATE TABLE fam_purchase_bills (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	bill_number VARCHAR(120) NOT NULL, 
	bill_date DATE NOT NULL, 
	due_date DATE, 
	gstin VARCHAR(20), 
	place_of_supply VARCHAR(4), 
	subtotal NUMERIC(14, 2), 
	discount_total NUMERIC(14, 2), 
	gst_total NUMERIC(14, 2), 
	tds_amount NUMERIC(14, 2), 
	grand_total NUMERIC(14, 2), 
	status VARCHAR(30), 
	voucher_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL, 
	FOREIGN KEY(vendor_id) REFERENCES fam_parties (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_fam_purchase_bill_vendor_number UNIQUE (company_id, vendor_id, bill_number)
);

CREATE INDEX ix_fam_purchase_bills_vendor_id ON fam_purchase_bills (vendor_id);

CREATE INDEX ix_fam_purchase_bills_bill_number ON fam_purchase_bills (bill_number);

CREATE INDEX ix_fam_purchase_bills_place_of_supply ON fam_purchase_bills (place_of_supply);

CREATE INDEX ix_fam_purchase_bills_created_at ON fam_purchase_bills (created_at);

CREATE INDEX ix_fam_purchase_bills_id ON fam_purchase_bills (id);

CREATE INDEX ix_fam_purchase_bills_company_id ON fam_purchase_bills (company_id);

CREATE INDEX ix_fam_purchase_bills_due_date ON fam_purchase_bills (due_date);

CREATE INDEX ix_fam_purchase_bills_status ON fam_purchase_bills (status);

CREATE INDEX ix_fam_purchase_bills_bill_date ON fam_purchase_bills (bill_date);

CREATE INDEX ix_fam_purchase_bills_gstin ON fam_purchase_bills (gstin);

CREATE INDEX ix_fam_purchase_bills_voucher_id ON fam_purchase_bills (voucher_id);

CREATE TABLE fam_expense_claims (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	claim_number VARCHAR(120) NOT NULL, 
	claimant_name VARCHAR(180), 
	claim_date DATE NOT NULL, 
	payable_ledger_id INTEGER, 
	subtotal NUMERIC(14, 2), 
	gst_total NUMERIC(14, 2), 
	grand_total NUMERIC(14, 2), 
	status VARCHAR(30), 
	voucher_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL, 
	FOREIGN KEY(payable_ledger_id) REFERENCES fam_ledgers (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_expense_claims_id ON fam_expense_claims (id);

CREATE INDEX ix_fam_expense_claims_payable_ledger_id ON fam_expense_claims (payable_ledger_id);

CREATE INDEX ix_fam_expense_claims_voucher_id ON fam_expense_claims (voucher_id);

CREATE INDEX ix_fam_expense_claims_claimant_name ON fam_expense_claims (claimant_name);

CREATE INDEX ix_fam_expense_claims_claim_date ON fam_expense_claims (claim_date);

CREATE INDEX ix_fam_expense_claims_created_at ON fam_expense_claims (created_at);

CREATE INDEX ix_fam_expense_claims_company_id ON fam_expense_claims (company_id);

CREATE INDEX ix_fam_expense_claims_claim_number ON fam_expense_claims (claim_number);

CREATE INDEX ix_fam_expense_claims_status ON fam_expense_claims (status);

CREATE TABLE fam_tds_transactions (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	voucher_id INTEGER, 
	vendor_id INTEGER, 
	section_id INTEGER, 
	taxable_amount NUMERIC(14, 2), 
	tds_rate NUMERIC(7, 3), 
	tds_amount NUMERIC(14, 2), 
	deduction_date DATE NOT NULL, 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES fam_tds_sections (id) ON DELETE SET NULL, 
	FOREIGN KEY(vendor_id) REFERENCES fam_parties (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_tds_transactions_vendor_id ON fam_tds_transactions (vendor_id);

CREATE INDEX ix_fam_tds_transactions_section_id ON fam_tds_transactions (section_id);

CREATE INDEX ix_fam_tds_transactions_company_id ON fam_tds_transactions (company_id);

CREATE INDEX ix_fam_tds_transactions_voucher_id ON fam_tds_transactions (voucher_id);

CREATE INDEX ix_fam_tds_transactions_status ON fam_tds_transactions (status);

CREATE INDEX ix_fam_tds_transactions_id ON fam_tds_transactions (id);

CREATE INDEX ix_fam_tds_transactions_deduction_date ON fam_tds_transactions (deduction_date);

CREATE INDEX ix_fam_tds_transactions_created_at ON fam_tds_transactions (created_at);

CREATE TABLE fam_vendor_payment_runs (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	run_number VARCHAR(120) NOT NULL, 
	payment_date DATE NOT NULL, 
	bank_ledger_id INTEGER NOT NULL, 
	total_amount NUMERIC(14, 2), 
	status VARCHAR(30), 
	voucher_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(bank_ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_vendor_payment_runs_company_id ON fam_vendor_payment_runs (company_id);

CREATE INDEX ix_fam_vendor_payment_runs_run_number ON fam_vendor_payment_runs (run_number);

CREATE INDEX ix_fam_vendor_payment_runs_voucher_id ON fam_vendor_payment_runs (voucher_id);

CREATE INDEX ix_fam_vendor_payment_runs_id ON fam_vendor_payment_runs (id);

CREATE INDEX ix_fam_vendor_payment_runs_status ON fam_vendor_payment_runs (status);

CREATE INDEX ix_fam_vendor_payment_runs_created_at ON fam_vendor_payment_runs (created_at);

CREATE INDEX ix_fam_vendor_payment_runs_payment_date ON fam_vendor_payment_runs (payment_date);

CREATE INDEX ix_fam_vendor_payment_runs_bank_ledger_id ON fam_vendor_payment_runs (bank_ledger_id);

CREATE TABLE fam_stock_opening_balances (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	opening_number VARCHAR(120) NOT NULL, 
	opening_date DATE NOT NULL, 
	stock_item_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	rate NUMERIC(14, 4), 
	value NUMERIC(14, 2), 
	notes TEXT, 
	voucher_id INTEGER, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(warehouse_id) REFERENCES fam_warehouses (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_fam_stock_opening_item_warehouse_date UNIQUE (company_id, stock_item_id, warehouse_id, opening_date), 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL, 
	FOREIGN KEY(stock_item_id) REFERENCES fam_stock_items (id) ON DELETE RESTRICT
);

CREATE INDEX ix_fam_stock_opening_balances_id ON fam_stock_opening_balances (id);

CREATE INDEX ix_fam_stock_opening_balances_warehouse_id ON fam_stock_opening_balances (warehouse_id);

CREATE INDEX ix_fam_stock_opening_balances_created_at ON fam_stock_opening_balances (created_at);

CREATE INDEX ix_fam_stock_opening_balances_stock_item_id ON fam_stock_opening_balances (stock_item_id);

CREATE INDEX ix_fam_stock_opening_balances_voucher_id ON fam_stock_opening_balances (voucher_id);

CREATE INDEX ix_fam_stock_opening_balances_opening_number ON fam_stock_opening_balances (opening_number);

CREATE INDEX ix_fam_stock_opening_balances_opening_date ON fam_stock_opening_balances (opening_date);

CREATE INDEX ix_fam_stock_opening_balances_created_by ON fam_stock_opening_balances (created_by);

CREATE INDEX ix_fam_stock_opening_balances_company_id ON fam_stock_opening_balances (company_id);

CREATE TABLE fam_stock_movements (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	movement_number VARCHAR(120) NOT NULL, 
	movement_date DATE NOT NULL, 
	movement_type VARCHAR(40) NOT NULL, 
	status VARCHAR(30), 
	source_module VARCHAR(40), 
	source_record_type VARCHAR(80), 
	source_record_id VARCHAR(120), 
	reference_number VARCHAR(120), 
	narration TEXT, 
	voucher_id INTEGER, 
	created_by INTEGER, 
	posted_by INTEGER, 
	posted_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_stock_movement_company_number UNIQUE (company_id, movement_number), 
	FOREIGN KEY(posted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_stock_movements_id ON fam_stock_movements (id);

CREATE INDEX ix_fam_stock_movements_movement_number ON fam_stock_movements (movement_number);

CREATE INDEX ix_fam_stock_movements_status ON fam_stock_movements (status);

CREATE INDEX ix_fam_stock_movements_source_record_id ON fam_stock_movements (source_record_id);

CREATE INDEX ix_fam_stock_movements_created_by ON fam_stock_movements (created_by);

CREATE INDEX ix_fam_stock_movements_created_at ON fam_stock_movements (created_at);

CREATE INDEX ix_fam_stock_movements_company_id ON fam_stock_movements (company_id);

CREATE INDEX ix_fam_stock_movements_movement_date ON fam_stock_movements (movement_date);

CREATE INDEX ix_fam_stock_movements_source_module ON fam_stock_movements (source_module);

CREATE INDEX ix_fam_stock_movements_reference_number ON fam_stock_movements (reference_number);

CREATE INDEX ix_fam_stock_movements_posted_by ON fam_stock_movements (posted_by);

CREATE INDEX ix_fam_stock_movements_movement_type ON fam_stock_movements (movement_type);

CREATE INDEX ix_fam_stock_movements_source_record_type ON fam_stock_movements (source_record_type);

CREATE INDEX ix_fam_stock_movements_voucher_id ON fam_stock_movements (voucher_id);

CREATE INDEX ix_fam_stock_movements_posted_at ON fam_stock_movements (posted_at);

CREATE TABLE fam_inventory_reservations (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	reservation_number VARCHAR(120) NOT NULL, 
	stock_item_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	quantity NUMERIC(14, 3) NOT NULL, 
	reserved_quantity NUMERIC(14, 3) NOT NULL, 
	source_module VARCHAR(40) NOT NULL, 
	source_record_type VARCHAR(80) NOT NULL, 
	source_record_id VARCHAR(120) NOT NULL, 
	status VARCHAR(30), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	released_at TIMESTAMP WITH TIME ZONE, 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(stock_item_id) REFERENCES fam_stock_items (id) ON DELETE RESTRICT, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(warehouse_id) REFERENCES fam_warehouses (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_inventory_reservation_source_item UNIQUE (company_id, source_module, source_record_type, source_record_id, stock_item_id)
);

CREATE INDEX ix_fam_inventory_reservations_stock_item_id ON fam_inventory_reservations (stock_item_id);

CREATE INDEX ix_fam_inventory_reservations_source_record_type ON fam_inventory_reservations (source_record_type);

CREATE INDEX ix_fam_inventory_reservations_expires_at ON fam_inventory_reservations (expires_at);

CREATE INDEX ix_fam_inventory_reservations_created_at ON fam_inventory_reservations (created_at);

CREATE INDEX ix_fam_inventory_reservations_reservation_number ON fam_inventory_reservations (reservation_number);

CREATE INDEX ix_fam_inventory_reservations_warehouse_id ON fam_inventory_reservations (warehouse_id);

CREATE INDEX ix_fam_inventory_reservations_source_record_id ON fam_inventory_reservations (source_record_id);

CREATE INDEX ix_fam_inventory_reservations_released_at ON fam_inventory_reservations (released_at);

CREATE INDEX ix_fam_inventory_reservations_id ON fam_inventory_reservations (id);

CREATE INDEX ix_fam_inventory_reservations_company_id ON fam_inventory_reservations (company_id);

CREATE INDEX ix_fam_inventory_reservations_source_module ON fam_inventory_reservations (source_module);

CREATE INDEX ix_fam_inventory_reservations_status ON fam_inventory_reservations (status);

CREATE INDEX ix_fam_inventory_reservations_created_by ON fam_inventory_reservations (created_by);

CREATE TABLE fam_inventory_integration_links (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	stock_item_id INTEGER NOT NULL, 
	target_module VARCHAR(40) NOT NULL, 
	target_record_type VARCHAR(80) NOT NULL, 
	target_record_id VARCHAR(120) NOT NULL, 
	link_type VARCHAR(60), 
	metadata_json JSON, 
	active BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fam_inventory_link_target UNIQUE (company_id, stock_item_id, target_module, target_record_type, target_record_id), 
	FOREIGN KEY(stock_item_id) REFERENCES fam_stock_items (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_inventory_integration_links_target_record_id ON fam_inventory_integration_links (target_record_id);

CREATE INDEX ix_fam_inventory_integration_links_link_type ON fam_inventory_integration_links (link_type);

CREATE INDEX ix_fam_inventory_integration_links_created_at ON fam_inventory_integration_links (created_at);

CREATE INDEX ix_fam_inventory_integration_links_stock_item_id ON fam_inventory_integration_links (stock_item_id);

CREATE INDEX ix_fam_inventory_integration_links_target_module ON fam_inventory_integration_links (target_module);

CREATE INDEX ix_fam_inventory_integration_links_active ON fam_inventory_integration_links (active);

CREATE INDEX ix_fam_inventory_integration_links_company_id ON fam_inventory_integration_links (company_id);

CREATE INDEX ix_fam_inventory_integration_links_target_record_type ON fam_inventory_integration_links (target_record_type);

CREATE INDEX ix_fam_inventory_integration_links_created_by ON fam_inventory_integration_links (created_by);

CREATE INDEX ix_fam_inventory_integration_links_id ON fam_inventory_integration_links (id);

CREATE TABLE onboarding_tasks (
	id SERIAL NOT NULL, 
	template_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	category VARCHAR(50), 
	assigned_to_role VARCHAR(50), 
	due_days INTEGER, 
	is_mandatory BOOLEAN, 
	order_sequence INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT onboarding_tasks_ibfk_1 FOREIGN KEY(template_id) REFERENCES onboarding_templates (id) ON DELETE CASCADE
);

CREATE INDEX template_id ON onboarding_tasks (template_id);

CREATE INDEX ix_onboarding_tasks_id ON onboarding_tasks (id);

CREATE TABLE headcount_plans (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	company_id INTEGER NOT NULL, 
	business_unit_id INTEGER, 
	department_id INTEGER, 
	planned_headcount INTEGER, 
	approved_headcount INTEGER, 
	planned_budget NUMERIC(14, 2), 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_headcount_plans_id ON headcount_plans (id);

CREATE INDEX ix_headcount_plans_status ON headcount_plans (status);

CREATE INDEX ix_headcount_plans_business_unit_id ON headcount_plans (business_unit_id);

CREATE INDEX ix_headcount_plans_department_id ON headcount_plans (department_id);

CREATE INDEX ix_headcount_plans_financial_year ON headcount_plans (financial_year);

CREATE INDEX ix_headcount_plans_company_id ON headcount_plans (company_id);

CREATE TABLE designations (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(20), 
	organization_id INTEGER, 
	department_id INTEGER NOT NULL, 
	grade VARCHAR(20), 
	level INTEGER, 
	description TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_designations_id ON designations (id);

CREATE INDEX ix_designations_organization_id ON designations (organization_id);

CREATE INDEX ix_designations_name ON designations (name);

CREATE TABLE workflow_tasks (
	id SERIAL NOT NULL, 
	instance_id INTEGER NOT NULL, 
	step_definition_id INTEGER, 
	assigned_to_user_id INTEGER, 
	assigned_role VARCHAR(120), 
	original_assigned_to_user_id INTEGER, 
	original_assigned_role VARCHAR(120), 
	delegated_to_user_id INTEGER, 
	delegated_role VARCHAR(120), 
	delegation_reason TEXT, 
	delegation_started_at TIMESTAMP WITH TIME ZONE, 
	delegation_ends_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(30), 
	due_at TIMESTAMP WITH TIME ZONE, 
	reminder_sent_at TIMESTAMP WITH TIME ZONE, 
	escalated_at TIMESTAMP WITH TIME ZONE, 
	escalated_to_user_id INTEGER, 
	decision VARCHAR(30), 
	decision_reason TEXT, 
	decided_by INTEGER, 
	decided_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(instance_id) REFERENCES workflow_instances (id) ON DELETE CASCADE, 
	FOREIGN KEY(escalated_to_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(original_assigned_to_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(step_definition_id) REFERENCES workflow_step_definitions (id) ON DELETE SET NULL, 
	FOREIGN KEY(decided_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(delegated_to_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_to_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_workflow_tasks_assigned_to_user_id ON workflow_tasks (assigned_to_user_id);

CREATE INDEX ix_workflow_tasks_instance_id ON workflow_tasks (instance_id);

CREATE INDEX ix_workflow_tasks_id ON workflow_tasks (id);

CREATE INDEX ix_workflow_tasks_assigned_role ON workflow_tasks (assigned_role);

CREATE INDEX ix_workflow_tasks_status ON workflow_tasks (status);

CREATE TABLE customization_layout_fields (
	id SERIAL NOT NULL, 
	layout_id INTEGER NOT NULL, 
	section_id INTEGER, 
	field_id INTEGER NOT NULL, 
	order_index INTEGER, 
	required_override BOOLEAN, 
	readonly BOOLEAN, 
	hidden BOOLEAN, 
	role_visibility_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(field_id) REFERENCES customization_fields (id) ON DELETE CASCADE, 
	FOREIGN KEY(section_id) REFERENCES customization_layout_sections (id) ON DELETE SET NULL, 
	FOREIGN KEY(layout_id) REFERENCES customization_layouts (id) ON DELETE CASCADE
);

CREATE INDEX ix_customization_layout_fields_section_id ON customization_layout_fields (section_id);

CREATE INDEX ix_customization_layout_fields_layout_id ON customization_layout_fields (layout_id);

CREATE INDEX ix_customization_layout_fields_field_id ON customization_layout_fields (field_id);

CREATE INDEX ix_customization_layout_fields_id ON customization_layout_fields (id);

CREATE TABLE communication_webforms (
	id SERIAL NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	target_module VARCHAR(40) NOT NULL, 
	public_slug VARCHAR(140) NOT NULL, 
	fields_json JSON, 
	mapping_json JSON, 
	active BOOLEAN, 
	auto_response_rule_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(auto_response_rule_id) REFERENCES communication_auto_response_rules (id) ON DELETE SET NULL, 
	CONSTRAINT uq_communication_webform_slug UNIQUE (public_slug)
);

CREATE INDEX ix_communication_webforms_id ON communication_webforms (id);

CREATE INDEX ix_communication_webforms_created_at ON communication_webforms (created_at);

CREATE INDEX ix_communication_webforms_public_slug ON communication_webforms (public_slug);

CREATE INDEX ix_communication_webforms_active ON communication_webforms (active);

CREATE INDEX ix_communication_webforms_name ON communication_webforms (name);

CREATE INDEX ix_communication_webforms_target_module ON communication_webforms (target_module);

CREATE TABLE communication_campaign_members (
	id SERIAL NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	record_type VARCHAR(60) NOT NULL, 
	record_id INTEGER NOT NULL, 
	email VARCHAR(180) NOT NULL, 
	status VARCHAR(40), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_communication_campaign_member_record UNIQUE (campaign_id, record_type, record_id), 
	FOREIGN KEY(campaign_id) REFERENCES communication_campaigns (id) ON DELETE CASCADE
);

CREATE INDEX ix_communication_campaign_members_record_id ON communication_campaign_members (record_id);

CREATE INDEX ix_communication_campaign_members_email ON communication_campaign_members (email);

CREATE INDEX ix_communication_campaign_members_id ON communication_campaign_members (id);

CREATE INDEX ix_communication_campaign_members_record_type ON communication_campaign_members (record_type);

CREATE INDEX ix_communication_campaign_members_campaign_id ON communication_campaign_members (campaign_id);

CREATE INDEX ix_communication_campaign_members_status ON communication_campaign_members (status);

CREATE TABLE analytics_export_audit_logs (
	id SERIAL NOT NULL, 
	export_id INTEGER, 
	report_id INTEGER, 
	actor_user_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	metadata_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES analytics_reports (id) ON DELETE SET NULL, 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(export_id) REFERENCES analytics_exports (id) ON DELETE SET NULL
);

CREATE INDEX ix_analytics_export_audit_logs_id ON analytics_export_audit_logs (id);

CREATE INDEX ix_analytics_export_audit_logs_report_id ON analytics_export_audit_logs (report_id);

CREATE INDEX ix_analytics_export_audit_logs_export_id ON analytics_export_audit_logs (export_id);

CREATE INDEX ix_analytics_export_audit_logs_created_at ON analytics_export_audit_logs (created_at);

CREATE INDEX ix_analytics_export_audit_logs_actor_user_id ON analytics_export_audit_logs (actor_user_id);

CREATE INDEX ix_analytics_export_audit_logs_action ON analytics_export_audit_logs (action);

CREATE TABLE ai_record_summaries (
	id SERIAL NOT NULL, 
	prompt_run_id INTEGER, 
	module_name VARCHAR(80) NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	record_id INTEGER NOT NULL, 
	summary_text TEXT NOT NULL, 
	source_summary_json JSON, 
	confidence FLOAT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(prompt_run_id) REFERENCES ai_prompt_runs (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_record_summaries_id ON ai_record_summaries (id);

CREATE INDEX ix_ai_record_summaries_module_name ON ai_record_summaries (module_name);

CREATE INDEX ix_ai_record_summaries_created_at ON ai_record_summaries (created_at);

CREATE INDEX ix_ai_record_summaries_prompt_run_id ON ai_record_summaries (prompt_run_id);

CREATE INDEX ix_ai_record_summaries_created_by ON ai_record_summaries (created_by);

CREATE INDEX ix_ai_record_summaries_record_type ON ai_record_summaries (record_type);

CREATE INDEX ix_ai_record_summaries_record_id ON ai_record_summaries (record_id);

CREATE TABLE ai_scores (
	id SERIAL NOT NULL, 
	prompt_run_id INTEGER, 
	use_case VARCHAR(80) NOT NULL, 
	module_name VARCHAR(80) NOT NULL, 
	record_type VARCHAR(80) NOT NULL, 
	record_id INTEGER NOT NULL, 
	score FLOAT, 
	probability FLOAT, 
	label VARCHAR(80), 
	reasons_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(prompt_run_id) REFERENCES ai_prompt_runs (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_scores_record_id ON ai_scores (record_id);

CREATE INDEX ix_ai_scores_created_at ON ai_scores (created_at);

CREATE INDEX ix_ai_scores_module_name ON ai_scores (module_name);

CREATE INDEX ix_ai_scores_record_type ON ai_scores (record_type);

CREATE INDEX ix_ai_scores_id ON ai_scores (id);

CREATE INDEX ix_ai_scores_use_case ON ai_scores (use_case);

CREATE INDEX ix_ai_scores_created_by ON ai_scores (created_by);

CREATE INDEX ix_ai_scores_prompt_run_id ON ai_scores (prompt_run_id);

CREATE TABLE ai_recommendations (
	id SERIAL NOT NULL, 
	prompt_run_id INTEGER, 
	use_case VARCHAR(80) NOT NULL, 
	module_name VARCHAR(80) NOT NULL, 
	record_type VARCHAR(80), 
	record_id INTEGER, 
	recommendation_text TEXT NOT NULL, 
	confidence FLOAT, 
	reasons_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(prompt_run_id) REFERENCES ai_prompt_runs (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_recommendations_module_name ON ai_recommendations (module_name);

CREATE INDEX ix_ai_recommendations_record_type ON ai_recommendations (record_type);

CREATE INDEX ix_ai_recommendations_created_at ON ai_recommendations (created_at);

CREATE INDEX ix_ai_recommendations_id ON ai_recommendations (id);

CREATE INDEX ix_ai_recommendations_use_case ON ai_recommendations (use_case);

CREATE INDEX ix_ai_recommendations_created_by ON ai_recommendations (created_by);

CREATE INDEX ix_ai_recommendations_prompt_run_id ON ai_recommendations (prompt_run_id);

CREATE INDEX ix_ai_recommendations_record_id ON ai_recommendations (record_id);

CREATE TABLE ai_agent_actions (
	id SERIAL NOT NULL, 
	prompt_run_id INTEGER, 
	action_type VARCHAR(80) NOT NULL, 
	module_name VARCHAR(80) NOT NULL, 
	record_type VARCHAR(80), 
	record_id INTEGER, 
	preview_json JSON, 
	result_json JSON, 
	status VARCHAR(40), 
	requires_confirmation BOOLEAN, 
	created_by INTEGER, 
	confirmed_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	confirmed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(confirmed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(prompt_run_id) REFERENCES ai_prompt_runs (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_agent_actions_action_type ON ai_agent_actions (action_type);

CREATE INDEX ix_ai_agent_actions_record_type ON ai_agent_actions (record_type);

CREATE INDEX ix_ai_agent_actions_created_at ON ai_agent_actions (created_at);

CREATE INDEX ix_ai_agent_actions_prompt_run_id ON ai_agent_actions (prompt_run_id);

CREATE INDEX ix_ai_agent_actions_module_name ON ai_agent_actions (module_name);

CREATE INDEX ix_ai_agent_actions_status ON ai_agent_actions (status);

CREATE INDEX ix_ai_agent_actions_id ON ai_agent_actions (id);

CREATE INDEX ix_ai_agent_actions_record_id ON ai_agent_actions (record_id);

CREATE INDEX ix_ai_agent_actions_created_by ON ai_agent_actions (created_by);

CREATE TABLE ai_messages (
	id SERIAL NOT NULL, 
	conversation_id INTEGER, 
	role VARCHAR(30) NOT NULL, 
	content TEXT, 
	tool_call_json JSON, 
	tool_result_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_messages_id ON ai_messages (id);

CREATE INDEX ix_ai_messages_role ON ai_messages (role);

CREATE INDEX ix_ai_messages_conversation_id ON ai_messages (conversation_id);

CREATE TABLE ai_action_approvals (
	id SERIAL NOT NULL, 
	conversation_id INTEGER, 
	agent_id INTEGER, 
	user_id INTEGER, 
	module VARCHAR(40) NOT NULL, 
	action_type VARCHAR(120) NOT NULL, 
	related_entity_type VARCHAR(80), 
	related_entity_id VARCHAR(80), 
	proposed_action_json JSON NOT NULL, 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	execution_status VARCHAR(30), 
	executed_at TIMESTAMP WITH TIME ZONE, 
	execution_result_json JSON, 
	execution_error TEXT, 
	idempotency_key VARCHAR(160), 
	rejected_reason TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_action_approvals_related_entity_id ON ai_action_approvals (related_entity_id);

CREATE INDEX ix_ai_action_approvals_idempotency_key ON ai_action_approvals (idempotency_key);

CREATE INDEX ix_ai_action_approvals_conversation_id ON ai_action_approvals (conversation_id);

CREATE INDEX ix_ai_action_approvals_id ON ai_action_approvals (id);

CREATE INDEX ix_ai_action_approvals_module ON ai_action_approvals (module);

CREATE INDEX ix_ai_action_approvals_status ON ai_action_approvals (status);

CREATE INDEX ix_ai_action_approvals_agent_id ON ai_action_approvals (agent_id);

CREATE INDEX ix_ai_action_approvals_related_entity_type ON ai_action_approvals (related_entity_type);

CREATE INDEX ix_ai_action_approvals_execution_status ON ai_action_approvals (execution_status);

CREATE INDEX ix_ai_action_approvals_user_id ON ai_action_approvals (user_id);

CREATE INDEX ix_ai_action_approvals_action_type ON ai_action_approvals (action_type);

CREATE TABLE ai_cost_logs (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	user_id INTEGER, 
	agent_id INTEGER, 
	conversation_id INTEGER, 
	model VARCHAR(80), 
	input_tokens INTEGER, 
	output_tokens INTEGER, 
	total_tokens INTEGER, 
	estimated_cost NUMERIC(12, 6), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_cost_logs_id ON ai_cost_logs (id);

CREATE INDEX ix_ai_cost_logs_agent_id ON ai_cost_logs (agent_id);

CREATE INDEX ix_ai_cost_logs_created_at ON ai_cost_logs (created_at);

CREATE INDEX ix_ai_cost_logs_company_id ON ai_cost_logs (company_id);

CREATE INDEX ix_ai_cost_logs_model ON ai_cost_logs (model);

CREATE INDEX ix_ai_cost_logs_user_id ON ai_cost_logs (user_id);

CREATE INDEX ix_ai_cost_logs_conversation_id ON ai_cost_logs (conversation_id);

CREATE TABLE ai_handoff_notes (
	id SERIAL NOT NULL, 
	conversation_id INTEGER, 
	agent_id INTEGER, 
	module VARCHAR(40) NOT NULL, 
	related_entity_type VARCHAR(80), 
	related_entity_id VARCHAR(80), 
	assigned_to INTEGER, 
	priority VARCHAR(20), 
	summary VARCHAR(300) NOT NULL, 
	reason TEXT, 
	recommended_action TEXT, 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_handoff_notes_created_by ON ai_handoff_notes (created_by);

CREATE INDEX ix_ai_handoff_notes_id ON ai_handoff_notes (id);

CREATE INDEX ix_ai_handoff_notes_related_entity_type ON ai_handoff_notes (related_entity_type);

CREATE INDEX ix_ai_handoff_notes_priority ON ai_handoff_notes (priority);

CREATE INDEX ix_ai_handoff_notes_created_at ON ai_handoff_notes (created_at);

CREATE INDEX ix_ai_handoff_notes_module ON ai_handoff_notes (module);

CREATE INDEX ix_ai_handoff_notes_related_entity_id ON ai_handoff_notes (related_entity_id);

CREATE INDEX ix_ai_handoff_notes_status ON ai_handoff_notes (status);

CREATE INDEX ix_ai_handoff_notes_conversation_id ON ai_handoff_notes (conversation_id);

CREATE INDEX ix_ai_handoff_notes_agent_id ON ai_handoff_notes (agent_id);

CREATE INDEX ix_ai_handoff_notes_assigned_to ON ai_handoff_notes (assigned_to);

CREATE TABLE payroll_calendars (
	id SERIAL NOT NULL, 
	pay_group_id INTEGER NOT NULL, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	payroll_date DATE NOT NULL, 
	attendance_cutoff_date DATE, 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(pay_group_id) REFERENCES payroll_pay_groups (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_calendars_pay_group_id ON payroll_calendars (pay_group_id);

CREATE INDEX ix_payroll_calendars_id ON payroll_calendars (id);

CREATE TABLE payroll_periods (
	id SERIAL NOT NULL, 
	pay_group_id INTEGER NOT NULL, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	attendance_cutoff_at TIMESTAMP WITH TIME ZONE, 
	input_cutoff_at TIMESTAMP WITH TIME ZONE, 
	payroll_date DATE NOT NULL, 
	status VARCHAR(30), 
	locked_by INTEGER, 
	locked_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(pay_group_id) REFERENCES payroll_pay_groups (id) ON DELETE CASCADE, 
	FOREIGN KEY(locked_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_periods_financial_year ON payroll_periods (financial_year);

CREATE INDEX ix_payroll_periods_status ON payroll_periods (status);

CREATE INDEX ix_payroll_periods_id ON payroll_periods (id);

CREATE INDEX ix_payroll_periods_pay_group_id ON payroll_periods (pay_group_id);

CREATE TABLE salary_templates (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	pay_group_id INTEGER, 
	grade VARCHAR(80), 
	location VARCHAR(120), 
	description TEXT, 
	residual_component_id INTEGER, 
	effective_from DATE, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(pay_group_id) REFERENCES payroll_pay_groups (id) ON DELETE SET NULL, 
	FOREIGN KEY(residual_component_id) REFERENCES salary_components (id) ON DELETE SET NULL
);

CREATE INDEX ix_salary_templates_pay_group_id ON salary_templates (pay_group_id);

CREATE INDEX ix_salary_templates_id ON salary_templates (id);

CREATE INDEX ix_salary_templates_is_active ON salary_templates (is_active);

CREATE TABLE overtime_policies (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	pay_group_id INTEGER, 
	wage_base VARCHAR(50), 
	regular_multiplier NUMERIC(6, 2), 
	weekend_multiplier NUMERIC(6, 2), 
	holiday_multiplier NUMERIC(6, 2), 
	min_hours NUMERIC(6, 2), 
	max_hours_per_month NUMERIC(6, 2), 
	component_id INTEGER, 
	approval_required BOOLEAN, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES salary_components (id) ON DELETE SET NULL, 
	FOREIGN KEY(pay_group_id) REFERENCES payroll_pay_groups (id) ON DELETE SET NULL
);

CREATE INDEX ix_overtime_policies_pay_group_id ON overtime_policies (pay_group_id);

CREATE INDEX ix_overtime_policies_id ON overtime_policies (id);

CREATE INDEX ix_overtime_policies_is_active ON overtime_policies (is_active);

CREATE TABLE leave_encashment_policies (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	leave_type_id INTEGER NOT NULL, 
	pay_group_id INTEGER, 
	formula VARCHAR(120), 
	max_days NUMERIC(6, 2), 
	tax_treatment VARCHAR(50), 
	component_id INTEGER, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES salary_components (id) ON DELETE SET NULL, 
	FOREIGN KEY(pay_group_id) REFERENCES payroll_pay_groups (id) ON DELETE SET NULL, 
	FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE CASCADE
);

CREATE INDEX ix_leave_encashment_policies_pay_group_id ON leave_encashment_policies (pay_group_id);

CREATE INDEX ix_leave_encashment_policies_leave_type_id ON leave_encashment_policies (leave_type_id);

CREATE INDEX ix_leave_encashment_policies_is_active ON leave_encashment_policies (is_active);

CREATE INDEX ix_leave_encashment_policies_id ON leave_encashment_policies (id);

CREATE TABLE payroll_runs (
	id SERIAL NOT NULL, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	company_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	pay_group_id INTEGER, 
	employee_category VARCHAR(80), 
	pay_period_start DATE, 
	pay_period_end DATE, 
	run_date DATE, 
	status VARCHAR(20), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	locked_by INTEGER, 
	locked_at TIMESTAMP WITH TIME ZONE, 
	total_gross NUMERIC(16, 2), 
	total_deductions NUMERIC(16, 2), 
	total_net NUMERIC(16, 2), 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	deleted_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(locked_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(pay_group_id) REFERENCES payroll_pay_groups (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(deleted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_runs_department_id ON payroll_runs (department_id);

CREATE INDEX idx_payroll_run_active_month ON payroll_runs (deleted_at, year, month);

CREATE INDEX ix_payroll_runs_id ON payroll_runs (id);

CREATE INDEX ix_payroll_runs_branch_id ON payroll_runs (branch_id);

CREATE INDEX ix_payroll_runs_employee_category ON payroll_runs (employee_category);

CREATE INDEX idx_payroll_run_period ON payroll_runs (pay_period_start, pay_period_end, company_id);

CREATE INDEX idx_payroll_run_company_active_month ON payroll_runs (company_id, deleted_at, year, month);

CREATE INDEX ix_payroll_runs_pay_group_id ON payroll_runs (pay_group_id);

CREATE INDEX idx_payroll_run_company_status_month ON payroll_runs (company_id, status, year, month);

CREATE TABLE payroll_gl_mappings (
	id SERIAL NOT NULL, 
	component_name VARCHAR(120) NOT NULL, 
	component_type VARCHAR(50) NOT NULL, 
	debit_ledger_id INTEGER, 
	credit_ledger_id INTEGER, 
	legal_entity_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	cost_center VARCHAR(100), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE SET NULL, 
	FOREIGN KEY(debit_ledger_id) REFERENCES accounting_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(credit_ledger_id) REFERENCES accounting_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_gl_mappings_id ON payroll_gl_mappings (id);

CREATE INDEX ix_payroll_gl_mappings_component_name ON payroll_gl_mappings (component_name);

CREATE INDEX ix_payroll_gl_mappings_is_active ON payroll_gl_mappings (is_active);

CREATE INDEX ix_payroll_gl_mappings_legal_entity_id ON payroll_gl_mappings (legal_entity_id);

CREATE TABLE bonus_policies (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	bonus_type VARCHAR(60), 
	amount_type VARCHAR(30), 
	amount_value NUMERIC(12, 2) NOT NULL, 
	applicable_month INTEGER, 
	department_id INTEGER, 
	grade_band_id INTEGER, 
	is_active BOOLEAN, 
	description TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(grade_band_id) REFERENCES grade_bands (id) ON DELETE SET NULL
);

CREATE INDEX ix_bonus_policies_bonus_type ON bonus_policies (bonus_type);

CREATE INDEX ix_bonus_policies_grade_band_id ON bonus_policies (grade_band_id);

CREATE INDEX ix_bonus_policies_id ON bonus_policies (id);

CREATE INDEX ix_bonus_policies_department_id ON bonus_policies (department_id);

CREATE INDEX ix_bonus_policies_is_active ON bonus_policies (is_active);

CREATE TABLE payroll_budgets (
	id SERIAL NOT NULL, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	department_id INTEGER, 
	cost_center_id INTEGER, 
	budget_amount NUMERIC(16, 2) NOT NULL, 
	currency VARCHAR(3), 
	remarks TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(cost_center_id) REFERENCES cost_centers (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_budgets_id ON payroll_budgets (id);

CREATE INDEX ix_payroll_budgets_month ON payroll_budgets (month);

CREATE INDEX ix_payroll_budgets_cost_center_id ON payroll_budgets (cost_center_id);

CREATE INDEX ix_payroll_budgets_year ON payroll_budgets (year);

CREATE INDEX ix_payroll_budgets_department_id ON payroll_budgets (department_id);

CREATE TABLE pay_bands (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	grade_band_id INTEGER, 
	location_id INTEGER, 
	currency VARCHAR(10), 
	min_ctc NUMERIC(14, 2), 
	midpoint_ctc NUMERIC(14, 2), 
	max_ctc NUMERIC(14, 2), 
	effective_from DATE, 
	is_active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(location_id) REFERENCES work_locations (id) ON DELETE SET NULL, 
	FOREIGN KEY(grade_band_id) REFERENCES grade_bands (id) ON DELETE SET NULL
);

CREATE INDEX ix_pay_bands_grade_band_id ON pay_bands (grade_band_id);

CREATE INDEX ix_pay_bands_id ON pay_bands (id);

CREATE INDEX ix_pay_bands_is_active ON pay_bands (is_active);

CREATE INDEX ix_pay_bands_location_id ON pay_bands (location_id);

CREATE TABLE announcements (
	id SERIAL NOT NULL, 
	title VARCHAR(220) NOT NULL, 
	body TEXT NOT NULL, 
	audience VARCHAR(80), 
	target_department_id INTEGER, 
	target_location_id INTEGER, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	requires_acknowledgement BOOLEAN, 
	is_published BOOLEAN, 
	published_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(target_department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(target_location_id) REFERENCES work_locations (id) ON DELETE SET NULL
);

CREATE INDEX ix_announcements_id ON announcements (id);

CREATE INDEX ix_announcements_is_published ON announcements (is_published);

CREATE INDEX ix_announcements_target_location_id ON announcements (target_location_id);

CREATE INDEX ix_announcements_target_department_id ON announcements (target_department_id);

CREATE TABLE crm_contacts (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	assigned_team_id INTEGER, 
	company_id INTEGER, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100), 
	full_name VARCHAR(220) NOT NULL, 
	email VARCHAR(150), 
	phone VARCHAR(40), 
	alternate_phone VARCHAR(40), 
	job_title VARCHAR(120), 
	department VARCHAR(120), 
	lifecycle_stage VARCHAR(60), 
	source VARCHAR(80), 
	date_of_birth DATE, 
	company_name VARCHAR(180), 
	company_website VARCHAR(200), 
	industry VARCHAR(120), 
	employee_count INTEGER, 
	website VARCHAR(200), 
	linkedin_url VARCHAR(300), 
	twitter_url VARCHAR(300), 
	email_verification_status VARCHAR(40), 
	social_profiles_json JSON, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	address TEXT, 
	status VARCHAR(40), 
	customer_since DATE, 
	last_contacted_at TIMESTAMP WITH TIME ZONE, 
	next_follow_up_at TIMESTAMP WITH TIME ZONE, 
	tags_text VARCHAR(500), 
	notes TEXT, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_contacts_email_verification_status ON crm_contacts (email_verification_status);

CREATE INDEX ix_crm_contacts_next_follow_up_at ON crm_contacts (next_follow_up_at);

CREATE INDEX ix_crm_contacts_branch_id ON crm_contacts (branch_id);

CREATE INDEX ix_crm_contacts_department_id ON crm_contacts (department_id);

CREATE INDEX ix_crm_contacts_email ON crm_contacts (email);

CREATE INDEX ix_crm_contacts_company_name ON crm_contacts (company_name);

CREATE INDEX ix_crm_contacts_city ON crm_contacts (city);

CREATE INDEX ix_crm_contacts_organization_id ON crm_contacts (organization_id);

CREATE INDEX ix_crm_contacts_owner_user_id ON crm_contacts (owner_user_id);

CREATE INDEX ix_crm_contacts_company_id ON crm_contacts (company_id);

CREATE INDEX ix_crm_contacts_lifecycle_stage ON crm_contacts (lifecycle_stage);

CREATE INDEX ix_crm_contacts_industry ON crm_contacts (industry);

CREATE INDEX ix_crm_contacts_status ON crm_contacts (status);

CREATE INDEX ix_crm_contacts_id ON crm_contacts (id);

CREATE INDEX ix_crm_contacts_assigned_team_id ON crm_contacts (assigned_team_id);

CREATE INDEX ix_crm_contacts_full_name ON crm_contacts (full_name);

CREATE INDEX ix_crm_contacts_source ON crm_contacts (source);

CREATE TABLE crm_approval_request_steps (
	id SERIAL NOT NULL, 
	request_id INTEGER NOT NULL, 
	step_id INTEGER, 
	approver_id INTEGER, 
	status VARCHAR(30) NOT NULL, 
	comments TEXT, 
	acted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(approver_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(step_id) REFERENCES crm_approval_steps (id) ON DELETE SET NULL, 
	FOREIGN KEY(request_id) REFERENCES crm_approval_requests (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_approval_request_steps_approver_id ON crm_approval_request_steps (approver_id);

CREATE INDEX ix_crm_approval_request_steps_status ON crm_approval_request_steps (status);

CREATE INDEX ix_crm_approval_request_steps_id ON crm_approval_request_steps (id);

CREATE INDEX ix_crm_approval_request_steps_step_id ON crm_approval_request_steps (step_id);

CREATE INDEX ix_crm_approval_request_steps_request_id ON crm_approval_request_steps (request_id);

CREATE TABLE pms_projects (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	workspace_id INTEGER, 
	client_id INTEGER, 
	manager_user_id INTEGER, 
	owner_user_id INTEGER, 
	department_id INTEGER, 
	branch_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	project_key VARCHAR(20) NOT NULL, 
	category VARCHAR(80), 
	description TEXT, 
	status VARCHAR(40), 
	priority VARCHAR(30), 
	health VARCHAR(30), 
	start_date DATE, 
	due_date DATE, 
	planned_start_date DATE, 
	planned_end_date DATE, 
	actual_start_date DATE, 
	actual_end_date DATE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	budget_amount NUMERIC(12, 2), 
	estimated_hours NUMERIC(10, 2), 
	estimated_cost NUMERIC(12, 2), 
	actual_cost NUMERIC(12, 2), 
	billing_status VARCHAR(40), 
	progress_percent INTEGER, 
	is_client_visible BOOLEAN, 
	is_template BOOLEAN, 
	is_archived BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(manager_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(workspace_id) REFERENCES pms_workspaces (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_pms_project_org_key UNIQUE (organization_id, project_key), 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(client_id) REFERENCES pms_clients (id) ON DELETE SET NULL
);

CREATE INDEX ix_pms_projects_organization_id ON pms_projects (organization_id);

CREATE INDEX ix_pms_projects_client_id ON pms_projects (client_id);

CREATE INDEX ix_pms_projects_department_id ON pms_projects (department_id);

CREATE INDEX ix_pms_projects_project_key ON pms_projects (project_key);

CREATE INDEX ix_pms_projects_priority ON pms_projects (priority);

CREATE INDEX ix_pms_projects_billing_status ON pms_projects (billing_status);

CREATE INDEX ix_pms_projects_id ON pms_projects (id);

CREATE INDEX ix_pms_projects_owner_user_id ON pms_projects (owner_user_id);

CREATE INDEX ix_pms_projects_branch_id ON pms_projects (branch_id);

CREATE INDEX ix_pms_projects_category ON pms_projects (category);

CREATE INDEX ix_pms_projects_health ON pms_projects (health);

CREATE INDEX ix_pms_projects_is_template ON pms_projects (is_template);

CREATE INDEX ix_pms_projects_workspace_id ON pms_projects (workspace_id);

CREATE INDEX ix_pms_projects_manager_user_id ON pms_projects (manager_user_id);

CREATE INDEX ix_pms_projects_name ON pms_projects (name);

CREATE INDEX ix_pms_projects_status ON pms_projects (status);

CREATE INDEX ix_pms_projects_due_date ON pms_projects (due_date);

CREATE INDEX ix_pms_projects_is_archived ON pms_projects (is_archived);

CREATE TABLE srm_pos_return_lines (
	id SERIAL NOT NULL, 
	return_id INTEGER NOT NULL, 
	sales_order_line_id INTEGER, 
	product_id INTEGER, 
	warehouse_id INTEGER, 
	item_code VARCHAR(80), 
	description TEXT, 
	quantity NUMERIC(12, 2), 
	unit_price NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	line_total NUMERIC(14, 2), 
	condition VARCHAR(60), 
	restock BOOLEAN, 
	metadata_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(return_id) REFERENCES srm_pos_returns (id) ON DELETE CASCADE, 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE SET NULL, 
	FOREIGN KEY(sales_order_line_id) REFERENCES srm_sales_order_lines (id) ON DELETE SET NULL, 
	FOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_pos_return_lines_id ON srm_pos_return_lines (id);

CREATE INDEX ix_srm_pos_return_lines_warehouse_id ON srm_pos_return_lines (warehouse_id);

CREATE INDEX ix_srm_pos_return_lines_condition ON srm_pos_return_lines (condition);

CREATE INDEX ix_srm_pos_return_lines_product_id ON srm_pos_return_lines (product_id);

CREATE INDEX ix_srm_pos_return_lines_sales_order_line_id ON srm_pos_return_lines (sales_order_line_id);

CREATE INDEX ix_srm_pos_return_lines_restock ON srm_pos_return_lines (restock);

CREATE INDEX ix_srm_pos_return_lines_return_id ON srm_pos_return_lines (return_id);

CREATE INDEX ix_srm_pos_return_lines_item_code ON srm_pos_return_lines (item_code);

CREATE TABLE srm_inventory_balances (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	quantity NUMERIC(14, 3), 
	average_cost NUMERIC(14, 4), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_inventory_balance_org_product_warehouse UNIQUE (organization_id, product_id, warehouse_id), 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_inventory_balances_organization_id ON srm_inventory_balances (organization_id);

CREATE INDEX ix_srm_inventory_balances_product_id ON srm_inventory_balances (product_id);

CREATE INDEX ix_srm_inventory_balances_id ON srm_inventory_balances (id);

CREATE INDEX ix_srm_inventory_balances_warehouse_id ON srm_inventory_balances (warehouse_id);

CREATE TABLE srm_inventory_movements (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	movement_number VARCHAR(80) NOT NULL, 
	movement_type VARCHAR(40), 
	movement_date DATE NOT NULL, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	quantity_in NUMERIC(14, 3), 
	quantity_out NUMERIC(14, 3), 
	rate NUMERIC(14, 4), 
	value NUMERIC(14, 2), 
	reference_number VARCHAR(120), 
	notes TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_srm_inventory_movement_org_number UNIQUE (organization_id, movement_number)
);

CREATE INDEX ix_srm_inventory_movements_organization_id ON srm_inventory_movements (organization_id);

CREATE INDEX ix_srm_inventory_movements_movement_date ON srm_inventory_movements (movement_date);

CREATE INDEX ix_srm_inventory_movements_reference_number ON srm_inventory_movements (reference_number);

CREATE INDEX ix_srm_inventory_movements_movement_number ON srm_inventory_movements (movement_number);

CREATE INDEX ix_srm_inventory_movements_product_id ON srm_inventory_movements (product_id);

CREATE INDEX ix_srm_inventory_movements_created_by ON srm_inventory_movements (created_by);

CREATE INDEX ix_srm_inventory_movements_id ON srm_inventory_movements (id);

CREATE INDEX ix_srm_inventory_movements_movement_type ON srm_inventory_movements (movement_type);

CREATE INDEX ix_srm_inventory_movements_warehouse_id ON srm_inventory_movements (warehouse_id);

CREATE INDEX ix_srm_inventory_movements_created_at ON srm_inventory_movements (created_at);

CREATE TABLE srm_purchase_order_lines (
	id SERIAL NOT NULL, 
	purchase_order_id INTEGER NOT NULL, 
	product_id INTEGER, 
	warehouse_id INTEGER, 
	item_code VARCHAR(80), 
	description TEXT, 
	quantity NUMERIC(14, 3), 
	received_quantity NUMERIC(14, 3), 
	unit_price NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	line_total NUMERIC(14, 2), 
	metadata_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(purchase_order_id) REFERENCES srm_purchase_orders (id) ON DELETE CASCADE, 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE SET NULL, 
	FOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_purchase_order_lines_purchase_order_id ON srm_purchase_order_lines (purchase_order_id);

CREATE INDEX ix_srm_purchase_order_lines_id ON srm_purchase_order_lines (id);

CREATE INDEX ix_srm_purchase_order_lines_item_code ON srm_purchase_order_lines (item_code);

CREATE INDEX ix_srm_purchase_order_lines_product_id ON srm_purchase_order_lines (product_id);

CREATE INDEX ix_srm_purchase_order_lines_warehouse_id ON srm_purchase_order_lines (warehouse_id);

CREATE TABLE srm_price_list_lines (
	id SERIAL NOT NULL, 
	price_list_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	sku VARCHAR(80), 
	item_name VARCHAR(220), 
	min_quantity NUMERIC(14, 3), 
	price NUMERIC(14, 2) NOT NULL, 
	discount_percent NUMERIC(6, 2), 
	discount_amount NUMERIC(14, 2), 
	tax_inclusive BOOLEAN, 
	active BOOLEAN, 
	metadata_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE CASCADE, 
	FOREIGN KEY(price_list_id) REFERENCES srm_price_lists (id) ON DELETE CASCADE, 
	CONSTRAINT uq_srm_price_list_line_product_break UNIQUE (price_list_id, product_id, min_quantity)
);

CREATE INDEX ix_srm_price_list_lines_price_list_id ON srm_price_list_lines (price_list_id);

CREATE INDEX ix_srm_price_list_lines_sku ON srm_price_list_lines (sku);

CREATE INDEX ix_srm_price_list_lines_active ON srm_price_list_lines (active);

CREATE INDEX ix_srm_price_list_lines_id ON srm_price_list_lines (id);

CREATE INDEX ix_srm_price_list_lines_product_id ON srm_price_list_lines (product_id);

CREATE TABLE srm_inventory_batches (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	batch_number VARCHAR(120) NOT NULL, 
	manufacture_date DATE, 
	expiry_date DATE, 
	received_date DATE, 
	quantity NUMERIC(14, 3), 
	available_quantity NUMERIC(14, 3), 
	unit_cost NUMERIC(14, 4), 
	status VARCHAR(40), 
	notes TEXT, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_inventory_batch_org_product_number UNIQUE (organization_id, product_id, batch_number), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_inventory_batches_product_id ON srm_inventory_batches (product_id);

CREATE INDEX ix_srm_inventory_batches_manufacture_date ON srm_inventory_batches (manufacture_date);

CREATE INDEX ix_srm_inventory_batches_status ON srm_inventory_batches (status);

CREATE INDEX ix_srm_inventory_batches_id ON srm_inventory_batches (id);

CREATE INDEX ix_srm_inventory_batches_warehouse_id ON srm_inventory_batches (warehouse_id);

CREATE INDEX ix_srm_inventory_batches_expiry_date ON srm_inventory_batches (expiry_date);

CREATE INDEX ix_srm_inventory_batches_created_by ON srm_inventory_batches (created_by);

CREATE INDEX ix_srm_inventory_batches_organization_id ON srm_inventory_batches (organization_id);

CREATE INDEX ix_srm_inventory_batches_batch_number ON srm_inventory_batches (batch_number);

CREATE INDEX ix_srm_inventory_batches_received_date ON srm_inventory_batches (received_date);

CREATE INDEX ix_srm_inventory_batches_created_at ON srm_inventory_batches (created_at);

CREATE TABLE srm_bills_of_material (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	bom_number VARCHAR(80) NOT NULL, 
	bom_name VARCHAR(180) NOT NULL, 
	finished_product_id INTEGER NOT NULL, 
	output_quantity NUMERIC(14, 3), 
	status VARCHAR(40), 
	notes TEXT, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_bom_org_number UNIQUE (organization_id, bom_number), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(finished_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT
);

CREATE INDEX ix_srm_bills_of_material_created_at ON srm_bills_of_material (created_at);

CREATE INDEX ix_srm_bills_of_material_organization_id ON srm_bills_of_material (organization_id);

CREATE INDEX ix_srm_bills_of_material_status ON srm_bills_of_material (status);

CREATE INDEX ix_srm_bills_of_material_id ON srm_bills_of_material (id);

CREATE INDEX ix_srm_bills_of_material_finished_product_id ON srm_bills_of_material (finished_product_id);

CREATE INDEX ix_srm_bills_of_material_created_by ON srm_bills_of_material (created_by);

CREATE INDEX ix_srm_bills_of_material_bom_number ON srm_bills_of_material (bom_number);

CREATE INDEX ix_srm_bills_of_material_bom_name ON srm_bills_of_material (bom_name);

CREATE TABLE srm_engagements (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	engagement_number VARCHAR(80) NOT NULL, 
	sales_order_id INTEGER, 
	contract_id INTEGER, 
	customer_id INTEGER, 
	crm_deal_id INTEGER, 
	crm_quote_id INTEGER, 
	pms_project_id INTEGER, 
	assigned_user_id INTEGER, 
	project_manager_user_id INTEGER, 
	name VARCHAR(220) NOT NULL, 
	status VARCHAR(40), 
	billing_type VARCHAR(40), 
	budget_amount NUMERIC(14, 2), 
	currency VARCHAR(10), 
	planned_start_date DATE, 
	planned_end_date DATE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_manager_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(contract_id) REFERENCES srm_contracts (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_engagements_crm_deal_id ON srm_engagements (crm_deal_id);

CREATE INDEX ix_srm_engagements_assigned_user_id ON srm_engagements (assigned_user_id);

CREATE INDEX ix_srm_engagements_billing_type ON srm_engagements (billing_type);

CREATE INDEX ix_srm_engagements_id ON srm_engagements (id);

CREATE INDEX ix_srm_engagements_customer_id ON srm_engagements (customer_id);

CREATE INDEX ix_srm_engagements_crm_quote_id ON srm_engagements (crm_quote_id);

CREATE INDEX ix_srm_engagements_project_manager_user_id ON srm_engagements (project_manager_user_id);

CREATE INDEX ix_srm_engagements_created_at ON srm_engagements (created_at);

CREATE INDEX ix_srm_engagements_sales_order_id ON srm_engagements (sales_order_id);

CREATE INDEX ix_srm_engagements_contract_id ON srm_engagements (contract_id);

CREATE INDEX ix_srm_engagements_pms_project_id ON srm_engagements (pms_project_id);

CREATE INDEX ix_srm_engagements_status ON srm_engagements (status);

CREATE INDEX ix_srm_engagements_organization_id ON srm_engagements (organization_id);

CREATE INDEX ix_srm_engagements_engagement_number ON srm_engagements (engagement_number);

CREATE TABLE fam_ledger_entries (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	financial_year_id INTEGER NOT NULL, 
	accounting_period_id INTEGER, 
	voucher_id INTEGER NOT NULL, 
	voucher_line_id INTEGER NOT NULL, 
	voucher_number VARCHAR(80) NOT NULL, 
	voucher_date DATE NOT NULL, 
	ledger_id INTEGER NOT NULL, 
	debit_amount NUMERIC(14, 2), 
	credit_amount NUMERIC(14, 2), 
	running_balance NUMERIC(14, 2), 
	narration TEXT, 
	source_module VARCHAR(40), 
	source_record_type VARCHAR(80), 
	source_record_id VARCHAR(120), 
	posted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(voucher_line_id) REFERENCES fam_voucher_lines (id) ON DELETE RESTRICT, 
	FOREIGN KEY(accounting_period_id) REFERENCES fam_accounting_periods (id) ON DELETE RESTRICT, 
	FOREIGN KEY(ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE RESTRICT, 
	FOREIGN KEY(financial_year_id) REFERENCES fam_financial_years (id) ON DELETE RESTRICT
);

CREATE INDEX ix_fam_ledger_entries_id ON fam_ledger_entries (id);

CREATE INDEX ix_fam_ledger_entries_voucher_id ON fam_ledger_entries (voucher_id);

CREATE INDEX ix_fam_ledger_entries_voucher_date ON fam_ledger_entries (voucher_date);

CREATE INDEX ix_fam_ledger_entries_source_record_type ON fam_ledger_entries (source_record_type);

CREATE INDEX ix_fam_ledger_entries_accounting_period_id ON fam_ledger_entries (accounting_period_id);

CREATE INDEX ix_fam_ledger_entries_voucher_line_id ON fam_ledger_entries (voucher_line_id);

CREATE INDEX ix_fam_ledger_entries_ledger_id ON fam_ledger_entries (ledger_id);

CREATE INDEX ix_fam_ledger_entries_source_record_id ON fam_ledger_entries (source_record_id);

CREATE INDEX ix_fam_ledger_entries_company_id ON fam_ledger_entries (company_id);

CREATE INDEX ix_fam_ledger_entries_financial_year_id ON fam_ledger_entries (financial_year_id);

CREATE INDEX ix_fam_ledger_entries_voucher_number ON fam_ledger_entries (voucher_number);

CREATE INDEX ix_fam_ledger_entries_source_module ON fam_ledger_entries (source_module);

CREATE INDEX ix_fam_ledger_entries_posted_at ON fam_ledger_entries (posted_at);

CREATE TABLE fam_bill_references (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	party_id INTEGER NOT NULL, 
	ledger_id INTEGER NOT NULL, 
	voucher_id INTEGER, 
	voucher_line_id INTEGER, 
	bill_number VARCHAR(120) NOT NULL, 
	bill_date DATE NOT NULL, 
	due_date DATE NOT NULL, 
	bill_type VARCHAR(30) NOT NULL, 
	original_amount NUMERIC(14, 2), 
	outstanding_amount NUMERIC(14, 2), 
	status VARCHAR(30), 
	source_module VARCHAR(40), 
	source_record_type VARCHAR(80), 
	source_record_id VARCHAR(120), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(party_id) REFERENCES fam_parties (id) ON DELETE CASCADE, 
	CONSTRAINT uq_fam_bill_company_party_number UNIQUE (company_id, party_id, bill_number), 
	FOREIGN KEY(voucher_line_id) REFERENCES fam_voucher_lines (id) ON DELETE SET NULL, 
	FOREIGN KEY(ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_bill_references_source_record_type ON fam_bill_references (source_record_type);

CREATE INDEX ix_fam_bill_references_id ON fam_bill_references (id);

CREATE INDEX ix_fam_bill_references_voucher_id ON fam_bill_references (voucher_id);

CREATE INDEX ix_fam_bill_references_bill_date ON fam_bill_references (bill_date);

CREATE INDEX ix_fam_bill_references_status ON fam_bill_references (status);

CREATE INDEX ix_fam_bill_references_source_record_id ON fam_bill_references (source_record_id);

CREATE INDEX ix_fam_bill_references_ledger_id ON fam_bill_references (ledger_id);

CREATE INDEX ix_fam_bill_references_voucher_line_id ON fam_bill_references (voucher_line_id);

CREATE INDEX ix_fam_bill_references_due_date ON fam_bill_references (due_date);

CREATE INDEX ix_fam_bill_references_source_module ON fam_bill_references (source_module);

CREATE INDEX ix_fam_bill_references_company_id ON fam_bill_references (company_id);

CREATE INDEX ix_fam_bill_references_party_id ON fam_bill_references (party_id);

CREATE INDEX ix_fam_bill_references_bill_number ON fam_bill_references (bill_number);

CREATE INDEX ix_fam_bill_references_bill_type ON fam_bill_references (bill_type);

CREATE TABLE fam_payment_references (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	voucher_id INTEGER NOT NULL, 
	voucher_line_id INTEGER, 
	payment_mode_id INTEGER, 
	reference_number VARCHAR(160) NOT NULL, 
	reference_date DATE, 
	bank_account_id INTEGER, 
	amount NUMERIC(14, 2), 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(bank_account_id) REFERENCES fam_bank_accounts (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_line_id) REFERENCES fam_voucher_lines (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_payment_reference UNIQUE (company_id, reference_number, payment_mode_id), 
	FOREIGN KEY(payment_mode_id) REFERENCES fam_payment_modes (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_payment_references_id ON fam_payment_references (id);

CREATE INDEX ix_fam_payment_references_voucher_line_id ON fam_payment_references (voucher_line_id);

CREATE INDEX ix_fam_payment_references_payment_mode_id ON fam_payment_references (payment_mode_id);

CREATE INDEX ix_fam_payment_references_status ON fam_payment_references (status);

CREATE INDEX ix_fam_payment_references_voucher_id ON fam_payment_references (voucher_id);

CREATE INDEX ix_fam_payment_references_reference_date ON fam_payment_references (reference_date);

CREATE INDEX ix_fam_payment_references_created_at ON fam_payment_references (created_at);

CREATE INDEX ix_fam_payment_references_company_id ON fam_payment_references (company_id);

CREATE INDEX ix_fam_payment_references_reference_number ON fam_payment_references (reference_number);

CREATE INDEX ix_fam_payment_references_bank_account_id ON fam_payment_references (bank_account_id);

CREATE TABLE fam_gst_transaction_lines (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	voucher_id INTEGER, 
	voucher_line_id INTEGER, 
	transaction_type VARCHAR(30) NOT NULL, 
	party_id INTEGER, 
	gstin VARCHAR(20), 
	place_of_supply_state VARCHAR(4), 
	supply_type VARCHAR(30) NOT NULL, 
	hsn_sac_code VARCHAR(30), 
	taxable_value NUMERIC(14, 2), 
	cgst_amount NUMERIC(14, 2), 
	sgst_amount NUMERIC(14, 2), 
	igst_amount NUMERIC(14, 2), 
	cess_amount NUMERIC(14, 2), 
	itc_eligible BOOLEAN, 
	reverse_charge BOOLEAN, 
	exempt_type VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(party_id) REFERENCES fam_parties (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_line_id) REFERENCES fam_voucher_lines (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_gst_transaction_lines_voucher_id ON fam_gst_transaction_lines (voucher_id);

CREATE INDEX ix_fam_gst_transaction_lines_transaction_type ON fam_gst_transaction_lines (transaction_type);

CREATE INDEX ix_fam_gst_transaction_lines_place_of_supply_state ON fam_gst_transaction_lines (place_of_supply_state);

CREATE INDEX ix_fam_gst_transaction_lines_itc_eligible ON fam_gst_transaction_lines (itc_eligible);

CREATE INDEX ix_fam_gst_transaction_lines_created_at ON fam_gst_transaction_lines (created_at);

CREATE INDEX ix_fam_gst_transaction_lines_id ON fam_gst_transaction_lines (id);

CREATE INDEX ix_fam_gst_transaction_lines_company_id ON fam_gst_transaction_lines (company_id);

CREATE INDEX ix_fam_gst_transaction_lines_party_id ON fam_gst_transaction_lines (party_id);

CREATE INDEX ix_fam_gst_transaction_lines_supply_type ON fam_gst_transaction_lines (supply_type);

CREATE INDEX ix_fam_gst_transaction_lines_reverse_charge ON fam_gst_transaction_lines (reverse_charge);

CREATE INDEX ix_fam_gst_transaction_lines_voucher_line_id ON fam_gst_transaction_lines (voucher_line_id);

CREATE INDEX ix_fam_gst_transaction_lines_gstin ON fam_gst_transaction_lines (gstin);

CREATE INDEX ix_fam_gst_transaction_lines_hsn_sac_code ON fam_gst_transaction_lines (hsn_sac_code);

CREATE INDEX ix_fam_gst_transaction_lines_exempt_type ON fam_gst_transaction_lines (exempt_type);

CREATE TABLE fam_purchase_bill_lines (
	id SERIAL NOT NULL, 
	purchase_bill_id INTEGER NOT NULL, 
	expense_ledger_id INTEGER NOT NULL, 
	item_id INTEGER, 
	description TEXT NOT NULL, 
	hsn_sac VARCHAR(30), 
	quantity NUMERIC(14, 3), 
	rate NUMERIC(14, 2), 
	taxable_value NUMERIC(14, 2), 
	gst_rate_id INTEGER, 
	gst_amount NUMERIC(14, 2), 
	tds_section_id INTEGER, 
	tds_amount NUMERIC(14, 2), 
	line_total NUMERIC(14, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tds_section_id) REFERENCES fam_tds_sections (id) ON DELETE SET NULL, 
	FOREIGN KEY(expense_ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT, 
	FOREIGN KEY(gst_rate_id) REFERENCES fam_gst_rates (id) ON DELETE SET NULL, 
	FOREIGN KEY(purchase_bill_id) REFERENCES fam_purchase_bills (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_purchase_bill_lines_expense_ledger_id ON fam_purchase_bill_lines (expense_ledger_id);

CREATE INDEX ix_fam_purchase_bill_lines_gst_rate_id ON fam_purchase_bill_lines (gst_rate_id);

CREATE INDEX ix_fam_purchase_bill_lines_item_id ON fam_purchase_bill_lines (item_id);

CREATE INDEX ix_fam_purchase_bill_lines_tds_section_id ON fam_purchase_bill_lines (tds_section_id);

CREATE INDEX ix_fam_purchase_bill_lines_purchase_bill_id ON fam_purchase_bill_lines (purchase_bill_id);

CREATE INDEX ix_fam_purchase_bill_lines_id ON fam_purchase_bill_lines (id);

CREATE INDEX ix_fam_purchase_bill_lines_hsn_sac ON fam_purchase_bill_lines (hsn_sac);

CREATE TABLE fam_expense_lines (
	id SERIAL NOT NULL, 
	expense_claim_id INTEGER NOT NULL, 
	expense_ledger_id INTEGER NOT NULL, 
	description TEXT NOT NULL, 
	hsn_sac VARCHAR(30), 
	taxable_value NUMERIC(14, 2), 
	gst_rate_id INTEGER, 
	gst_amount NUMERIC(14, 2), 
	line_total NUMERIC(14, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(expense_claim_id) REFERENCES fam_expense_claims (id) ON DELETE CASCADE, 
	FOREIGN KEY(gst_rate_id) REFERENCES fam_gst_rates (id) ON DELETE SET NULL, 
	FOREIGN KEY(expense_ledger_id) REFERENCES fam_ledgers (id) ON DELETE RESTRICT
);

CREATE INDEX ix_fam_expense_lines_expense_claim_id ON fam_expense_lines (expense_claim_id);

CREATE INDEX ix_fam_expense_lines_hsn_sac ON fam_expense_lines (hsn_sac);

CREATE INDEX ix_fam_expense_lines_gst_rate_id ON fam_expense_lines (gst_rate_id);

CREATE INDEX ix_fam_expense_lines_id ON fam_expense_lines (id);

CREATE INDEX ix_fam_expense_lines_expense_ledger_id ON fam_expense_lines (expense_ledger_id);

CREATE TABLE fam_stock_movement_lines (
	id SERIAL NOT NULL, 
	movement_id INTEGER NOT NULL, 
	company_id INTEGER NOT NULL, 
	stock_item_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	quantity_in NUMERIC(14, 3), 
	quantity_out NUMERIC(14, 3), 
	rate NUMERIC(14, 4), 
	value NUMERIC(14, 2), 
	balance_quantity NUMERIC(14, 3), 
	balance_value NUMERIC(14, 2), 
	line_number INTEGER, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(stock_item_id) REFERENCES fam_stock_items (id) ON DELETE RESTRICT, 
	FOREIGN KEY(warehouse_id) REFERENCES fam_warehouses (id) ON DELETE RESTRICT, 
	FOREIGN KEY(movement_id) REFERENCES fam_stock_movements (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_stock_movement_lines_created_at ON fam_stock_movement_lines (created_at);

CREATE INDEX ix_fam_stock_movement_lines_stock_item_id ON fam_stock_movement_lines (stock_item_id);

CREATE INDEX ix_fam_stock_movement_lines_warehouse_id ON fam_stock_movement_lines (warehouse_id);

CREATE INDEX ix_fam_stock_movement_lines_id ON fam_stock_movement_lines (id);

CREATE INDEX ix_fam_stock_movement_lines_company_id ON fam_stock_movement_lines (company_id);

CREATE INDEX ix_fam_stock_movement_lines_movement_id ON fam_stock_movement_lines (movement_id);

CREATE TABLE fam_stock_transfers (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	transfer_number VARCHAR(120) NOT NULL, 
	transfer_date DATE NOT NULL, 
	from_warehouse_id INTEGER NOT NULL, 
	to_warehouse_id INTEGER NOT NULL, 
	status VARCHAR(30), 
	notes TEXT, 
	movement_id INTEGER, 
	created_by INTEGER, 
	posted_by INTEGER, 
	posted_at TIMESTAMP WITH TIME ZONE, 
	lines_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(to_warehouse_id) REFERENCES fam_warehouses (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_fam_stock_transfer_company_number UNIQUE (company_id, transfer_number), 
	FOREIGN KEY(posted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(movement_id) REFERENCES fam_stock_movements (id) ON DELETE SET NULL, 
	FOREIGN KEY(from_warehouse_id) REFERENCES fam_warehouses (id) ON DELETE RESTRICT
);

CREATE INDEX ix_fam_stock_transfers_transfer_date ON fam_stock_transfers (transfer_date);

CREATE INDEX ix_fam_stock_transfers_from_warehouse_id ON fam_stock_transfers (from_warehouse_id);

CREATE INDEX ix_fam_stock_transfers_created_by ON fam_stock_transfers (created_by);

CREATE INDEX ix_fam_stock_transfers_created_at ON fam_stock_transfers (created_at);

CREATE INDEX ix_fam_stock_transfers_id ON fam_stock_transfers (id);

CREATE INDEX ix_fam_stock_transfers_transfer_number ON fam_stock_transfers (transfer_number);

CREATE INDEX ix_fam_stock_transfers_status ON fam_stock_transfers (status);

CREATE INDEX ix_fam_stock_transfers_posted_by ON fam_stock_transfers (posted_by);

CREATE INDEX ix_fam_stock_transfers_company_id ON fam_stock_transfers (company_id);

CREATE INDEX ix_fam_stock_transfers_to_warehouse_id ON fam_stock_transfers (to_warehouse_id);

CREATE INDEX ix_fam_stock_transfers_movement_id ON fam_stock_transfers (movement_id);

CREATE INDEX ix_fam_stock_transfers_posted_at ON fam_stock_transfers (posted_at);

CREATE TABLE fam_stock_adjustments (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	adjustment_number VARCHAR(120) NOT NULL, 
	adjustment_date DATE NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	adjustment_type VARCHAR(40), 
	reason VARCHAR(220), 
	status VARCHAR(30), 
	voucher_id INTEGER, 
	movement_id INTEGER, 
	notes TEXT, 
	created_by INTEGER, 
	posted_by INTEGER, 
	posted_at TIMESTAMP WITH TIME ZONE, 
	lines_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(movement_id) REFERENCES fam_stock_movements (id) ON DELETE SET NULL, 
	FOREIGN KEY(warehouse_id) REFERENCES fam_warehouses (id) ON DELETE RESTRICT, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_stock_adjustment_company_number UNIQUE (company_id, adjustment_number), 
	FOREIGN KEY(posted_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_stock_adjustments_status ON fam_stock_adjustments (status);

CREATE INDEX ix_fam_stock_adjustments_created_by ON fam_stock_adjustments (created_by);

CREATE INDEX ix_fam_stock_adjustments_created_at ON fam_stock_adjustments (created_at);

CREATE INDEX ix_fam_stock_adjustments_adjustment_number ON fam_stock_adjustments (adjustment_number);

CREATE INDEX ix_fam_stock_adjustments_warehouse_id ON fam_stock_adjustments (warehouse_id);

CREATE INDEX ix_fam_stock_adjustments_voucher_id ON fam_stock_adjustments (voucher_id);

CREATE INDEX ix_fam_stock_adjustments_posted_by ON fam_stock_adjustments (posted_by);

CREATE INDEX ix_fam_stock_adjustments_id ON fam_stock_adjustments (id);

CREATE INDEX ix_fam_stock_adjustments_company_id ON fam_stock_adjustments (company_id);

CREATE INDEX ix_fam_stock_adjustments_adjustment_type ON fam_stock_adjustments (adjustment_type);

CREATE INDEX ix_fam_stock_adjustments_movement_id ON fam_stock_adjustments (movement_id);

CREATE INDEX ix_fam_stock_adjustments_posted_at ON fam_stock_adjustments (posted_at);

CREATE INDEX ix_fam_stock_adjustments_adjustment_date ON fam_stock_adjustments (adjustment_date);

CREATE TABLE positions (
	id SERIAL NOT NULL, 
	position_code VARCHAR(50) NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	company_id INTEGER NOT NULL, 
	organization_id INTEGER, 
	description TEXT, 
	business_unit_id INTEGER, 
	cost_center_id INTEGER, 
	location_id INTEGER, 
	department_id INTEGER, 
	designation_id INTEGER, 
	job_profile_id INTEGER, 
	grade_band_id INTEGER, 
	manager_position_id INTEGER, 
	incumbent_employee_id INTEGER, 
	status VARCHAR(30), 
	budgeted_ctc NUMERIC(14, 2), 
	effective_from DATE, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(cost_center_id) REFERENCES cost_centers (id) ON DELETE SET NULL, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(grade_band_id) REFERENCES grade_bands (id) ON DELETE SET NULL, 
	FOREIGN KEY(designation_id) REFERENCES designations (id) ON DELETE SET NULL, 
	FOREIGN KEY(location_id) REFERENCES work_locations (id) ON DELETE SET NULL, 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(manager_position_id) REFERENCES positions (id) ON DELETE SET NULL, 
	FOREIGN KEY(job_profile_id) REFERENCES job_profiles (id) ON DELETE SET NULL
);

CREATE INDEX ix_positions_id ON positions (id);

CREATE INDEX ix_positions_organization_id ON positions (organization_id);

CREATE INDEX ix_positions_location_id ON positions (location_id);

CREATE INDEX ix_positions_job_profile_id ON positions (job_profile_id);

CREATE INDEX ix_positions_status ON positions (status);

CREATE INDEX ix_positions_company_id ON positions (company_id);

CREATE INDEX ix_positions_business_unit_id ON positions (business_unit_id);

CREATE INDEX ix_positions_department_id ON positions (department_id);

CREATE INDEX ix_positions_grade_band_id ON positions (grade_band_id);

CREATE INDEX ix_positions_is_active ON positions (is_active);

CREATE UNIQUE INDEX ix_positions_position_code ON positions (position_code);

CREATE INDEX ix_positions_cost_center_id ON positions (cost_center_id);

CREATE INDEX ix_positions_designation_id ON positions (designation_id);

CREATE INDEX ix_positions_incumbent_employee_id ON positions (incumbent_employee_id);

CREATE TABLE workflow_audit_events (
	id SERIAL NOT NULL, 
	instance_id INTEGER NOT NULL, 
	task_id INTEGER, 
	step_definition_id INTEGER, 
	event_type VARCHAR(60) NOT NULL, 
	actor_user_id INTEGER, 
	before_status VARCHAR(30), 
	after_status VARCHAR(30), 
	reason TEXT, 
	details_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(task_id) REFERENCES workflow_tasks (id) ON DELETE SET NULL, 
	FOREIGN KEY(instance_id) REFERENCES workflow_instances (id) ON DELETE CASCADE, 
	FOREIGN KEY(step_definition_id) REFERENCES workflow_step_definitions (id) ON DELETE SET NULL
);

CREATE INDEX ix_workflow_audit_events_event_type ON workflow_audit_events (event_type);

CREATE INDEX ix_workflow_audit_events_instance_id ON workflow_audit_events (instance_id);

CREATE INDEX ix_workflow_audit_events_task_id ON workflow_audit_events (task_id);

CREATE INDEX ix_workflow_audit_events_id ON workflow_audit_events (id);

CREATE TABLE communication_webform_fields (
	id SERIAL NOT NULL, 
	webform_id INTEGER NOT NULL, 
	field_key VARCHAR(120) NOT NULL, 
	label VARCHAR(160) NOT NULL, 
	field_type VARCHAR(40), 
	required BOOLEAN, 
	order_index INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(webform_id) REFERENCES communication_webforms (id) ON DELETE CASCADE
);

CREATE INDEX ix_communication_webform_fields_webform_id ON communication_webform_fields (webform_id);

CREATE INDEX ix_communication_webform_fields_id ON communication_webform_fields (id);

CREATE TABLE communication_webform_submissions (
	id SERIAL NOT NULL, 
	webform_id INTEGER NOT NULL, 
	payload_json JSON NOT NULL, 
	created_record_type VARCHAR(60), 
	created_record_id INTEGER, 
	duplicate_detected BOOLEAN, 
	ip_address VARCHAR(80), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(webform_id) REFERENCES communication_webforms (id) ON DELETE CASCADE
);

CREATE INDEX ix_communication_webform_submissions_id ON communication_webform_submissions (id);

CREATE INDEX ix_communication_webform_submissions_created_at ON communication_webform_submissions (created_at);

CREATE INDEX ix_communication_webform_submissions_created_record_type ON communication_webform_submissions (created_record_type);

CREATE INDEX ix_communication_webform_submissions_duplicate_detected ON communication_webform_submissions (duplicate_detected);

CREATE INDEX ix_communication_webform_submissions_webform_id ON communication_webform_submissions (webform_id);

CREATE INDEX ix_communication_webform_submissions_created_record_id ON communication_webform_submissions (created_record_id);

CREATE TABLE communication_campaign_sends (
	id SERIAL NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	member_id INTEGER, 
	email_message_id INTEGER, 
	status VARCHAR(40) NOT NULL, 
	error_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(email_message_id) REFERENCES communication_email_messages (id) ON DELETE SET NULL, 
	FOREIGN KEY(member_id) REFERENCES communication_campaign_members (id) ON DELETE SET NULL, 
	FOREIGN KEY(campaign_id) REFERENCES communication_campaigns (id) ON DELETE CASCADE
);

CREATE INDEX ix_communication_campaign_sends_created_at ON communication_campaign_sends (created_at);

CREATE INDEX ix_communication_campaign_sends_email_message_id ON communication_campaign_sends (email_message_id);

CREATE INDEX ix_communication_campaign_sends_member_id ON communication_campaign_sends (member_id);

CREATE INDEX ix_communication_campaign_sends_id ON communication_campaign_sends (id);

CREATE INDEX ix_communication_campaign_sends_campaign_id ON communication_campaign_sends (campaign_id);

CREATE INDEX ix_communication_campaign_sends_status ON communication_campaign_sends (status);

CREATE TABLE ai_action_logs (
	id SERIAL NOT NULL, 
	prompt_run_id INTEGER, 
	agent_action_id INTEGER, 
	event_type VARCHAR(80) NOT NULL, 
	module_name VARCHAR(80), 
	record_type VARCHAR(80), 
	record_id INTEGER, 
	status VARCHAR(40) NOT NULL, 
	detail_json JSON, 
	error_message TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(agent_action_id) REFERENCES ai_agent_actions (id) ON DELETE SET NULL, 
	FOREIGN KEY(prompt_run_id) REFERENCES ai_prompt_runs (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_action_logs_status ON ai_action_logs (status);

CREATE INDEX ix_ai_action_logs_event_type ON ai_action_logs (event_type);

CREATE INDEX ix_ai_action_logs_module_name ON ai_action_logs (module_name);

CREATE INDEX ix_ai_action_logs_created_by ON ai_action_logs (created_by);

CREATE INDEX ix_ai_action_logs_prompt_run_id ON ai_action_logs (prompt_run_id);

CREATE INDEX ix_ai_action_logs_agent_action_id ON ai_action_logs (agent_action_id);

CREATE INDEX ix_ai_action_logs_record_id ON ai_action_logs (record_id);

CREATE INDEX ix_ai_action_logs_created_at ON ai_action_logs (created_at);

CREATE INDEX ix_ai_action_logs_id ON ai_action_logs (id);

CREATE INDEX ix_ai_action_logs_record_type ON ai_action_logs (record_type);

CREATE TABLE ai_user_feedback (
	id SERIAL NOT NULL, 
	prompt_run_id INTEGER, 
	recommendation_id INTEGER, 
	rating VARCHAR(40) NOT NULL, 
	comments TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(prompt_run_id) REFERENCES ai_prompt_runs (id) ON DELETE SET NULL, 
	FOREIGN KEY(recommendation_id) REFERENCES ai_recommendations (id) ON DELETE SET NULL
);

CREATE INDEX ix_ai_user_feedback_prompt_run_id ON ai_user_feedback (prompt_run_id);

CREATE INDEX ix_ai_user_feedback_recommendation_id ON ai_user_feedback (recommendation_id);

CREATE INDEX ix_ai_user_feedback_id ON ai_user_feedback (id);

CREATE INDEX ix_ai_user_feedback_created_at ON ai_user_feedback (created_at);

CREATE INDEX ix_ai_user_feedback_rating ON ai_user_feedback (rating);

CREATE INDEX ix_ai_user_feedback_created_by ON ai_user_feedback (created_by);

CREATE TABLE ai_message_feedback (
	id SERIAL NOT NULL, 
	message_id INTEGER NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	agent_id INTEGER, 
	rating VARCHAR(20) NOT NULL, 
	feedback_text TEXT, 
	feedback_type VARCHAR(40) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(message_id) REFERENCES ai_messages (id) ON DELETE CASCADE, 
	FOREIGN KEY(agent_id) REFERENCES ai_agents (id) ON DELETE SET NULL, 
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_message_feedback_user_id ON ai_message_feedback (user_id);

CREATE INDEX ix_ai_message_feedback_agent_id ON ai_message_feedback (agent_id);

CREATE INDEX ix_ai_message_feedback_id ON ai_message_feedback (id);

CREATE INDEX ix_ai_message_feedback_conversation_id ON ai_message_feedback (conversation_id);

CREATE INDEX ix_ai_message_feedback_feedback_type ON ai_message_feedback (feedback_type);

CREATE INDEX ix_ai_message_feedback_message_id ON ai_message_feedback (message_id);

CREATE INDEX ix_ai_message_feedback_rating ON ai_message_feedback (rating);

CREATE INDEX ix_ai_message_feedback_created_at ON ai_message_feedback (created_at);

CREATE TABLE salary_template_components (
	id SERIAL NOT NULL, 
	template_id INTEGER NOT NULL, 
	component_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2), 
	percentage NUMERIC(8, 4), 
	formula_expression TEXT, 
	min_amount NUMERIC(12, 2), 
	max_amount NUMERIC(12, 2), 
	is_employee_editable BOOLEAN, 
	order_sequence INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES salary_components (id) ON DELETE CASCADE, 
	FOREIGN KEY(template_id) REFERENCES salary_templates (id) ON DELETE CASCADE
);

CREATE INDEX ix_salary_template_components_id ON salary_template_components (id);

CREATE INDEX ix_salary_template_components_template_id ON salary_template_components (template_id);

CREATE INDEX ix_salary_template_components_component_id ON salary_template_components (component_id);

CREATE TABLE statutory_challans (
	id SERIAL NOT NULL, 
	legal_entity_id INTEGER, 
	pay_group_id INTEGER, 
	period_id INTEGER, 
	challan_type VARCHAR(40) NOT NULL, 
	due_date DATE NOT NULL, 
	amount NUMERIC(14, 2), 
	status VARCHAR(30), 
	payment_reference VARCHAR(120), 
	paid_at TIMESTAMP WITH TIME ZONE, 
	file_url VARCHAR(500), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(pay_group_id) REFERENCES payroll_pay_groups (id) ON DELETE SET NULL, 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE SET NULL, 
	FOREIGN KEY(period_id) REFERENCES payroll_periods (id) ON DELETE SET NULL
);

CREATE INDEX ix_statutory_challans_legal_entity_id ON statutory_challans (legal_entity_id);

CREATE INDEX ix_statutory_challans_status ON statutory_challans (status);

CREATE INDEX ix_statutory_challans_period_id ON statutory_challans (period_id);

CREATE INDEX ix_statutory_challans_challan_type ON statutory_challans (challan_type);

CREATE INDEX ix_statutory_challans_id ON statutory_challans (id);

CREATE INDEX ix_statutory_challans_pay_group_id ON statutory_challans (pay_group_id);

CREATE TABLE statutory_filing_submissions (
	id SERIAL NOT NULL, 
	statutory_type VARCHAR(50), 
	payroll_run_id INTEGER, 
	file_type VARCHAR(20), 
	generated_file_path VARCHAR(500), 
	validation_status VARCHAR(30), 
	validation_errors_json JSON, 
	row_count INTEGER, 
	total_amount NUMERIC(18, 2), 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	submitted_by INTEGER, 
	portal_reference VARCHAR(200), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(submitted_by) REFERENCES users (id), 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id)
);

CREATE INDEX ix_statutory_filing_submissions_validation_status ON statutory_filing_submissions (validation_status);

CREATE INDEX ix_statutory_filing_submissions_statutory_type ON statutory_filing_submissions (statutory_type);

CREATE INDEX ix_statutory_filing_submissions_payroll_run_id ON statutory_filing_submissions (payroll_run_id);

CREATE TABLE statutory_exports (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	payroll_run_id INTEGER NOT NULL, 
	export_type VARCHAR(40) NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	total_employees INTEGER, 
	total_amount NUMERIC(14, 2), 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	downloaded_at TIMESTAMP WITH TIME ZONE, 
	download_count INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_statutory_exports_payroll_run_id ON statutory_exports (payroll_run_id);

CREATE INDEX ix_statutory_exports_organization_id ON statutory_exports (organization_id);

CREATE INDEX ix_statutory_exports_export_type ON statutory_exports (export_type);

CREATE INDEX ix_statutory_exports_id ON statutory_exports (id);

CREATE TABLE payroll_arrear_runs (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER, 
	period_id INTEGER, 
	name VARCHAR(150) NOT NULL, 
	reason TEXT, 
	status VARCHAR(30), 
	created_by INTEGER, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(period_id) REFERENCES payroll_periods (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_arrear_runs_period_id ON payroll_arrear_runs (period_id);

CREATE INDEX ix_payroll_arrear_runs_payroll_run_id ON payroll_arrear_runs (payroll_run_id);

CREATE INDEX ix_payroll_arrear_runs_id ON payroll_arrear_runs (id);

CREATE INDEX ix_payroll_arrear_runs_status ON payroll_arrear_runs (status);

CREATE TABLE off_cycle_payroll_runs (
	id SERIAL NOT NULL, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	run_type VARCHAR(50), 
	pay_group_id INTEGER, 
	period_id INTEGER, 
	reason TEXT, 
	status VARCHAR(30), 
	total_amount NUMERIC(14, 2), 
	scheduled_payment_date DATE, 
	created_by INTEGER, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(pay_group_id) REFERENCES payroll_pay_groups (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(period_id) REFERENCES payroll_periods (id) ON DELETE SET NULL
);

CREATE INDEX ix_off_cycle_payroll_runs_id ON off_cycle_payroll_runs (id);

CREATE INDEX ix_off_cycle_payroll_runs_run_type ON off_cycle_payroll_runs (run_type);

CREATE INDEX ix_off_cycle_payroll_runs_month ON off_cycle_payroll_runs (month);

CREATE INDEX ix_off_cycle_payroll_runs_pay_group_id ON off_cycle_payroll_runs (pay_group_id);

CREATE INDEX ix_off_cycle_payroll_runs_year ON off_cycle_payroll_runs (year);

CREATE INDEX ix_off_cycle_payroll_runs_status ON off_cycle_payroll_runs (status);

CREATE TABLE payroll_payment_batches (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	bank_format_id INTEGER, 
	debit_account VARCHAR(120), 
	total_amount NUMERIC(14, 2), 
	status VARCHAR(30), 
	generated_file_url VARCHAR(500), 
	approved_by INTEGER, 
	released_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(bank_format_id) REFERENCES bank_advice_formats (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_payment_batches_status ON payroll_payment_batches (status);

CREATE INDEX ix_payroll_payment_batches_payroll_run_id ON payroll_payment_batches (payroll_run_id);

CREATE INDEX ix_payroll_payment_batches_id ON payroll_payment_batches (id);

CREATE TABLE payroll_journal_entries (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	legal_entity_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	cost_center VARCHAR(100), 
	status VARCHAR(30), 
	total_debit NUMERIC(14, 2), 
	total_credit NUMERIC(14, 2), 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	posted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_journal_entries_legal_entity_id ON payroll_journal_entries (legal_entity_id);

CREATE INDEX ix_payroll_journal_entries_id ON payroll_journal_entries (id);

CREATE INDEX ix_payroll_journal_entries_status ON payroll_journal_entries (status);

CREATE INDEX ix_payroll_journal_entries_payroll_run_id ON payroll_journal_entries (payroll_run_id);

CREATE TABLE statutory_file_validations (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER, 
	period_id INTEGER, 
	file_type VARCHAR(50) NOT NULL, 
	status VARCHAR(30), 
	total_rows INTEGER, 
	error_count INTEGER, 
	warning_count INTEGER, 
	output_file_url VARCHAR(500), 
	validation_errors_json JSON, 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(period_id) REFERENCES payroll_periods (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_statutory_file_validations_payroll_run_id ON statutory_file_validations (payroll_run_id);

CREATE INDEX ix_statutory_file_validations_period_id ON statutory_file_validations (period_id);

CREATE INDEX ix_statutory_file_validations_status ON statutory_file_validations (status);

CREATE INDEX ix_statutory_file_validations_id ON statutory_file_validations (id);

CREATE INDEX ix_statutory_file_validations_file_type ON statutory_file_validations (file_type);

CREATE TABLE payroll_export_batches (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	export_type VARCHAR(50) NOT NULL, 
	status VARCHAR(30), 
	output_file_url VARCHAR(500), 
	total_records INTEGER, 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_export_batches_export_type ON payroll_export_batches (export_type);

CREATE INDEX ix_payroll_export_batches_status ON payroll_export_batches (status);

CREATE INDEX ix_payroll_export_batches_id ON payroll_export_batches (id);

CREATE INDEX ix_payroll_export_batches_payroll_run_id ON payroll_export_batches (payroll_run_id);

CREATE TABLE payroll_bank_exports (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	payroll_run_id INTEGER NOT NULL, 
	export_type VARCHAR(20) NOT NULL, 
	bank_name VARCHAR(120), 
	total_employees INTEGER, 
	total_amount NUMERIC(14, 2), 
	file_path VARCHAR(500) NOT NULL, 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	downloaded_at TIMESTAMP WITH TIME ZONE, 
	download_count INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_bank_exports_id ON payroll_bank_exports (id);

CREATE INDEX ix_payroll_bank_exports_export_type ON payroll_bank_exports (export_type);

CREATE INDEX ix_payroll_bank_exports_organization_id ON payroll_bank_exports (organization_id);

CREATE INDEX ix_payroll_bank_exports_payroll_run_id ON payroll_bank_exports (payroll_run_id);

CREATE TABLE payroll_run_audit_logs (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	actor_user_id INTEGER, 
	details TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_run_audit_logs_id ON payroll_run_audit_logs (id);

CREATE INDEX ix_payroll_run_audit_logs_action ON payroll_run_audit_logs (action);

CREATE INDEX ix_payroll_run_audit_logs_payroll_run_id ON payroll_run_audit_logs (payroll_run_id);

CREATE TABLE payroll_unlock_requests (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	reason TEXT NOT NULL, 
	status VARCHAR(30), 
	requested_by INTEGER, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_unlock_requests_payroll_run_id ON payroll_unlock_requests (payroll_run_id);

CREATE INDEX ix_payroll_unlock_requests_id ON payroll_unlock_requests (id);

CREATE INDEX ix_payroll_unlock_requests_status ON payroll_unlock_requests (status);

CREATE TABLE payslip_publish_batches (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	status VARCHAR(30), 
	total_payslips INTEGER, 
	published_count INTEGER, 
	email_dispatch_status VARCHAR(30), 
	output_file_url VARCHAR(500), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_payslip_publish_batches_status ON payslip_publish_batches (status);

CREATE INDEX ix_payslip_publish_batches_payroll_run_id ON payslip_publish_batches (payroll_run_id);

CREATE INDEX ix_payslip_publish_batches_id ON payslip_publish_batches (id);

CREATE TABLE payroll_bank_file_validations (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	bank_name VARCHAR(120) NOT NULL, 
	status VARCHAR(30), 
	error_count INTEGER, 
	warnings_json JSON, 
	errors_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_bank_file_validations_id ON payroll_bank_file_validations (id);

CREATE INDEX ix_payroll_bank_file_validations_status ON payroll_bank_file_validations (status);

CREATE INDEX ix_payroll_bank_file_validations_payroll_run_id ON payroll_bank_file_validations (payroll_run_id);

CREATE INDEX ix_payroll_bank_file_validations_bank_name ON payroll_bank_file_validations (bank_name);

CREATE TABLE role_skill_requirements (
	id SERIAL NOT NULL, 
	designation_id INTEGER, 
	job_profile_id INTEGER, 
	competency_id INTEGER NOT NULL, 
	required_level INTEGER, 
	importance VARCHAR(30), 
	is_active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(designation_id) REFERENCES designations (id) ON DELETE CASCADE, 
	FOREIGN KEY(competency_id) REFERENCES competencies (id) ON DELETE CASCADE, 
	FOREIGN KEY(job_profile_id) REFERENCES job_profiles (id) ON DELETE CASCADE
);

CREATE INDEX ix_role_skill_requirements_id ON role_skill_requirements (id);

CREATE INDEX ix_role_skill_requirements_competency_id ON role_skill_requirements (competency_id);

CREATE INDEX ix_role_skill_requirements_designation_id ON role_skill_requirements (designation_id);

CREATE INDEX ix_role_skill_requirements_job_profile_id ON role_skill_requirements (job_profile_id);

CREATE INDEX ix_role_skill_requirements_is_active ON role_skill_requirements (is_active);

CREATE TABLE crm_deals (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	assigned_team_id INTEGER, 
	territory_id INTEGER, 
	company_id INTEGER, 
	contact_id INTEGER, 
	pipeline_id INTEGER NOT NULL, 
	stage_id INTEGER NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	description TEXT, 
	amount NUMERIC(12, 2), 
	currency VARCHAR(10), 
	probability INTEGER, 
	expected_revenue NUMERIC(12, 2), 
	expected_close_date DATE, 
	actual_close_date DATE, 
	status VARCHAR(30), 
	loss_reason TEXT, 
	lost_reason TEXT, 
	win_reason TEXT, 
	lead_source VARCHAR(80), 
	source VARCHAR(80), 
	won_at TIMESTAMP WITH TIME ZONE, 
	lost_at TIMESTAMP WITH TIME ZONE, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	discount_amount NUMERIC(12, 2), 
	position INTEGER, 
	next_follow_up_at TIMESTAMP WITH TIME ZONE, 
	last_activity_at TIMESTAMP WITH TIME ZONE, 
	tags_text VARCHAR(500), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(pipeline_id) REFERENCES crm_pipelines (id) ON DELETE CASCADE, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(stage_id) REFERENCES crm_pipeline_stages (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE SET NULL, 
	FOREIGN KEY(territory_id) REFERENCES crm_territories (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_deals_stage_id ON crm_deals (stage_id);

CREATE INDEX ix_crm_deals_name ON crm_deals (name);

CREATE INDEX ix_crm_deals_id ON crm_deals (id);

CREATE INDEX ix_crm_deals_expected_close_date ON crm_deals (expected_close_date);

CREATE INDEX ix_crm_deals_branch_id ON crm_deals (branch_id);

CREATE INDEX ix_crm_deals_status ON crm_deals (status);

CREATE INDEX ix_crm_deals_organization_id ON crm_deals (organization_id);

CREATE INDEX ix_crm_deals_lead_source ON crm_deals (lead_source);

CREATE INDEX ix_crm_deals_department_id ON crm_deals (department_id);

CREATE INDEX ix_crm_deals_source ON crm_deals (source);

CREATE INDEX ix_crm_deals_owner_user_id ON crm_deals (owner_user_id);

CREATE INDEX ix_crm_deals_won_at ON crm_deals (won_at);

CREATE INDEX ix_crm_deals_assigned_team_id ON crm_deals (assigned_team_id);

CREATE INDEX ix_crm_deals_lost_at ON crm_deals (lost_at);

CREATE INDEX ix_crm_deals_territory_id ON crm_deals (territory_id);

CREATE INDEX ix_crm_deals_closed_at ON crm_deals (closed_at);

CREATE INDEX ix_crm_deals_company_id ON crm_deals (company_id);

CREATE INDEX ix_crm_deals_next_follow_up_at ON crm_deals (next_follow_up_at);

CREATE INDEX ix_crm_deals_contact_id ON crm_deals (contact_id);

CREATE INDEX ix_crm_deals_pipeline_id ON crm_deals (pipeline_id);

CREATE TABLE crm_tickets (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	contact_id INTEGER, 
	company_id INTEGER, 
	owner_user_id INTEGER, 
	ticket_number VARCHAR(60) NOT NULL, 
	subject VARCHAR(220) NOT NULL, 
	description TEXT, 
	priority VARCHAR(30), 
	status VARCHAR(50), 
	category VARCHAR(100), 
	source VARCHAR(40), 
	due_date TIMESTAMP WITH TIME ZONE, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	satisfaction_rating INTEGER, 
	satisfaction_comment TEXT, 
	csat_requested_at TIMESTAMP WITH TIME ZONE, 
	csat_submitted_at TIMESTAMP WITH TIME ZONE, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_ticket_org_number UNIQUE (organization_id, ticket_number), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_tickets_source ON crm_tickets (source);

CREATE INDEX ix_crm_tickets_id ON crm_tickets (id);

CREATE INDEX ix_crm_tickets_ticket_number ON crm_tickets (ticket_number);

CREATE INDEX ix_crm_tickets_status ON crm_tickets (status);

CREATE INDEX ix_crm_tickets_due_date ON crm_tickets (due_date);

CREATE INDEX ix_crm_tickets_contact_id ON crm_tickets (contact_id);

CREATE INDEX ix_crm_tickets_owner_user_id ON crm_tickets (owner_user_id);

CREATE INDEX ix_crm_tickets_category ON crm_tickets (category);

CREATE INDEX ix_crm_tickets_organization_id ON crm_tickets (organization_id);

CREATE INDEX ix_crm_tickets_company_id ON crm_tickets (company_id);

CREATE INDEX ix_crm_tickets_priority ON crm_tickets (priority);

CREATE TABLE pms_project_intakes (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	title VARCHAR(180) NOT NULL, 
	description TEXT, 
	requester_user_id INTEGER, 
	requester_name VARCHAR(180), 
	requester_email VARCHAR(150), 
	client_id INTEGER, 
	client_name VARCHAR(180), 
	priority VARCHAR(30), 
	desired_start_date DATE, 
	desired_due_date DATE, 
	budget_amount NUMERIC(12, 2), 
	status VARCHAR(30), 
	review_notes TEXT, 
	reviewed_by_user_id INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	created_project_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_project_id) REFERENCES pms_projects (id) ON DELETE SET NULL, 
	FOREIGN KEY(client_id) REFERENCES pms_clients (id) ON DELETE SET NULL, 
	FOREIGN KEY(reviewed_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(requester_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_pms_project_intakes_title ON pms_project_intakes (title);

CREATE INDEX ix_pms_project_intakes_requester_user_id ON pms_project_intakes (requester_user_id);

CREATE INDEX ix_pms_project_intakes_status ON pms_project_intakes (status);

CREATE INDEX ix_pms_project_intakes_organization_id ON pms_project_intakes (organization_id);

CREATE INDEX ix_pms_project_intakes_id ON pms_project_intakes (id);

CREATE INDEX ix_pms_project_intakes_client_id ON pms_project_intakes (client_id);

CREATE INDEX ix_pms_project_intakes_created_project_id ON pms_project_intakes (created_project_id);

CREATE INDEX ix_pms_project_intakes_requester_email ON pms_project_intakes (requester_email);

CREATE INDEX ix_pms_project_intakes_priority ON pms_project_intakes (priority);

CREATE TABLE pms_project_members (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role VARCHAR(40), 
	allocation_percent NUMERIC(5, 2), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE, 
	CONSTRAINT uq_pms_project_member UNIQUE (project_id, user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_project_members_id ON pms_project_members (id);

CREATE INDEX ix_pms_project_members_project_id ON pms_project_members (project_id);

CREATE INDEX ix_pms_project_members_role ON pms_project_members (role);

CREATE INDEX ix_pms_project_members_user_id ON pms_project_members (user_id);

CREATE TABLE pms_epics (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	project_id INTEGER NOT NULL, 
	epic_key VARCHAR(60) NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	description TEXT, 
	status VARCHAR(40), 
	owner_user_id INTEGER, 
	color VARCHAR(30), 
	start_date DATE, 
	end_date DATE, 
	target_date DATE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_pms_epic_project_key UNIQUE (project_id, epic_key)
);

CREATE INDEX ix_pms_epics_epic_key ON pms_epics (epic_key);

CREATE INDEX ix_pms_epics_owner_user_id ON pms_epics (owner_user_id);

CREATE INDEX ix_pms_epics_organization_id ON pms_epics (organization_id);

CREATE INDEX ix_pms_epics_project_id ON pms_epics (project_id);

CREATE INDEX ix_pms_epics_end_date ON pms_epics (end_date);

CREATE INDEX ix_pms_epics_id ON pms_epics (id);

CREATE INDEX ix_pms_epics_status ON pms_epics (status);

CREATE INDEX ix_pms_epics_target_date ON pms_epics (target_date);

CREATE TABLE pms_components (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	lead_user_id INTEGER, 
	default_assignee_user_id INTEGER, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pms_component_project_name UNIQUE (project_id, name), 
	FOREIGN KEY(lead_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(default_assignee_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_components_lead_user_id ON pms_components (lead_user_id);

CREATE INDEX ix_pms_components_name ON pms_components (name);

CREATE INDEX ix_pms_components_project_id ON pms_components (project_id);

CREATE INDEX ix_pms_components_id ON pms_components (id);

CREATE INDEX ix_pms_components_is_active ON pms_components (is_active);

CREATE INDEX ix_pms_components_default_assignee_user_id ON pms_components (default_assignee_user_id);

CREATE TABLE pms_releases (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	status VARCHAR(40), 
	release_date DATE, 
	owner_user_id INTEGER, 
	readiness_percent INTEGER, 
	launch_notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pms_release_project_name UNIQUE (project_id, name), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_releases_status ON pms_releases (status);

CREATE INDEX ix_pms_releases_release_date ON pms_releases (release_date);

CREATE INDEX ix_pms_releases_project_id ON pms_releases (project_id);

CREATE INDEX ix_pms_releases_name ON pms_releases (name);

CREATE INDEX ix_pms_releases_id ON pms_releases (id);

CREATE INDEX ix_pms_releases_owner_user_id ON pms_releases (owner_user_id);

CREATE TABLE pms_boards (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	board_type VARCHAR(40), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_boards_id ON pms_boards (id);

CREATE INDEX ix_pms_boards_board_type ON pms_boards (board_type);

CREATE INDEX ix_pms_boards_project_id ON pms_boards (project_id);

CREATE TABLE pms_sprints (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	goal TEXT, 
	status VARCHAR(30), 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	capacity_hours NUMERIC(8, 2), 
	velocity_points INTEGER, 
	committed_task_count INTEGER, 
	committed_story_points INTEGER, 
	completed_story_points INTEGER, 
	scope_change_count INTEGER, 
	carry_forward_task_count INTEGER, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	completed_by_user_id INTEGER, 
	commitment_snapshot TEXT, 
	completion_summary TEXT, 
	review_notes TEXT, 
	retrospective_notes TEXT, 
	what_went_well TEXT, 
	what_did_not_go_well TEXT, 
	outcome TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(completed_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_sprints_id ON pms_sprints (id);

CREATE INDEX ix_pms_sprints_project_id ON pms_sprints (project_id);

CREATE INDEX ix_pms_sprints_status ON pms_sprints (status);

CREATE INDEX ix_pms_sprints_completed_by_user_id ON pms_sprints (completed_by_user_id);

CREATE TABLE pms_milestones (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	owner_user_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	description TEXT, 
	status VARCHAR(40), 
	start_date DATE, 
	due_date DATE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	progress_percent INTEGER, 
	client_approval_status VARCHAR(40), 
	client_approved_at TIMESTAMP WITH TIME ZONE, 
	client_rejected_reason TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_milestones_id ON pms_milestones (id);

CREATE INDEX ix_pms_milestones_due_date ON pms_milestones (due_date);

CREATE INDEX ix_pms_milestones_status ON pms_milestones (status);

CREATE INDEX ix_pms_milestones_client_approval_status ON pms_milestones (client_approval_status);

CREATE INDEX ix_pms_milestones_project_id ON pms_milestones (project_id);

CREATE INDEX ix_pms_milestones_owner_user_id ON pms_milestones (owner_user_id);

CREATE TABLE pms_dev_integrations (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	project_id INTEGER NOT NULL, 
	provider VARCHAR(30) NOT NULL, 
	repo_owner VARCHAR(160) NOT NULL, 
	repo_name VARCHAR(180) NOT NULL, 
	access_token_encrypted TEXT, 
	webhook_secret_encrypted TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE, 
	CONSTRAINT uq_pms_dev_integration_repo UNIQUE (project_id, provider, repo_owner, repo_name)
);

CREATE INDEX ix_pms_dev_integrations_id ON pms_dev_integrations (id);

CREATE INDEX ix_pms_dev_integrations_repo_name ON pms_dev_integrations (repo_name);

CREATE INDEX ix_pms_dev_integrations_provider ON pms_dev_integrations (provider);

CREATE INDEX ix_pms_dev_integrations_repo_owner ON pms_dev_integrations (repo_owner);

CREATE INDEX ix_pms_dev_integrations_is_active ON pms_dev_integrations (is_active);

CREATE INDEX ix_pms_dev_integrations_organization_id ON pms_dev_integrations (organization_id);

CREATE INDEX ix_pms_dev_integrations_project_id ON pms_dev_integrations (project_id);

CREATE TABLE pms_saved_filters (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	project_id INTEGER, 
	user_id INTEGER, 
	name VARCHAR(140) NOT NULL, 
	view_type VARCHAR(40), 
	entity_type VARCHAR(40), 
	query TEXT NOT NULL, 
	filters_json TEXT, 
	sort_json TEXT, 
	columns_json TEXT, 
	visibility VARCHAR(30), 
	is_default BOOLEAN, 
	is_shared BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE, 
	CONSTRAINT uq_pms_saved_filter_owner_name UNIQUE (project_id, user_id, name), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_saved_filters_organization_id ON pms_saved_filters (organization_id);

CREATE INDEX ix_pms_saved_filters_user_id ON pms_saved_filters (user_id);

CREATE INDEX ix_pms_saved_filters_visibility ON pms_saved_filters (visibility);

CREATE INDEX ix_pms_saved_filters_id ON pms_saved_filters (id);

CREATE INDEX ix_pms_saved_filters_view_type ON pms_saved_filters (view_type);

CREATE INDEX ix_pms_saved_filters_is_default ON pms_saved_filters (is_default);

CREATE INDEX ix_pms_saved_filters_project_id ON pms_saved_filters (project_id);

CREATE INDEX ix_pms_saved_filters_entity_type ON pms_saved_filters (entity_type);

CREATE INDEX ix_pms_saved_filters_is_shared ON pms_saved_filters (is_shared);

CREATE TABLE srm_goods_receipt_lines (
	id SERIAL NOT NULL, 
	goods_receipt_id INTEGER NOT NULL, 
	purchase_order_line_id INTEGER, 
	product_id INTEGER, 
	warehouse_id INTEGER, 
	item_code VARCHAR(80), 
	description TEXT, 
	quantity NUMERIC(14, 3), 
	accepted_quantity NUMERIC(14, 3), 
	rejected_quantity NUMERIC(14, 3), 
	unit_price NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	line_total NUMERIC(14, 2), 
	metadata_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE SET NULL, 
	FOREIGN KEY(goods_receipt_id) REFERENCES srm_goods_receipts (id) ON DELETE CASCADE, 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE SET NULL, 
	FOREIGN KEY(purchase_order_line_id) REFERENCES srm_purchase_order_lines (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_goods_receipt_lines_goods_receipt_id ON srm_goods_receipt_lines (goods_receipt_id);

CREATE INDEX ix_srm_goods_receipt_lines_item_code ON srm_goods_receipt_lines (item_code);

CREATE INDEX ix_srm_goods_receipt_lines_id ON srm_goods_receipt_lines (id);

CREATE INDEX ix_srm_goods_receipt_lines_purchase_order_line_id ON srm_goods_receipt_lines (purchase_order_line_id);

CREATE INDEX ix_srm_goods_receipt_lines_warehouse_id ON srm_goods_receipt_lines (warehouse_id);

CREATE INDEX ix_srm_goods_receipt_lines_product_id ON srm_goods_receipt_lines (product_id);

CREATE TABLE srm_serial_numbers (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	product_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	batch_id INTEGER, 
	serial_number VARCHAR(160) NOT NULL, 
	status VARCHAR(40), 
	received_date DATE, 
	sold_at TIMESTAMP WITH TIME ZONE, 
	reference_number VARCHAR(120), 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(batch_id) REFERENCES srm_inventory_batches (id) ON DELETE SET NULL, 
	FOREIGN KEY(product_id) REFERENCES srm_products (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_serial_org_number UNIQUE (organization_id, serial_number)
);

CREATE INDEX ix_srm_serial_numbers_organization_id ON srm_serial_numbers (organization_id);

CREATE INDEX ix_srm_serial_numbers_product_id ON srm_serial_numbers (product_id);

CREATE INDEX ix_srm_serial_numbers_serial_number ON srm_serial_numbers (serial_number);

CREATE INDEX ix_srm_serial_numbers_reference_number ON srm_serial_numbers (reference_number);

CREATE INDEX ix_srm_serial_numbers_id ON srm_serial_numbers (id);

CREATE INDEX ix_srm_serial_numbers_warehouse_id ON srm_serial_numbers (warehouse_id);

CREATE INDEX ix_srm_serial_numbers_status ON srm_serial_numbers (status);

CREATE INDEX ix_srm_serial_numbers_created_by ON srm_serial_numbers (created_by);

CREATE INDEX ix_srm_serial_numbers_batch_id ON srm_serial_numbers (batch_id);

CREATE INDEX ix_srm_serial_numbers_received_date ON srm_serial_numbers (received_date);

CREATE INDEX ix_srm_serial_numbers_created_at ON srm_serial_numbers (created_at);

CREATE TABLE srm_bom_components (
	id SERIAL NOT NULL, 
	bom_id INTEGER NOT NULL, 
	component_product_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	quantity NUMERIC(14, 3), 
	scrap_percent NUMERIC(6, 2), 
	unit_cost NUMERIC(14, 4), 
	line_total NUMERIC(14, 2), 
	metadata_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE SET NULL, 
	FOREIGN KEY(bom_id) REFERENCES srm_bills_of_material (id) ON DELETE CASCADE, 
	FOREIGN KEY(component_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT
);

CREATE INDEX ix_srm_bom_components_bom_id ON srm_bom_components (bom_id);

CREATE INDEX ix_srm_bom_components_warehouse_id ON srm_bom_components (warehouse_id);

CREATE INDEX ix_srm_bom_components_id ON srm_bom_components (id);

CREATE INDEX ix_srm_bom_components_component_product_id ON srm_bom_components (component_product_id);

CREATE TABLE srm_production_orders (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	production_number VARCHAR(80) NOT NULL, 
	bom_id INTEGER NOT NULL, 
	finished_product_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	planned_quantity NUMERIC(14, 3), 
	completed_quantity NUMERIC(14, 3), 
	status VARCHAR(40), 
	order_date DATE NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	total_component_cost NUMERIC(14, 2), 
	notes TEXT, 
	metadata_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(finished_product_id) REFERENCES srm_products (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_srm_production_order_org_number UNIQUE (organization_id, production_number), 
	FOREIGN KEY(warehouse_id) REFERENCES srm_warehouses (id) ON DELETE SET NULL, 
	FOREIGN KEY(bom_id) REFERENCES srm_bills_of_material (id) ON DELETE RESTRICT
);

CREATE INDEX ix_srm_production_orders_organization_id ON srm_production_orders (organization_id);

CREATE INDEX ix_srm_production_orders_warehouse_id ON srm_production_orders (warehouse_id);

CREATE INDEX ix_srm_production_orders_created_by ON srm_production_orders (created_by);

CREATE INDEX ix_srm_production_orders_id ON srm_production_orders (id);

CREATE INDEX ix_srm_production_orders_finished_product_id ON srm_production_orders (finished_product_id);

CREATE INDEX ix_srm_production_orders_status ON srm_production_orders (status);

CREATE INDEX ix_srm_production_orders_created_at ON srm_production_orders (created_at);

CREATE INDEX ix_srm_production_orders_production_number ON srm_production_orders (production_number);

CREATE INDEX ix_srm_production_orders_bom_id ON srm_production_orders (bom_id);

CREATE INDEX ix_srm_production_orders_order_date ON srm_production_orders (order_date);

CREATE TABLE srm_engagement_links (
	id SERIAL NOT NULL, 
	engagement_id INTEGER NOT NULL, 
	linked_module VARCHAR(80) NOT NULL, 
	linked_entity_type VARCHAR(80) NOT NULL, 
	linked_entity_id INTEGER NOT NULL, 
	label VARCHAR(180), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE CASCADE, 
	CONSTRAINT uq_srm_engagement_link UNIQUE (engagement_id, linked_module, linked_entity_type, linked_entity_id)
);

CREATE INDEX ix_srm_engagement_links_id ON srm_engagement_links (id);

CREATE INDEX ix_srm_engagement_links_linked_entity_type ON srm_engagement_links (linked_entity_type);

CREATE INDEX ix_srm_engagement_links_linked_entity_id ON srm_engagement_links (linked_entity_id);

CREATE INDEX ix_srm_engagement_links_engagement_id ON srm_engagement_links (engagement_id);

CREATE INDEX ix_srm_engagement_links_linked_module ON srm_engagement_links (linked_module);

CREATE TABLE srm_billing_plans (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	engagement_id INTEGER NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	billing_type VARCHAR(40), 
	status VARCHAR(40), 
	currency VARCHAR(10), 
	total_amount NUMERIC(14, 2), 
	recurrence_rule VARCHAR(120), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_billing_plans_id ON srm_billing_plans (id);

CREATE INDEX ix_srm_billing_plans_organization_id ON srm_billing_plans (organization_id);

CREATE INDEX ix_srm_billing_plans_billing_type ON srm_billing_plans (billing_type);

CREATE INDEX ix_srm_billing_plans_status ON srm_billing_plans (status);

CREATE INDEX ix_srm_billing_plans_engagement_id ON srm_billing_plans (engagement_id);

CREATE TABLE srm_profitability_snapshots (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	engagement_id INTEGER, 
	customer_id INTEGER, 
	quoted_amount NUMERIC(14, 2), 
	order_amount NUMERIC(14, 2), 
	contract_amount NUMERIC(14, 2), 
	billing_amount NUMERIC(14, 2), 
	invoiced_amount NUMERIC(14, 2), 
	collected_amount NUMERIC(14, 2), 
	outstanding_amount NUMERIC(14, 2), 
	overdue_amount NUMERIC(14, 2), 
	cost_amount NUMERIC(14, 2), 
	gross_margin_amount NUMERIC(14, 2), 
	gross_margin_percent NUMERIC(6, 2), 
	cash_margin_amount NUMERIC(14, 2), 
	status VARCHAR(40), 
	snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_profitability_snapshots_customer_id ON srm_profitability_snapshots (customer_id);

CREATE INDEX ix_srm_profitability_snapshots_snapshot_at ON srm_profitability_snapshots (snapshot_at);

CREATE INDEX ix_srm_profitability_snapshots_organization_id ON srm_profitability_snapshots (organization_id);

CREATE INDEX ix_srm_profitability_snapshots_engagement_id ON srm_profitability_snapshots (engagement_id);

CREATE INDEX ix_srm_profitability_snapshots_id ON srm_profitability_snapshots (id);

CREATE INDEX ix_srm_profitability_snapshots_status ON srm_profitability_snapshots (status);

CREATE TABLE fam_bill_allocations (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	allocation_date DATE NOT NULL, 
	party_id INTEGER NOT NULL, 
	from_bill_reference_id INTEGER NOT NULL, 
	to_bill_reference_id INTEGER NOT NULL, 
	voucher_id INTEGER, 
	allocated_amount NUMERIC(14, 2), 
	allocation_type VARCHAR(30) NOT NULL, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE SET NULL, 
	FOREIGN KEY(from_bill_reference_id) REFERENCES fam_bill_references (id) ON DELETE RESTRICT, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(to_bill_reference_id) REFERENCES fam_bill_references (id) ON DELETE RESTRICT, 
	FOREIGN KEY(party_id) REFERENCES fam_parties (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_bill_allocations_company_id ON fam_bill_allocations (company_id);

CREATE INDEX ix_fam_bill_allocations_from_bill_reference_id ON fam_bill_allocations (from_bill_reference_id);

CREATE INDEX ix_fam_bill_allocations_created_by ON fam_bill_allocations (created_by);

CREATE INDEX ix_fam_bill_allocations_id ON fam_bill_allocations (id);

CREATE INDEX ix_fam_bill_allocations_to_bill_reference_id ON fam_bill_allocations (to_bill_reference_id);

CREATE INDEX ix_fam_bill_allocations_voucher_id ON fam_bill_allocations (voucher_id);

CREATE INDEX ix_fam_bill_allocations_party_id ON fam_bill_allocations (party_id);

CREATE INDEX ix_fam_bill_allocations_allocation_date ON fam_bill_allocations (allocation_date);

CREATE INDEX ix_fam_bill_allocations_allocation_type ON fam_bill_allocations (allocation_type);

CREATE TABLE fam_bank_reconciliation_matches (
	id SERIAL NOT NULL, 
	statement_line_id INTEGER NOT NULL, 
	voucher_id INTEGER NOT NULL, 
	ledger_entry_id INTEGER, 
	match_type VARCHAR(30) NOT NULL, 
	confidence_score NUMERIC(5, 2), 
	matched_amount NUMERIC(14, 2), 
	matched_by INTEGER, 
	matched_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(matched_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(voucher_id) REFERENCES fam_vouchers (id) ON DELETE RESTRICT, 
	FOREIGN KEY(ledger_entry_id) REFERENCES fam_ledger_entries (id) ON DELETE SET NULL, 
	CONSTRAINT uq_fam_bank_recon_line_voucher UNIQUE (statement_line_id, voucher_id), 
	FOREIGN KEY(statement_line_id) REFERENCES fam_bank_statement_lines (id) ON DELETE CASCADE
);

CREATE INDEX ix_fam_bank_reconciliation_matches_ledger_entry_id ON fam_bank_reconciliation_matches (ledger_entry_id);

CREATE INDEX ix_fam_bank_reconciliation_matches_match_type ON fam_bank_reconciliation_matches (match_type);

CREATE INDEX ix_fam_bank_reconciliation_matches_id ON fam_bank_reconciliation_matches (id);

CREATE INDEX ix_fam_bank_reconciliation_matches_voucher_id ON fam_bank_reconciliation_matches (voucher_id);

CREATE INDEX ix_fam_bank_reconciliation_matches_matched_at ON fam_bank_reconciliation_matches (matched_at);

CREATE INDEX ix_fam_bank_reconciliation_matches_statement_line_id ON fam_bank_reconciliation_matches (statement_line_id);

CREATE INDEX ix_fam_bank_reconciliation_matches_matched_by ON fam_bank_reconciliation_matches (matched_by);

CREATE TABLE fam_vendor_payment_items (
	id SERIAL NOT NULL, 
	payment_run_id INTEGER NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	purchase_bill_id INTEGER, 
	bill_reference_id INTEGER, 
	amount NUMERIC(14, 2), 
	status VARCHAR(30), 
	PRIMARY KEY (id), 
	FOREIGN KEY(vendor_id) REFERENCES fam_parties (id) ON DELETE RESTRICT, 
	FOREIGN KEY(purchase_bill_id) REFERENCES fam_purchase_bills (id) ON DELETE SET NULL, 
	FOREIGN KEY(payment_run_id) REFERENCES fam_vendor_payment_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(bill_reference_id) REFERENCES fam_bill_references (id) ON DELETE SET NULL
);

CREATE INDEX ix_fam_vendor_payment_items_id ON fam_vendor_payment_items (id);

CREATE INDEX ix_fam_vendor_payment_items_vendor_id ON fam_vendor_payment_items (vendor_id);

CREATE INDEX ix_fam_vendor_payment_items_payment_run_id ON fam_vendor_payment_items (payment_run_id);

CREATE INDEX ix_fam_vendor_payment_items_status ON fam_vendor_payment_items (status);

CREATE INDEX ix_fam_vendor_payment_items_purchase_bill_id ON fam_vendor_payment_items (purchase_bill_id);

CREATE INDEX ix_fam_vendor_payment_items_bill_reference_id ON fam_vendor_payment_items (bill_reference_id);

CREATE TABLE fam_inventory_valuation_layers (
	id SERIAL NOT NULL, 
	company_id INTEGER NOT NULL, 
	stock_item_id INTEGER NOT NULL, 
	warehouse_id INTEGER, 
	movement_id INTEGER, 
	movement_line_id INTEGER, 
	valuation_method VARCHAR(40), 
	quantity NUMERIC(14, 3), 
	unit_cost NUMERIC(14, 4), 
	layer_value NUMERIC(14, 2), 
	remaining_quantity NUMERIC(14, 3), 
	remaining_value NUMERIC(14, 2), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(movement_line_id) REFERENCES fam_stock_movement_lines (id) ON DELETE SET NULL, 
	FOREIGN KEY(warehouse_id) REFERENCES fam_warehouses (id) ON DELETE RESTRICT, 
	FOREIGN KEY(movement_id) REFERENCES fam_stock_movements (id) ON DELETE SET NULL, 
	FOREIGN KEY(stock_item_id) REFERENCES fam_stock_items (id) ON DELETE RESTRICT
);

CREATE INDEX ix_fam_inventory_valuation_layers_id ON fam_inventory_valuation_layers (id);

CREATE INDEX ix_fam_inventory_valuation_layers_movement_line_id ON fam_inventory_valuation_layers (movement_line_id);

CREATE INDEX ix_fam_inventory_valuation_layers_created_at ON fam_inventory_valuation_layers (created_at);

CREATE INDEX ix_fam_inventory_valuation_layers_warehouse_id ON fam_inventory_valuation_layers (warehouse_id);

CREATE INDEX ix_fam_inventory_valuation_layers_movement_id ON fam_inventory_valuation_layers (movement_id);

CREATE INDEX ix_fam_inventory_valuation_layers_company_id ON fam_inventory_valuation_layers (company_id);

CREATE INDEX ix_fam_inventory_valuation_layers_stock_item_id ON fam_inventory_valuation_layers (stock_item_id);

CREATE INDEX ix_fam_inventory_valuation_layers_valuation_method ON fam_inventory_valuation_layers (valuation_method);

CREATE TABLE employees (
	id SERIAL NOT NULL, 
	employee_id VARCHAR(50) NOT NULL, 
	user_id INTEGER, 
	salutation VARCHAR(20), 
	first_name VARCHAR(80) NOT NULL, 
	middle_name TEXT, 
	last_name VARCHAR(80) NOT NULL, 
	gender TEXT, 
	date_of_birth DATE, 
	place_of_birth TEXT, 
	marital_status TEXT, 
	blood_group TEXT, 
	nationality TEXT, 
	domicile_state TEXT, 
	religion TEXT, 
	category TEXT, 
	sub_caste TEXT, 
	gender_identity TEXT, 
	disability_status TEXT, 
	disability_percentage NUMERIC(5, 2), 
	disability_certificate_number TEXT, 
	ex_serviceman BOOLEAN, 
	veteran_status TEXT, 
	father_name TEXT, 
	mother_name TEXT, 
	spouse_name TEXT, 
	spouse_occupation TEXT, 
	number_of_dependants INTEGER, 
	work_email VARCHAR(150), 
	personal_email VARCHAR(150), 
	phone_number VARCHAR(20), 
	alternate_phone TEXT, 
	whatsapp_number TEXT, 
	office_extension TEXT, 
	emergency_contact_name TEXT, 
	emergency_contact_number VARCHAR(20), 
	emergency_contact_relation TEXT, 
	present_address TEXT, 
	present_city TEXT, 
	present_state TEXT, 
	present_pincode TEXT, 
	present_country TEXT, 
	permanent_address TEXT, 
	permanent_city TEXT, 
	permanent_state TEXT, 
	permanent_pincode TEXT, 
	permanent_country TEXT, 
	passport_number TEXT, 
	passport_expiry DATE, 
	passport_issue_place TEXT, 
	driving_license_number TEXT, 
	driving_license_expiry DATE, 
	driving_license_class TEXT, 
	voter_id_number TEXT, 
	ration_card_number TEXT, 
	date_of_joining DATE NOT NULL, 
	date_of_confirmation DATE, 
	date_of_exit DATE, 
	branch_id INTEGER, 
	department_id INTEGER, 
	designation_id INTEGER, 
	business_unit_id INTEGER, 
	cost_center_id INTEGER, 
	location_id INTEGER, 
	grade_band_id INTEGER, 
	position_id INTEGER, 
	reporting_manager_id INTEGER, 
	functional_area TEXT, 
	employment_type TEXT, 
	worker_type TEXT, 
	status VARCHAR(30), 
	work_location TEXT, 
	shift_id INTEGER, 
	probation_period_months INTEGER, 
	probation_start_date DATE, 
	probation_end_date DATE, 
	probation_status VARCHAR(30), 
	notice_period_days INTEGER, 
	last_promotion_date DATE, 
	next_promotion_due_date DATE, 
	flexi_timing_applicable BOOLEAN, 
	work_from_home_eligible BOOLEAN, 
	desk_code TEXT, 
	seat_number TEXT, 
	timezone TEXT, 
	manager_chain_path TEXT, 
	contract_start_date DATE, 
	contract_end_date DATE, 
	contract_reference_number TEXT, 
	contractor_company TEXT, 
	bond_applicable BOOLEAN, 
	bond_amount NUMERIC(12, 2), 
	bond_end_date DATE, 
	bond_remarks TEXT, 
	academic_rank TEXT, 
	subjects_taught JSON, 
	class_assigned TEXT, 
	teaching_experience_years NUMERIC(4, 1), 
	research_areas TEXT, 
	publications_count INTEGER, 
	h_index INTEGER, 
	orcid_id TEXT, 
	google_scholar_url TEXT, 
	medical_specialty TEXT, 
	medical_sub_specialty TEXT, 
	clinical_grade TEXT, 
	service_number TEXT, 
	service_type TEXT, 
	cadre TEXT, 
	pay_level VARCHAR(20), 
	pay_band VARCHAR(50), 
	grade_pay NUMERIC(10, 2), 
	worker_category TEXT, 
	trade TEXT, 
	apprentice_type TEXT, 
	factory_gate_number TEXT, 
	professional_reg_number TEXT, 
	professional_reg_body TEXT, 
	professional_reg_expiry DATE, 
	background_verification_status TEXT, 
	background_verification_date DATE, 
	background_verification_agency TEXT, 
	bank_name TEXT, 
	bank_branch TEXT, 
	account_number TEXT, 
	account_type TEXT, 
	ifsc_code TEXT, 
	micr_code TEXT, 
	pan_number TEXT, 
	aadhaar_number TEXT, 
	uan_number TEXT, 
	pf_number TEXT, 
	esic_number TEXT, 
	salary_currency TEXT, 
	is_nri BOOLEAN, 
	nri_bank_account_type TEXT, 
	tax_regime_preference TEXT, 
	form_16_delivery TEXT, 
	linkedin_url TEXT, 
	github_username TEXT, 
	portfolio_url TEXT, 
	research_gate_url TEXT, 
	languages_known JSON, 
	profile_photo_url TEXT, 
	preferred_display_name TEXT, 
	directory_visibility VARCHAR(20), 
	skills_tags TEXT, 
	profile_completeness INTEGER, 
	bio TEXT, 
	interests TEXT, 
	research_work TEXT, 
	family_information TEXT, 
	health_information TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	deleted_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(designation_id) REFERENCES designations (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(shift_id) REFERENCES shifts (id) ON DELETE SET NULL, 
	FOREIGN KEY(position_id) REFERENCES positions (id) ON DELETE SET NULL, 
	FOREIGN KEY(location_id) REFERENCES work_locations (id) ON DELETE SET NULL, 
	FOREIGN KEY(business_unit_id) REFERENCES business_units (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deleted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(reporting_manager_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(grade_band_id) REFERENCES grade_bands (id) ON DELETE SET NULL, 
	FOREIGN KEY(cost_center_id) REFERENCES cost_centers (id) ON DELETE SET NULL
);

CREATE INDEX idx_employees_name ON employees (first_name, last_name);

CREATE INDEX idx_employees_directory_email ON employees (work_email, personal_email);

CREATE UNIQUE INDEX ix_employees_employee_id ON employees (employee_id);

CREATE INDEX ix_employees_directory_visibility ON employees (directory_visibility);

CREATE INDEX idx_employees_active_status ON employees (deleted_at, status);

CREATE INDEX idx_employees_department_status ON employees (department_id, status, deleted_at);

CREATE INDEX ix_employees_id ON employees (id);

CREATE INDEX ix_employees_work_email ON employees (work_email);

CREATE INDEX ix_employees_probation_status ON employees (probation_status);

CREATE INDEX idx_employees_manager_status ON employees (reporting_manager_id, status, deleted_at);

CREATE TABLE statutory_return_files (
	id SERIAL NOT NULL, 
	challan_id INTEGER NOT NULL, 
	return_type VARCHAR(50) NOT NULL, 
	format_version VARCHAR(30), 
	file_url VARCHAR(500), 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	validation_status VARCHAR(30), 
	validation_errors_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(challan_id) REFERENCES statutory_challans (id) ON DELETE CASCADE
);

CREATE INDEX ix_statutory_return_files_validation_status ON statutory_return_files (validation_status);

CREATE INDEX ix_statutory_return_files_id ON statutory_return_files (id);

CREATE INDEX ix_statutory_return_files_return_type ON statutory_return_files (return_type);

CREATE INDEX ix_statutory_return_files_challan_id ON statutory_return_files (challan_id);

CREATE TABLE crm_leads (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	assigned_team_id INTEGER, 
	territory_id INTEGER, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100), 
	full_name VARCHAR(220) NOT NULL, 
	email VARCHAR(150), 
	phone VARCHAR(40), 
	alternate_phone VARCHAR(40), 
	company_name VARCHAR(180), 
	job_title VARCHAR(120), 
	source VARCHAR(80), 
	status VARCHAR(40), 
	rating VARCHAR(20), 
	lead_score INTEGER, 
	lead_score_label VARCHAR(20), 
	lead_score_mode VARCHAR(20), 
	last_score_calculated_at TIMESTAMP WITH TIME ZONE, 
	industry VARCHAR(120), 
	website VARCHAR(200), 
	linkedin_url VARCHAR(300), 
	company_website VARCHAR(200), 
	employee_count INTEGER, 
	email_verification_status VARCHAR(40), 
	social_profiles_json JSON, 
	city VARCHAR(100), 
	state VARCHAR(100), 
	country VARCHAR(100), 
	address TEXT, 
	estimated_value NUMERIC(12, 2), 
	expected_close_date DATE, 
	last_contacted_at TIMESTAMP WITH TIME ZONE, 
	next_follow_up_at TIMESTAMP WITH TIME ZONE, 
	is_converted BOOLEAN, 
	converted_at TIMESTAMP WITH TIME ZONE, 
	converted_contact_id INTEGER, 
	converted_company_id INTEGER, 
	converted_deal_id INTEGER, 
	tags_text VARCHAR(500), 
	notes TEXT, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(converted_deal_id) REFERENCES crm_deals (id) ON DELETE SET NULL, 
	FOREIGN KEY(converted_contact_id) REFERENCES crm_contacts (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(converted_company_id) REFERENCES crm_companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(territory_id) REFERENCES crm_territories (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_leads_department_id ON crm_leads (department_id);

CREATE INDEX ix_crm_leads_industry ON crm_leads (industry);

CREATE INDEX ix_crm_leads_territory_id ON crm_leads (territory_id);

CREATE INDEX ix_crm_leads_email_verification_status ON crm_leads (email_verification_status);

CREATE INDEX ix_crm_leads_full_name ON crm_leads (full_name);

CREATE INDEX ix_crm_leads_city ON crm_leads (city);

CREATE INDEX ix_crm_leads_email ON crm_leads (email);

CREATE INDEX ix_crm_leads_expected_close_date ON crm_leads (expected_close_date);

CREATE INDEX ix_crm_leads_phone ON crm_leads (phone);

CREATE INDEX ix_crm_leads_next_follow_up_at ON crm_leads (next_follow_up_at);

CREATE INDEX ix_crm_leads_company_name ON crm_leads (company_name);

CREATE INDEX ix_crm_leads_is_converted ON crm_leads (is_converted);

CREATE INDEX ix_crm_leads_source ON crm_leads (source);

CREATE INDEX ix_crm_leads_organization_id ON crm_leads (organization_id);

CREATE INDEX ix_crm_leads_status ON crm_leads (status);

CREATE INDEX ix_crm_leads_id ON crm_leads (id);

CREATE INDEX ix_crm_leads_rating ON crm_leads (rating);

CREATE INDEX ix_crm_leads_owner_user_id ON crm_leads (owner_user_id);

CREATE INDEX ix_crm_leads_lead_score ON crm_leads (lead_score);

CREATE INDEX ix_crm_leads_branch_id ON crm_leads (branch_id);

CREATE INDEX ix_crm_leads_lead_score_label ON crm_leads (lead_score_label);

CREATE INDEX ix_crm_leads_assigned_team_id ON crm_leads (assigned_team_id);

CREATE INDEX ix_crm_leads_lead_score_mode ON crm_leads (lead_score_mode);

CREATE TABLE crm_deal_contacts (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	deal_id INTEGER NOT NULL, 
	contact_id INTEGER NOT NULL, 
	role VARCHAR(80), 
	influence_level VARCHAR(40), 
	is_primary BOOLEAN, 
	notes TEXT, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE CASCADE, 
	CONSTRAINT uq_crm_deal_contact UNIQUE (deal_id, contact_id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_deal_contacts_organization_id ON crm_deal_contacts (organization_id);

CREATE INDEX ix_crm_deal_contacts_influence_level ON crm_deal_contacts (influence_level);

CREATE INDEX ix_crm_deal_contacts_deal_id ON crm_deal_contacts (deal_id);

CREATE INDEX ix_crm_deal_contacts_role ON crm_deal_contacts (role);

CREATE INDEX ix_crm_deal_contacts_id ON crm_deal_contacts (id);

CREATE INDEX ix_crm_deal_contacts_contact_id ON crm_deal_contacts (contact_id);

CREATE INDEX ix_crm_deal_contacts_is_primary ON crm_deal_contacts (is_primary);

CREATE TABLE crm_deal_products (
	id SERIAL NOT NULL, 
	deal_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER, 
	unit_price NUMERIC(12, 2), 
	discount_amount NUMERIC(12, 2), 
	tax_rate NUMERIC(5, 2), 
	total_amount NUMERIC(12, 2), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES crm_products (id) ON DELETE CASCADE, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_deal_products_deal_id ON crm_deal_products (deal_id);

CREATE INDEX ix_crm_deal_products_id ON crm_deal_products (id);

CREATE INDEX ix_crm_deal_products_product_id ON crm_deal_products (product_id);

CREATE TABLE crm_quotations (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	deal_id INTEGER, 
	company_id INTEGER, 
	account_id INTEGER, 
	contact_id INTEGER, 
	owner_user_id INTEGER, 
	owner_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	assigned_team_id INTEGER, 
	quote_number VARCHAR(60) NOT NULL, 
	issue_date DATE NOT NULL, 
	quote_date DATE, 
	expiry_date DATE NOT NULL, 
	valid_until DATE, 
	status VARCHAR(30), 
	approval_status VARCHAR(30), 
	currency VARCHAR(10), 
	subtotal NUMERIC(12, 2), 
	discount_amount NUMERIC(12, 2), 
	discount_total NUMERIC(14, 2), 
	tax_amount NUMERIC(12, 2), 
	tax_total NUMERIC(14, 2), 
	total_amount NUMERIC(12, 2), 
	grand_total NUMERIC(14, 2), 
	estimated_cost NUMERIC(14, 2), 
	expected_margin NUMERIC(14, 2), 
	margin_percentage NUMERIC(6, 2), 
	version_number INTEGER, 
	terms TEXT, 
	terms_and_conditions TEXT, 
	notes TEXT, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	declined_at TIMESTAMP WITH TIME ZONE, 
	converted_srm_sales_order_id INTEGER, 
	converted_srm_contract_id INTEGER, 
	converted_srm_engagement_id INTEGER, 
	pdf_url VARCHAR(500), 
	pdf_file_name VARCHAR(180), 
	pdf_status VARCHAR(30), 
	pdf_generated_at TIMESTAMP WITH TIME ZONE, 
	pdf_generated_by_user_id INTEGER, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(account_id) REFERENCES crm_companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE SET NULL, 
	FOREIGN KEY(pdf_generated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE SET NULL, 
	CONSTRAINT uq_crm_quote_org_number UNIQUE (organization_id, quote_number)
);

CREATE INDEX ix_crm_quotations_valid_until ON crm_quotations (valid_until);

CREATE INDEX ix_crm_quotations_organization_id ON crm_quotations (organization_id);

CREATE INDEX ix_crm_quotations_status ON crm_quotations (status);

CREATE INDEX ix_crm_quotations_id ON crm_quotations (id);

CREATE INDEX ix_crm_quotations_account_id ON crm_quotations (account_id);

CREATE INDEX ix_crm_quotations_approval_status ON crm_quotations (approval_status);

CREATE INDEX ix_crm_quotations_company_id ON crm_quotations (company_id);

CREATE INDEX ix_crm_quotations_version_number ON crm_quotations (version_number);

CREATE INDEX ix_crm_quotations_contact_id ON crm_quotations (contact_id);

CREATE INDEX ix_crm_quotations_converted_srm_sales_order_id ON crm_quotations (converted_srm_sales_order_id);

CREATE INDEX ix_crm_quotations_owner_user_id ON crm_quotations (owner_user_id);

CREATE INDEX ix_crm_quotations_converted_srm_contract_id ON crm_quotations (converted_srm_contract_id);

CREATE INDEX ix_crm_quotations_owner_id ON crm_quotations (owner_id);

CREATE INDEX ix_crm_quotations_converted_srm_engagement_id ON crm_quotations (converted_srm_engagement_id);

CREATE INDEX ix_crm_quotations_branch_id ON crm_quotations (branch_id);

CREATE INDEX ix_crm_quotations_department_id ON crm_quotations (department_id);

CREATE INDEX ix_crm_quotations_assigned_team_id ON crm_quotations (assigned_team_id);

CREATE INDEX ix_crm_quotations_quote_number ON crm_quotations (quote_number);

CREATE INDEX ix_crm_quotations_expiry_date ON crm_quotations (expiry_date);

CREATE INDEX ix_crm_quotations_deal_id ON crm_quotations (deal_id);

CREATE TABLE pms_board_columns (
	id SERIAL NOT NULL, 
	board_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	status_key VARCHAR(60) NOT NULL, 
	position INTEGER, 
	wip_limit INTEGER, 
	is_collapsed BOOLEAN, 
	color VARCHAR(30), 
	PRIMARY KEY (id), 
	FOREIGN KEY(board_id) REFERENCES pms_boards (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_board_columns_status_key ON pms_board_columns (status_key);

CREATE INDEX ix_pms_board_columns_id ON pms_board_columns (id);

CREATE INDEX ix_pms_board_columns_board_id ON pms_board_columns (board_id);

CREATE TABLE pms_client_approvals (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	milestone_id INTEGER, 
	requested_by_user_id INTEGER, 
	client_user_id INTEGER, 
	status VARCHAR(30), 
	remarks TEXT, 
	decided_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(requested_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(client_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(milestone_id) REFERENCES pms_milestones (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_client_approvals_project_id ON pms_client_approvals (project_id);

CREATE INDEX ix_pms_client_approvals_status ON pms_client_approvals (status);

CREATE INDEX ix_pms_client_approvals_milestone_id ON pms_client_approvals (milestone_id);

CREATE INDEX ix_pms_client_approvals_id ON pms_client_approvals (id);

CREATE TABLE srm_billing_milestones (
	id SERIAL NOT NULL, 
	billing_plan_id INTEGER NOT NULL, 
	name VARCHAR(180) NOT NULL, 
	status VARCHAR(40), 
	due_date DATE, 
	amount NUMERIC(14, 2), 
	invoice_draft_id INTEGER, 
	metadata_json JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(billing_plan_id) REFERENCES srm_billing_plans (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_billing_milestones_id ON srm_billing_milestones (id);

CREATE INDEX ix_srm_billing_milestones_due_date ON srm_billing_milestones (due_date);

CREATE INDEX ix_srm_billing_milestones_invoice_draft_id ON srm_billing_milestones (invoice_draft_id);

CREATE INDEX ix_srm_billing_milestones_status ON srm_billing_milestones (status);

CREATE INDEX ix_srm_billing_milestones_billing_plan_id ON srm_billing_milestones (billing_plan_id);

CREATE TABLE srm_invoice_drafts (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	sales_order_id INTEGER, 
	engagement_id INTEGER, 
	billing_plan_id INTEGER, 
	customer_id INTEGER, 
	status VARCHAR(40), 
	source_type VARCHAR(60) NOT NULL, 
	currency VARCHAR(10), 
	subtotal NUMERIC(14, 2), 
	discount_amount NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	total_amount NUMERIC(14, 2), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE SET NULL, 
	FOREIGN KEY(billing_plan_id) REFERENCES srm_billing_plans (id) ON DELETE SET NULL, 
	FOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_invoice_drafts_customer_id ON srm_invoice_drafts (customer_id);

CREATE INDEX ix_srm_invoice_drafts_created_at ON srm_invoice_drafts (created_at);

CREATE INDEX ix_srm_invoice_drafts_engagement_id ON srm_invoice_drafts (engagement_id);

CREATE INDEX ix_srm_invoice_drafts_status ON srm_invoice_drafts (status);

CREATE INDEX ix_srm_invoice_drafts_sales_order_id ON srm_invoice_drafts (sales_order_id);

CREATE INDEX ix_srm_invoice_drafts_billing_plan_id ON srm_invoice_drafts (billing_plan_id);

CREATE INDEX ix_srm_invoice_drafts_source_type ON srm_invoice_drafts (source_type);

CREATE INDEX ix_srm_invoice_drafts_id ON srm_invoice_drafts (id);

CREATE INDEX ix_srm_invoice_drafts_organization_id ON srm_invoice_drafts (organization_id);

CREATE TABLE field_audit_events (
	id SERIAL NOT NULL, 
	module VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(100) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	employee_id INTEGER, 
	field_name VARCHAR(120) NOT NULL, 
	action VARCHAR(50), 
	old_value_masked VARCHAR(500), 
	new_value_masked VARCHAR(500), 
	old_value_hash VARCHAR(128), 
	new_value_hash VARCHAR(128), 
	old_value_plaintext TEXT, 
	new_value_plaintext TEXT, 
	is_sensitive BOOLEAN, 
	actor_user_id INTEGER, 
	reason TEXT, 
	request_id VARCHAR(120), 
	ip_address VARCHAR(50), 
	metadata_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL
);

CREATE INDEX ix_field_audit_events_actor_user_id ON field_audit_events (actor_user_id);

CREATE INDEX idx_field_audit_hash ON field_audit_events (new_value_hash);

CREATE INDEX ix_field_audit_events_module ON field_audit_events (module);

CREATE INDEX ix_field_audit_events_field_name ON field_audit_events (field_name);

CREATE INDEX ix_field_audit_events_new_value_hash ON field_audit_events (new_value_hash);

CREATE INDEX ix_field_audit_events_created_at ON field_audit_events (created_at);

CREATE INDEX idx_field_audit_module_actor ON field_audit_events (module, actor_user_id, created_at);

CREATE INDEX ix_field_audit_events_id ON field_audit_events (id);

CREATE INDEX ix_field_audit_events_entity_type ON field_audit_events (entity_type);

CREATE INDEX ix_field_audit_events_action ON field_audit_events (action);

CREATE INDEX ix_field_audit_events_is_sensitive ON field_audit_events (is_sensitive);

CREATE INDEX idx_field_audit_employee_field ON field_audit_events (employee_id, field_name, created_at);

CREATE INDEX ix_field_audit_events_entity_id ON field_audit_events (entity_id);

CREATE INDEX ix_field_audit_events_employee_id ON field_audit_events (employee_id);

CREATE INDEX ix_field_audit_events_old_value_hash ON field_audit_events (old_value_hash);

CREATE TABLE employee_educations (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	degree VARCHAR(100) NOT NULL, 
	specialization VARCHAR(150), 
	institution VARCHAR(200), 
	board_university VARCHAR(200), 
	pass_year INTEGER, 
	from_year INTEGER, 
	percentage_cgpa NUMERIC(5, 2), 
	grade_class VARCHAR(30), 
	education_mode VARCHAR(30), 
	is_highest_qualification BOOLEAN, 
	roll_number VARCHAR(50), 
	registration_number VARCHAR(50), 
	document_url VARCHAR(500), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_educations_id ON employee_educations (id);

CREATE TABLE employee_experiences (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	company_name VARCHAR(200) NOT NULL, 
	company_industry VARCHAR(100), 
	company_location VARCHAR(150), 
	designation VARCHAR(150), 
	department VARCHAR(100), 
	employment_type VARCHAR(30), 
	from_date DATE, 
	to_date DATE, 
	is_current BOOLEAN, 
	responsibilities TEXT, 
	reason_for_leaving VARCHAR(200), 
	last_drawn_salary NUMERIC(12, 2), 
	last_drawn_currency VARCHAR(3), 
	reference_name VARCHAR(150), 
	reference_contact VARCHAR(30), 
	appointment_letter_url VARCHAR(500), 
	relieving_letter_url VARCHAR(500), 
	experience_certificate_url VARCHAR(500), 
	payslip_url VARCHAR(500), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_experiences_id ON employee_experiences (id);

CREATE TABLE employee_skills (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	skill_name VARCHAR(100) NOT NULL, 
	proficiency VARCHAR(30), 
	years_experience NUMERIC(4, 1), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_skills_id ON employee_skills (id);

CREATE TABLE employee_certifications (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	certification_name VARCHAR(200) NOT NULL, 
	issuing_body VARCHAR(200), 
	certification_type VARCHAR(50), 
	certificate_number VARCHAR(100), 
	issue_date DATE, 
	expiry_date DATE, 
	is_renewable BOOLEAN, 
	score_grade VARCHAR(50), 
	document_url VARCHAR(500), 
	verification_url VARCHAR(500), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_certifications_id ON employee_certifications (id);

CREATE TABLE employee_family_members (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	full_name VARCHAR(150) NOT NULL, 
	relation VARCHAR(50) NOT NULL, 
	gender VARCHAR(20), 
	date_of_birth DATE, 
	occupation VARCHAR(100), 
	phone_number VARCHAR(20), 
	is_dependent BOOLEAN, 
	is_emergency_contact BOOLEAN, 
	is_pf_nominee BOOLEAN, 
	pf_nominee_share_percent NUMERIC(5, 2), 
	is_insurance_covered BOOLEAN, 
	aadhaar_number VARCHAR(20), 
	address TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_family_members_id ON employee_family_members (id);

CREATE TABLE employee_documents (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	document_type VARCHAR(100) NOT NULL, 
	document_name VARCHAR(200), 
	document_number VARCHAR(100), 
	file_url VARCHAR(500), 
	expiry_date DATE, 
	verification_status VARCHAR(30), 
	is_verified BOOLEAN, 
	verified_by INTEGER, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	verifier_name VARCHAR(150), 
	verifier_company VARCHAR(200), 
	verification_notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(verified_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_employee_documents_verification_status ON employee_documents (verification_status);

CREATE INDEX ix_employee_documents_id ON employee_documents (id);

CREATE TABLE employee_lifecycle_events (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	event_type VARCHAR(50) NOT NULL, 
	event_date DATE NOT NULL, 
	effective_from DATE, 
	effective_to DATE, 
	from_status VARCHAR(30), 
	to_status VARCHAR(30), 
	from_branch_id INTEGER, 
	to_branch_id INTEGER, 
	from_department_id INTEGER, 
	to_department_id INTEGER, 
	from_designation_id INTEGER, 
	to_designation_id INTEGER, 
	from_manager_id INTEGER, 
	to_manager_id INTEGER, 
	reason TEXT, 
	remarks TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(to_manager_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(to_designation_id) REFERENCES designations (id) ON DELETE SET NULL, 
	FOREIGN KEY(to_department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(to_branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(from_manager_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(from_designation_id) REFERENCES designations (id) ON DELETE SET NULL, 
	FOREIGN KEY(from_department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(from_branch_id) REFERENCES branches (id) ON DELETE SET NULL
);

CREATE INDEX ix_employee_lifecycle_events_id ON employee_lifecycle_events (id);

CREATE INDEX ix_employee_lifecycle_events_event_type ON employee_lifecycle_events (event_type);

CREATE INDEX ix_employee_lifecycle_events_employee_id ON employee_lifecycle_events (employee_id);

CREATE TABLE employee_change_requests (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	request_type VARCHAR(60) NOT NULL, 
	field_name VARCHAR(120), 
	effective_date DATE, 
	field_changes_json JSON NOT NULL, 
	old_value_json JSON, 
	new_value_json JSON, 
	document_path VARCHAR(500), 
	status VARCHAR(30), 
	reason TEXT, 
	requested_by INTEGER, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_change_requests_id ON employee_change_requests (id);

CREATE INDEX ix_employee_change_requests_request_type ON employee_change_requests (request_type);

CREATE INDEX ix_employee_change_requests_organization_id ON employee_change_requests (organization_id);

CREATE INDEX ix_employee_change_requests_status ON employee_change_requests (status);

CREATE INDEX ix_employee_change_requests_employee_id ON employee_change_requests (employee_id);

CREATE INDEX ix_employee_change_requests_field_name ON employee_change_requests (field_name);

CREATE TABLE probation_reviews (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	manager_id INTEGER, 
	review_date DATE NOT NULL, 
	performance_rating INTEGER, 
	conduct_rating INTEGER, 
	attendance_rating INTEGER, 
	recommendation VARCHAR(30) NOT NULL, 
	comments TEXT, 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(manager_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_probation_reviews_id ON probation_reviews (id);

CREATE INDEX ix_probation_reviews_manager_id ON probation_reviews (manager_id);

CREATE INDEX ix_probation_reviews_status ON probation_reviews (status);

CREATE INDEX ix_probation_reviews_organization_id ON probation_reviews (organization_id);

CREATE INDEX ix_probation_reviews_employee_id ON probation_reviews (employee_id);

CREATE TABLE probation_actions (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	action_type VARCHAR(30) NOT NULL, 
	effective_date DATE NOT NULL, 
	extended_until DATE, 
	remarks TEXT, 
	letter_generated BOOLEAN, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_probation_actions_organization_id ON probation_actions (organization_id);

CREATE INDEX ix_probation_actions_employee_id ON probation_actions (employee_id);

CREATE INDEX ix_probation_actions_action_type ON probation_actions (action_type);

CREATE INDEX ix_probation_actions_id ON probation_actions (id);

CREATE TABLE shift_roster_assignments (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	shift_id INTEGER NOT NULL, 
	work_date DATE NOT NULL, 
	status VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(shift_id) REFERENCES shifts (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_shift_roster_assignments_shift_id ON shift_roster_assignments (shift_id);

CREATE INDEX ix_shift_roster_assignments_id ON shift_roster_assignments (id);

CREATE INDEX ix_shift_roster_assignments_employee_id ON shift_roster_assignments (employee_id);

CREATE INDEX ix_shift_roster_assignments_work_date ON shift_roster_assignments (work_date);

CREATE TABLE shift_rosters (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	shift_id INTEGER NOT NULL, 
	roster_date DATE NOT NULL, 
	status VARCHAR(20), 
	assigned_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(shift_id) REFERENCES shifts (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_shift_rosters_shift_id ON shift_rosters (shift_id);

CREATE INDEX ix_shift_rosters_roster_date ON shift_rosters (roster_date);

CREATE INDEX ix_shift_rosters_organization_id ON shift_rosters (organization_id);

CREATE INDEX ix_shift_rosters_employee_id ON shift_rosters (employee_id);

CREATE INDEX idx_shift_roster_employee_date ON shift_rosters (employee_id, roster_date);

CREATE INDEX ix_shift_rosters_id ON shift_rosters (id);

CREATE INDEX ix_shift_rosters_status ON shift_rosters (status);

CREATE INDEX idx_shift_roster_org_date ON shift_rosters (organization_id, roster_date);

CREATE TABLE attendances (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	attendance_date DATE NOT NULL, 
	check_in TIMESTAMP WITH TIME ZONE, 
	check_out TIMESTAMP WITH TIME ZONE, 
	check_in_location VARCHAR(200), 
	check_out_location VARCHAR(200), 
	check_in_ip VARCHAR(50), 
	check_out_ip VARCHAR(50), 
	shift_id INTEGER, 
	total_hours NUMERIC(5, 2), 
	overtime_hours NUMERIC(5, 2), 
	late_minutes INTEGER, 
	early_exit_minutes INTEGER, 
	short_minutes INTEGER, 
	is_late BOOLEAN, 
	is_early_exit BOOLEAN, 
	is_short_hours BOOLEAN, 
	status VARCHAR(30), 
	source VARCHAR(30), 
	is_regularized BOOLEAN, 
	computed_at TIMESTAMP WITH TIME ZONE, 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(shift_id) REFERENCES shifts (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX idx_attendance_employee_date ON attendances (employee_id, attendance_date);

CREATE INDEX ix_attendances_id ON attendances (id);

CREATE TABLE attendance_punches (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	punch_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	punch_type VARCHAR(20) NOT NULL, 
	source VARCHAR(30), 
	device_id VARCHAR(120), 
	ip_address VARCHAR(50), 
	latitude NUMERIC(10, 7), 
	longitude NUMERIC(10, 7), 
	location_text VARCHAR(250), 
	raw_payload TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_attendance_punches_punch_time ON attendance_punches (punch_time);

CREATE INDEX ix_attendance_punches_employee_id ON attendance_punches (employee_id);

CREATE INDEX ix_attendance_punches_id ON attendance_punches (id);

CREATE TABLE overtime_requests (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	hours NUMERIC(4, 2) NOT NULL, 
	reason TEXT, 
	status VARCHAR(20), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_overtime_requests_id ON overtime_requests (id);

CREATE TABLE leave_balances (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	leave_type_id INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	allocated NUMERIC(5, 1), 
	used NUMERIC(5, 1), 
	pending NUMERIC(5, 1), 
	carried_forward NUMERIC(5, 1), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_leave_balances_id ON leave_balances (id);

CREATE TABLE leave_requests (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	leave_type_id INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	to_date DATE NOT NULL, 
	days_count NUMERIC(5, 1) NOT NULL, 
	is_half_day BOOLEAN, 
	half_day_period VARCHAR(20), 
	reason TEXT, 
	status VARCHAR(20), 
	applied_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	contact_during_leave VARCHAR(20), 
	handover_employee_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	deleted_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE CASCADE, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(handover_employee_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(deleted_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_leave_request_company_active_status ON leave_requests (company_id, deleted_at, status, employee_id);

CREATE INDEX ix_leave_requests_company_id ON leave_requests (company_id);

CREATE INDEX idx_leave_request_company_status ON leave_requests (company_id, status, employee_id);

CREATE INDEX idx_leave_request_active_status ON leave_requests (deleted_at, status, employee_id);

CREATE INDEX idx_leave_request_status ON leave_requests (status, employee_id);

CREATE INDEX ix_leave_requests_id ON leave_requests (id);

CREATE TABLE employee_salary_template_assignments (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	template_id INTEGER NOT NULL, 
	ctc NUMERIC(14, 2) NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(template_id) REFERENCES salary_templates (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_salary_template_assignments_employee_id ON employee_salary_template_assignments (employee_id);

CREATE INDEX ix_employee_salary_template_assignments_id ON employee_salary_template_assignments (id);

CREATE INDEX ix_employee_salary_template_assignments_template_id ON employee_salary_template_assignments (template_id);

CREATE INDEX ix_employee_salary_template_assignments_status ON employee_salary_template_assignments (status);

CREATE TABLE employee_tax_regime_elections (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	tax_regime_id INTEGER NOT NULL, 
	selected_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	locked_at TIMESTAMP WITH TIME ZONE, 
	locked_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tax_regime_id) REFERENCES tax_regimes (id) ON DELETE CASCADE, 
	FOREIGN KEY(locked_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_tax_regime_elections_tax_regime_id ON employee_tax_regime_elections (tax_regime_id);

CREATE INDEX ix_employee_tax_regime_elections_employee_id ON employee_tax_regime_elections (employee_id);

CREATE INDEX ix_employee_tax_regime_elections_financial_year ON employee_tax_regime_elections (financial_year);

CREATE INDEX ix_employee_tax_regime_elections_id ON employee_tax_regime_elections (id);

CREATE TABLE employee_tax_worksheets (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	tax_regime_id INTEGER, 
	gross_taxable_income NUMERIC(14, 2), 
	exemptions NUMERIC(14, 2), 
	deductions NUMERIC(14, 2), 
	previous_employment_income NUMERIC(14, 2), 
	previous_tds NUMERIC(14, 2), 
	projected_tax NUMERIC(14, 2), 
	monthly_tds NUMERIC(14, 2), 
	paid_tds NUMERIC(14, 2), 
	balance_tax NUMERIC(14, 2), 
	status VARCHAR(30), 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tax_regime_id) REFERENCES tax_regimes (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_tax_worksheets_id ON employee_tax_worksheets (id);

CREATE INDEX ix_employee_tax_worksheets_status ON employee_tax_worksheets (status);

CREATE INDEX ix_employee_tax_worksheets_tax_regime_id ON employee_tax_worksheets (tax_regime_id);

CREATE INDEX ix_employee_tax_worksheets_employee_id ON employee_tax_worksheets (employee_id);

CREATE INDEX ix_employee_tax_worksheets_financial_year ON employee_tax_worksheets (financial_year);

CREATE TABLE previous_employment_tax_details (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	employer_name VARCHAR(180) NOT NULL, 
	taxable_income NUMERIC(14, 2), 
	pf NUMERIC(14, 2), 
	professional_tax NUMERIC(14, 2), 
	tds_deducted NUMERIC(14, 2), 
	proof_url VARCHAR(500), 
	verified_status VARCHAR(30), 
	verified_by INTEGER, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(verified_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_previous_employment_tax_details_employee_id ON previous_employment_tax_details (employee_id);

CREATE INDEX ix_previous_employment_tax_details_financial_year ON previous_employment_tax_details (financial_year);

CREATE INDEX ix_previous_employment_tax_details_id ON previous_employment_tax_details (id);

CREATE INDEX ix_previous_employment_tax_details_verified_status ON previous_employment_tax_details (verified_status);

CREATE TABLE employee_statutory_profiles (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	uan VARCHAR(30), 
	pf_join_date DATE, 
	pf_exit_date DATE, 
	pf_applicable BOOLEAN, 
	pension_applicable BOOLEAN, 
	esi_ip_number VARCHAR(30), 
	esi_applicable BOOLEAN, 
	pt_state VARCHAR(100), 
	lwf_applicable BOOLEAN, 
	nominee_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_employee_statutory_profiles_employee_id ON employee_statutory_profiles (employee_id);

CREATE INDEX ix_employee_statutory_profiles_id ON employee_statutory_profiles (id);

CREATE TABLE payroll_attendance_inputs (
	id SERIAL NOT NULL, 
	period_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	working_days NUMERIC(6, 2), 
	payable_days NUMERIC(6, 2), 
	present_days NUMERIC(6, 2), 
	paid_leave_days NUMERIC(6, 2), 
	unpaid_leave_days NUMERIC(6, 2), 
	lop_days NUMERIC(6, 2), 
	holiday_days NUMERIC(6, 2), 
	weekly_off_days NUMERIC(6, 2), 
	ot_hours NUMERIC(8, 2), 
	source_status VARCHAR(30), 
	locked_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(period_id) REFERENCES payroll_periods (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_attendance_inputs_id ON payroll_attendance_inputs (id);

CREATE INDEX ix_payroll_attendance_inputs_source_status ON payroll_attendance_inputs (source_status);

CREATE INDEX ix_payroll_attendance_inputs_period_id ON payroll_attendance_inputs (period_id);

CREATE INDEX ix_payroll_attendance_inputs_employee_id ON payroll_attendance_inputs (employee_id);

CREATE TABLE lop_adjustments (
	id SERIAL NOT NULL, 
	period_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	adjustment_days NUMERIC(6, 2), 
	reason TEXT, 
	source VARCHAR(40), 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(period_id) REFERENCES payroll_periods (id) ON DELETE CASCADE
);

CREATE INDEX ix_lop_adjustments_source ON lop_adjustments (source);

CREATE INDEX ix_lop_adjustments_status ON lop_adjustments (status);

CREATE INDEX ix_lop_adjustments_period_id ON lop_adjustments (period_id);

CREATE INDEX ix_lop_adjustments_employee_id ON lop_adjustments (employee_id);

CREATE INDEX ix_lop_adjustments_id ON lop_adjustments (id);

CREATE TABLE employee_salaries (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	structure_id INTEGER, 
	ctc NUMERIC(14, 2) NOT NULL, 
	basic NUMERIC(12, 2), 
	hra NUMERIC(12, 2), 
	payroll_type VARCHAR(40), 
	wage_rate NUMERIC(12, 2), 
	default_units NUMERIC(12, 2), 
	unit_label VARCHAR(40), 
	commission_rate_percent NUMERIC(8, 4), 
	commission_base_amount NUMERIC(14, 2), 
	invoice_amount NUMERIC(14, 2), 
	effective_from DATE NOT NULL, 
	effective_date DATE, 
	effective_to DATE, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(structure_id) REFERENCES salary_structures (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_salaries_payroll_type ON employee_salaries (payroll_type);

CREATE INDEX idx_employee_salary_effective ON employee_salaries (employee_id, effective_from, effective_to);

CREATE INDEX ix_employee_salaries_id ON employee_salaries (id);

CREATE TABLE sensitive_salary_audit_logs (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	field_name VARCHAR(80), 
	old_value_masked VARCHAR(120), 
	new_value_masked VARCHAR(120), 
	actor_user_id INTEGER, 
	reason TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_sensitive_salary_audit_logs_employee_id ON sensitive_salary_audit_logs (employee_id);

CREATE INDEX ix_sensitive_salary_audit_logs_action ON sensitive_salary_audit_logs (action);

CREATE INDEX ix_sensitive_salary_audit_logs_id ON sensitive_salary_audit_logs (id);

CREATE TABLE payroll_records (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	working_days INTEGER, 
	present_days NUMERIC(5, 1), 
	lop_days NUMERIC(5, 1), 
	paid_days NUMERIC(5, 1), 
	basic NUMERIC(12, 2), 
	hra NUMERIC(12, 2), 
	da NUMERIC(12, 2), 
	ta NUMERIC(12, 2), 
	other_allowances NUMERIC(12, 2), 
	gross_salary NUMERIC(12, 2), 
	pf_employee NUMERIC(10, 2), 
	pf_employer NUMERIC(10, 2), 
	esi_employee NUMERIC(10, 2), 
	esi_employer NUMERIC(10, 2), 
	professional_tax NUMERIC(10, 2), 
	tds NUMERIC(10, 2), 
	other_deductions NUMERIC(10, 2), 
	total_deductions NUMERIC(12, 2), 
	reimbursements NUMERIC(10, 2), 
	bonus NUMERIC(10, 2), 
	net_salary NUMERIC(12, 2), 
	salary_currency VARCHAR(3), 
	exchange_rate NUMERIC(14, 6), 
	converted_currency VARCHAR(3), 
	payslip_pdf_url VARCHAR(500), 
	payslip_generated_at TIMESTAMP WITH TIME ZONE, 
	is_anomaly BOOLEAN, 
	anomaly_reason TEXT, 
	status VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_records_id ON payroll_records (id);

CREATE TABLE payroll_journal_lines (
	id SERIAL NOT NULL, 
	journal_entry_id INTEGER NOT NULL, 
	ledger_id INTEGER, 
	ledger_code VARCHAR(50), 
	ledger_name VARCHAR(150), 
	employee_id INTEGER, 
	component_name VARCHAR(120), 
	debit NUMERIC(14, 2), 
	credit NUMERIC(14, 2), 
	memo TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(ledger_id) REFERENCES accounting_ledgers (id) ON DELETE SET NULL, 
	FOREIGN KEY(journal_entry_id) REFERENCES payroll_journal_entries (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_journal_lines_journal_entry_id ON payroll_journal_lines (journal_entry_id);

CREATE INDEX ix_payroll_journal_lines_id ON payroll_journal_lines (id);

CREATE TABLE payroll_pre_run_checks (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	check_type VARCHAR(80) NOT NULL, 
	status VARCHAR(30), 
	severity VARCHAR(20), 
	message TEXT, 
	affected_employee_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(affected_employee_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_pre_run_checks_id ON payroll_pre_run_checks (id);

CREATE INDEX ix_payroll_pre_run_checks_payroll_run_id ON payroll_pre_run_checks (payroll_run_id);

CREATE INDEX ix_payroll_pre_run_checks_check_type ON payroll_pre_run_checks (check_type);

CREATE INDEX ix_payroll_pre_run_checks_status ON payroll_pre_run_checks (status);

CREATE TABLE payroll_manual_inputs (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	input_type VARCHAR(40) NOT NULL, 
	component_name VARCHAR(120) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	remarks TEXT, 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_manual_inputs_id ON payroll_manual_inputs (id);

CREATE INDEX ix_payroll_manual_inputs_input_type ON payroll_manual_inputs (input_type);

CREATE INDEX ix_payroll_manual_inputs_status ON payroll_manual_inputs (status);

CREATE INDEX ix_payroll_manual_inputs_payroll_run_id ON payroll_manual_inputs (payroll_run_id);

CREATE INDEX ix_payroll_manual_inputs_employee_id ON payroll_manual_inputs (employee_id);

CREATE TABLE employee_loans (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	loan_type VARCHAR(80), 
	principal_amount NUMERIC(14, 2) NOT NULL, 
	interest_rate NUMERIC(6, 2), 
	total_payable NUMERIC(14, 2) NOT NULL, 
	emi_amount NUMERIC(12, 2) NOT NULL, 
	start_month INTEGER NOT NULL, 
	start_year INTEGER NOT NULL, 
	tenure_months INTEGER NOT NULL, 
	balance_amount NUMERIC(14, 2) NOT NULL, 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_employee_loans_status ON employee_loans (status);

CREATE INDEX ix_employee_loans_id ON employee_loans (id);

CREATE INDEX ix_employee_loans_employee_id ON employee_loans (employee_id);

CREATE TABLE tax_declarations (
	id SERIAL NOT NULL, 
	cycle_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	section VARCHAR(40) NOT NULL, 
	declared_amount NUMERIC(12, 2), 
	approved_amount NUMERIC(12, 2), 
	description TEXT, 
	status VARCHAR(30), 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(cycle_id) REFERENCES tax_declaration_cycles (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_tax_declarations_cycle_id ON tax_declarations (cycle_id);

CREATE INDEX ix_tax_declarations_employee_id ON tax_declarations (employee_id);

CREATE INDEX ix_tax_declarations_id ON tax_declarations (id);

CREATE TABLE employee_tax_declarations (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	status VARCHAR(30), 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_tax_declarations_organization_id ON employee_tax_declarations (organization_id);

CREATE INDEX ix_employee_tax_declarations_financial_year ON employee_tax_declarations (financial_year);

CREATE INDEX ix_employee_tax_declarations_id ON employee_tax_declarations (id);

CREATE INDEX ix_employee_tax_declarations_status ON employee_tax_declarations (status);

CREATE INDEX ix_employee_tax_declarations_employee_id ON employee_tax_declarations (employee_id);

CREATE INDEX idx_employee_tax_declaration_employee_fy ON employee_tax_declarations (employee_id, financial_year);

CREATE TABLE salary_revision_batch_lines (
	id SERIAL NOT NULL, 
	batch_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	current_ctc NUMERIC(14, 2), 
	new_ctc NUMERIC(14, 2) NOT NULL, 
	structure_id INTEGER, 
	status VARCHAR(30), 
	error_message TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(structure_id) REFERENCES salary_structures (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(batch_id) REFERENCES salary_revision_batches (id) ON DELETE CASCADE
);

CREATE INDEX ix_salary_revision_batch_lines_employee_id ON salary_revision_batch_lines (employee_id);

CREATE INDEX ix_salary_revision_batch_lines_batch_id ON salary_revision_batch_lines (batch_id);

CREATE INDEX ix_salary_revision_batch_lines_status ON salary_revision_batch_lines (status);

CREATE INDEX ix_salary_revision_batch_lines_id ON salary_revision_batch_lines (id);

CREATE TABLE gratuity_accruals (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	payroll_run_id INTEGER, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	gratuity_wage NUMERIC(14, 2), 
	accrual_amount NUMERIC(14, 2), 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_gratuity_accruals_id ON gratuity_accruals (id);

CREATE INDEX ix_gratuity_accruals_employee_id ON gratuity_accruals (employee_id);

CREATE INDEX ix_gratuity_accruals_status ON gratuity_accruals (status);

CREATE INDEX ix_gratuity_accruals_payroll_run_id ON gratuity_accruals (payroll_run_id);

CREATE TABLE salary_certificates (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	purpose VARCHAR(160) NOT NULL, 
	period_from DATE, 
	period_to DATE, 
	annual_ctc NUMERIC(14, 2), 
	monthly_gross NUMERIC(14, 2), 
	file_url VARCHAR(500), 
	status VARCHAR(30), 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_salary_certificates_employee_id ON salary_certificates (employee_id);

CREATE INDEX ix_salary_certificates_status ON salary_certificates (status);

CREATE INDEX ix_salary_certificates_id ON salary_certificates (id);

CREATE TABLE payroll_bank_validations (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER, 
	employee_id INTEGER, 
	status VARCHAR(30), 
	error_code VARCHAR(80), 
	message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE SET NULL
);

CREATE INDEX ix_payroll_bank_validations_status ON payroll_bank_validations (status);

CREATE INDEX ix_payroll_bank_validations_employee_id ON payroll_bank_validations (employee_id);

CREATE INDEX ix_payroll_bank_validations_id ON payroll_bank_validations (id);

CREATE INDEX ix_payroll_bank_validations_payroll_run_id ON payroll_bank_validations (payroll_run_id);

CREATE TABLE tds_26as_reconciliations (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	company_tds NUMERIC(14, 2), 
	reported_26as_tds NUMERIC(14, 2), 
	difference NUMERIC(14, 2), 
	status VARCHAR(30), 
	remarks TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_tds_26as_reconciliations_status ON tds_26as_reconciliations (status);

CREATE INDEX ix_tds_26as_reconciliations_employee_id ON tds_26as_reconciliations (employee_id);

CREATE INDEX ix_tds_26as_reconciliations_financial_year ON tds_26as_reconciliations (financial_year);

CREATE INDEX ix_tds_26as_reconciliations_id ON tds_26as_reconciliations (id);

CREATE TABLE form_12ba_records (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	perquisites_json JSON, 
	total_perquisite_value NUMERIC(14, 2), 
	file_url VARCHAR(500), 
	status VARCHAR(30), 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_form_12ba_records_id ON form_12ba_records (id);

CREATE INDEX ix_form_12ba_records_status ON form_12ba_records (status);

CREATE INDEX ix_form_12ba_records_employee_id ON form_12ba_records (employee_id);

CREATE INDEX ix_form_12ba_records_financial_year ON form_12ba_records (financial_year);

CREATE TABLE projects (
	id SERIAL NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	client_name VARCHAR(200), 
	description TEXT, 
	start_date DATE, 
	end_date DATE, 
	status VARCHAR(30), 
	is_billable BOOLEAN, 
	owner_employee_id INTEGER, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_employee_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_projects_status ON projects (status);

CREATE UNIQUE INDEX ix_projects_code ON projects (code);

CREATE INDEX ix_projects_name ON projects (name);

CREATE INDEX ix_projects_id ON projects (id);

CREATE TABLE jobs (
	id SERIAL NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	code VARCHAR(50), 
	department_id INTEGER, 
	designation_id INTEGER, 
	branch_id INTEGER, 
	job_type VARCHAR(30), 
	location VARCHAR(150), 
	work_mode VARCHAR(30), 
	openings INTEGER, 
	min_experience NUMERIC(4, 1), 
	max_experience NUMERIC(4, 1), 
	min_salary NUMERIC(12, 2), 
	max_salary NUMERIC(12, 2), 
	description TEXT, 
	requirements TEXT, 
	benefits TEXT, 
	skills_required TEXT, 
	status VARCHAR(30), 
	posted_date DATE, 
	closing_date DATE, 
	is_published BOOLEAN, 
	hiring_manager_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(hiring_manager_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(designation_id) REFERENCES designations (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL
);

CREATE INDEX ix_jobs_id ON jobs (id);

CREATE TABLE employee_onboardings (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	template_id INTEGER, 
	start_date DATE, 
	target_completion_date DATE, 
	status VARCHAR(30), 
	completion_percentage INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	created_by INTEGER, 
	expected_completion_date DATE, 
	completed_date DATE, 
	welcome_email_sent BOOLEAN, 
	welcome_email_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(template_id) REFERENCES onboarding_templates (id) ON DELETE SET NULL
);

CREATE INDEX ix_employee_onboardings_status ON employee_onboardings (status);

CREATE INDEX ix_employee_onboardings_employee_id ON employee_onboardings (employee_id);

CREATE INDEX ix_employee_onboardings_id ON employee_onboardings (id);

CREATE TABLE policy_acknowledgements (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	policy_name VARCHAR(200) NOT NULL, 
	policy_document_url VARCHAR(500), 
	acknowledged_at TIMESTAMP WITH TIME ZONE, 
	ip_address VARCHAR(50), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_policy_acknowledgements_id ON policy_acknowledgements (id);

CREATE TABLE performance_goals (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	cycle_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	category VARCHAR(30), 
	goal_type VARCHAR(20), 
	weightage NUMERIC(5, 2), 
	target_value VARCHAR(500), 
	achieved_value VARCHAR(500), 
	target VARCHAR(500), 
	target_date DATE, 
	achievement TEXT, 
	self_rating NUMERIC(3, 1), 
	manager_rating NUMERIC(3, 1), 
	status VARCHAR(20), 
	set_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(set_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(cycle_id) REFERENCES appraisal_cycles (id) ON DELETE CASCADE
);

CREATE INDEX ix_performance_goals_id ON performance_goals (id);

CREATE TABLE performance_reviews (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	reviewer_id INTEGER NOT NULL, 
	cycle_id INTEGER NOT NULL, 
	review_type VARCHAR(20), 
	overall_rating NUMERIC(3, 1), 
	strengths TEXT, 
	improvements TEXT, 
	comments TEXT, 
	status VARCHAR(20), 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	acknowledged_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cycle_id) REFERENCES appraisal_cycles (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewer_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_performance_reviews_id ON performance_reviews (id);

CREATE TABLE calibration_participants (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	proposed_rating NUMERIC(3, 1), 
	final_rating NUMERIC(3, 1), 
	potential_rating NUMERIC(3, 1), 
	notes TEXT, 
	status VARCHAR(30), 
	updated_by INTEGER, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(session_id) REFERENCES calibration_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_calibration_participants_session_id ON calibration_participants (session_id);

CREATE INDEX ix_calibration_participants_employee_id ON calibration_participants (employee_id);

CREATE INDEX ix_calibration_participants_id ON calibration_participants (id);

CREATE INDEX ix_calibration_participants_status ON calibration_participants (status);

CREATE TABLE one_on_one_records (
	id SERIAL NOT NULL, 
	manager_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	meeting_date DATE NOT NULL, 
	talking_points_json JSON, 
	action_items_json JSON, 
	private_manager_notes TEXT, 
	employee_notes TEXT, 
	status VARCHAR(30), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(manager_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_one_on_one_records_id ON one_on_one_records (id);

CREATE INDEX ix_one_on_one_records_employee_id ON one_on_one_records (employee_id);

CREATE INDEX ix_one_on_one_records_manager_id ON one_on_one_records (manager_id);

CREATE INDEX ix_one_on_one_records_meeting_date ON one_on_one_records (meeting_date);

CREATE INDEX ix_one_on_one_records_status ON one_on_one_records (status);

CREATE TABLE feedback_360_requests (
	id SERIAL NOT NULL, 
	cycle_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	reviewer_id INTEGER NOT NULL, 
	relationship_type VARCHAR(30), 
	status VARCHAR(30), 
	due_date DATE, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	responses_json JSON, 
	overall_rating NUMERIC(3, 1), 
	comments TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(cycle_id) REFERENCES appraisal_cycles (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewer_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_feedback_360_requests_cycle_id ON feedback_360_requests (cycle_id);

CREATE INDEX ix_feedback_360_requests_employee_id ON feedback_360_requests (employee_id);

CREATE INDEX ix_feedback_360_requests_reviewer_id ON feedback_360_requests (reviewer_id);

CREATE INDEX ix_feedback_360_requests_id ON feedback_360_requests (id);

CREATE INDEX ix_feedback_360_requests_status ON feedback_360_requests (status);

CREATE TABLE employee_competency_assessments (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	competency_id INTEGER NOT NULL, 
	assessed_level INTEGER, 
	assessment_source VARCHAR(40), 
	assessed_by INTEGER, 
	assessed_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	evidence TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assessed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(competency_id) REFERENCES competencies (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_competency_assessments_employee_id ON employee_competency_assessments (employee_id);

CREATE INDEX ix_employee_competency_assessments_competency_id ON employee_competency_assessments (competency_id);

CREATE INDEX ix_employee_competency_assessments_id ON employee_competency_assessments (id);

CREATE TABLE critical_roles (
	id SERIAL NOT NULL, 
	role_name VARCHAR(160) NOT NULL, 
	department_id INTEGER, 
	designation_id INTEGER, 
	incumbent_employee_id INTEGER, 
	business_impact VARCHAR(40), 
	vacancy_risk VARCHAR(40), 
	notes TEXT, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(designation_id) REFERENCES designations (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
	FOREIGN KEY(incumbent_employee_id) REFERENCES employees (id) ON DELETE SET NULL
);

CREATE INDEX ix_critical_roles_designation_id ON critical_roles (designation_id);

CREATE INDEX ix_critical_roles_id ON critical_roles (id);

CREATE INDEX ix_critical_roles_department_id ON critical_roles (department_id);

CREATE INDEX ix_critical_roles_is_active ON critical_roles (is_active);

CREATE INDEX ix_critical_roles_incumbent_employee_id ON critical_roles (incumbent_employee_id);

CREATE TABLE merit_recommendations (
	id SERIAL NOT NULL, 
	compensation_cycle_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	current_ctc NUMERIC(14, 2), 
	recommended_ctc NUMERIC(14, 2), 
	increase_percent NUMERIC(5, 2), 
	performance_rating NUMERIC(3, 1), 
	compa_ratio NUMERIC(6, 3), 
	manager_remarks TEXT, 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(compensation_cycle_id) REFERENCES compensation_cycles (id) ON DELETE CASCADE
);

CREATE INDEX ix_merit_recommendations_employee_id ON merit_recommendations (employee_id);

CREATE INDEX ix_merit_recommendations_id ON merit_recommendations (id);

CREATE INDEX ix_merit_recommendations_status ON merit_recommendations (status);

CREATE INDEX ix_merit_recommendations_compensation_cycle_id ON merit_recommendations (compensation_cycle_id);

CREATE TABLE compensation_worksheet_rows (
	id SERIAL NOT NULL, 
	compensation_cycle_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	manager_employee_id INTEGER, 
	pay_band_id INTEGER, 
	current_ctc NUMERIC(14, 2), 
	pay_band_min NUMERIC(14, 2), 
	pay_band_midpoint NUMERIC(14, 2), 
	pay_band_max NUMERIC(14, 2), 
	proposed_merit_amount NUMERIC(14, 2), 
	proposed_merit_percent NUMERIC(6, 2), 
	proposed_ctc NUMERIC(14, 2), 
	budget_impact NUMERIC(14, 2), 
	approval_status VARCHAR(30), 
	performance_rating NUMERIC(3, 1), 
	manager_notes TEXT, 
	hr_notes TEXT, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(pay_band_id) REFERENCES pay_bands (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(manager_employee_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(compensation_cycle_id) REFERENCES compensation_cycles (id) ON DELETE CASCADE
);

CREATE INDEX ix_compensation_worksheet_rows_id ON compensation_worksheet_rows (id);

CREATE INDEX ix_compensation_worksheet_rows_employee_id ON compensation_worksheet_rows (employee_id);

CREATE INDEX ix_compensation_worksheet_rows_compensation_cycle_id ON compensation_worksheet_rows (compensation_cycle_id);

CREATE INDEX ix_compensation_worksheet_rows_manager_employee_id ON compensation_worksheet_rows (manager_employee_id);

CREATE INDEX ix_compensation_worksheet_rows_approval_status ON compensation_worksheet_rows (approval_status);

CREATE TABLE helpdesk_tickets (
	id SERIAL NOT NULL, 
	ticket_number VARCHAR(30) NOT NULL, 
	employee_id INTEGER NOT NULL, 
	category_id INTEGER, 
	subject VARCHAR(300) NOT NULL, 
	description TEXT NOT NULL, 
	priority VARCHAR(20), 
	status VARCHAR(20), 
	assigned_to INTEGER, 
	first_response_due_at TIMESTAMP WITH TIME ZONE, 
	resolution_due_at TIMESTAMP WITH TIME ZONE, 
	escalated_at TIMESTAMP WITH TIME ZONE, 
	escalated_to INTEGER, 
	escalation_reason TEXT, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	satisfaction_rating INTEGER, 
	attachment_url VARCHAR(500), 
	ai_suggested_reply TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(escalated_to) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(category_id) REFERENCES helpdesk_categories (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_helpdesk_tickets_id ON helpdesk_tickets (id);

CREATE UNIQUE INDEX ix_helpdesk_tickets_ticket_number ON helpdesk_tickets (ticket_number);

CREATE TABLE generated_documents (
	id SERIAL NOT NULL, 
	template_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	document_type VARCHAR(100), 
	document_name VARCHAR(200), 
	file_url VARCHAR(500), 
	generated_by INTEGER, 
	is_signed BOOLEAN, 
	signed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(template_id) REFERENCES document_templates (id) ON DELETE SET NULL
);

CREATE INDEX ix_generated_documents_id ON generated_documents (id);

CREATE TABLE employee_certificates (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	certificate_type VARCHAR(100) NOT NULL, 
	title VARCHAR(250) NOT NULL, 
	issuing_entity VARCHAR(250), 
	issuing_entity_type VARCHAR(50), 
	class_or_grade VARCHAR(80), 
	course_or_program VARCHAR(200), 
	certificate_number VARCHAR(120), 
	issue_date DATE, 
	expiry_date DATE, 
	file_url VARCHAR(500) NOT NULL, 
	original_filename VARCHAR(255), 
	content_type VARCHAR(120), 
	file_size_bytes INTEGER, 
	verification_status VARCHAR(30), 
	verified_by_user_id INTEGER, 
	verifier_name VARCHAR(150), 
	verifier_company VARCHAR(200), 
	verifier_designation VARCHAR(150), 
	verifier_contact VARCHAR(150), 
	verified_at TIMESTAMP WITH TIME ZONE, 
	verification_notes TEXT, 
	uploaded_by INTEGER, 
	uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(verified_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_certificates_employee_id ON employee_certificates (employee_id);

CREATE INDEX ix_employee_certificates_verification_status ON employee_certificates (verification_status);

CREATE INDEX ix_employee_certificates_category ON employee_certificates (category);

CREATE INDEX ix_employee_certificates_id ON employee_certificates (id);

CREATE TABLE certificate_import_export_batches (
	id SERIAL NOT NULL, 
	operation_type VARCHAR(20) NOT NULL, 
	employee_id INTEGER, 
	source_file_url VARCHAR(500), 
	output_file_url VARCHAR(500), 
	error_report_url VARCHAR(500), 
	original_filename VARCHAR(255), 
	status VARCHAR(30), 
	total_records INTEGER, 
	success_count INTEGER, 
	failure_count INTEGER, 
	requested_by INTEGER, 
	requested_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL
);

CREATE INDEX ix_certificate_import_export_batches_status ON certificate_import_export_batches (status);

CREATE INDEX ix_certificate_import_export_batches_operation_type ON certificate_import_export_batches (operation_type);

CREATE INDEX ix_certificate_import_export_batches_employee_id ON certificate_import_export_batches (employee_id);

CREATE INDEX ix_certificate_import_export_batches_id ON certificate_import_export_batches (id);

CREATE TABLE asset_assignments (
	id SERIAL NOT NULL, 
	asset_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	assigned_date DATE NOT NULL, 
	returned_date DATE, 
	assigned_by INTEGER, 
	condition_at_assignment VARCHAR(30), 
	condition_at_return VARCHAR(30), 
	remarks TEXT, 
	acknowledgement_signed BOOLEAN, 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(asset_id) REFERENCES assets (id) ON DELETE CASCADE
);

CREATE INDEX ix_asset_assignments_id ON asset_assignments (id);

CREATE TABLE exit_records (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	exit_type VARCHAR(30), 
	resignation_date DATE, 
	last_working_date DATE, 
	notice_period_days INTEGER, 
	notice_waived BOOLEAN, 
	reason TEXT, 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	final_settlement_amount NUMERIC(14, 2), 
	final_settlement_date DATE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (employee_id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_exit_records_id ON exit_records (id);

CREATE TABLE consent_records (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	consent_type VARCHAR(80) NOT NULL, 
	status VARCHAR(30), 
	purpose TEXT, 
	channel VARCHAR(50), 
	evidence_url VARCHAR(500), 
	captured_by INTEGER, 
	captured_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(captured_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_consent_records_consent_type ON consent_records (consent_type);

CREATE INDEX ix_consent_records_status ON consent_records (status);

CREATE INDEX ix_consent_records_id ON consent_records (id);

CREATE INDEX ix_consent_records_employee_id ON consent_records (employee_id);

CREATE TABLE data_privacy_requests (
	id SERIAL NOT NULL, 
	employee_id INTEGER, 
	request_type VARCHAR(60) NOT NULL, 
	status VARCHAR(30), 
	requested_by_email VARCHAR(150), 
	due_date TIMESTAMP WITH TIME ZONE, 
	resolution_notes TEXT, 
	processing_result_json JSON, 
	assigned_to INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	processed_at TIMESTAMP WITH TIME ZONE, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL
);

CREATE INDEX ix_data_privacy_requests_request_type ON data_privacy_requests (request_type);

CREATE INDEX ix_data_privacy_requests_status ON data_privacy_requests (status);

CREATE INDEX ix_data_privacy_requests_employee_id ON data_privacy_requests (employee_id);

CREATE INDEX ix_data_privacy_requests_id ON data_privacy_requests (id);

CREATE TABLE manufacturing_safety_incidents (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	employee_id INTEGER, 
	incident_date DATE NOT NULL, 
	location VARCHAR(150), 
	incident_type VARCHAR(80) NOT NULL, 
	severity VARCHAR(30), 
	description TEXT, 
	lost_time_hours NUMERIC(8, 2), 
	corrective_action TEXT, 
	status VARCHAR(30), 
	reported_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(reported_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_manufacturing_safety_incidents_id ON manufacturing_safety_incidents (id);

CREATE INDEX ix_manufacturing_safety_incidents_company_id ON manufacturing_safety_incidents (company_id);

CREATE INDEX ix_manufacturing_safety_incidents_severity ON manufacturing_safety_incidents (severity);

CREATE INDEX ix_manufacturing_safety_incidents_incident_type ON manufacturing_safety_incidents (incident_type);

CREATE INDEX ix_manufacturing_safety_incidents_status ON manufacturing_safety_incidents (status);

CREATE INDEX ix_manufacturing_safety_incidents_employee_id ON manufacturing_safety_incidents (employee_id);

CREATE INDEX ix_manufacturing_safety_incidents_incident_date ON manufacturing_safety_incidents (incident_date);

CREATE TABLE manufacturing_ppe_issuances (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	ppe_item VARCHAR(120) NOT NULL, 
	issued_on DATE NOT NULL, 
	quantity INTEGER, 
	expiry_date DATE, 
	condition VARCHAR(40), 
	acknowledgement_status VARCHAR(30), 
	issued_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(issued_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_manufacturing_ppe_issuances_id ON manufacturing_ppe_issuances (id);

CREATE INDEX ix_manufacturing_ppe_issuances_acknowledgement_status ON manufacturing_ppe_issuances (acknowledgement_status);

CREATE INDEX ix_manufacturing_ppe_issuances_ppe_item ON manufacturing_ppe_issuances (ppe_item);

CREATE INDEX ix_manufacturing_ppe_issuances_issued_on ON manufacturing_ppe_issuances (issued_on);

CREATE INDEX ix_manufacturing_ppe_issuances_company_id ON manufacturing_ppe_issuances (company_id);

CREATE INDEX ix_manufacturing_ppe_issuances_employee_id ON manufacturing_ppe_issuances (employee_id);

CREATE TABLE manufacturing_medical_fitness_records (
	id SERIAL NOT NULL, 
	company_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	exam_date DATE NOT NULL, 
	fitness_status VARCHAR(40) NOT NULL, 
	valid_until DATE, 
	restrictions TEXT, 
	provider_name VARCHAR(150), 
	document_url VARCHAR(500), 
	recorded_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_manufacturing_medical_fitness_records_id ON manufacturing_medical_fitness_records (id);

CREATE INDEX ix_manufacturing_medical_fitness_records_valid_until ON manufacturing_medical_fitness_records (valid_until);

CREATE INDEX ix_manufacturing_medical_fitness_records_exam_date ON manufacturing_medical_fitness_records (exam_date);

CREATE INDEX ix_manufacturing_medical_fitness_records_fitness_status ON manufacturing_medical_fitness_records (fitness_status);

CREATE INDEX ix_manufacturing_medical_fitness_records_company_id ON manufacturing_medical_fitness_records (company_id);

CREATE INDEX ix_manufacturing_medical_fitness_records_employee_id ON manufacturing_medical_fitness_records (employee_id);

CREATE TABLE learning_assignments (
	id SERIAL NOT NULL, 
	course_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	assigned_by INTEGER, 
	due_date DATE, 
	status VARCHAR(30), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	score NUMERIC(5, 2), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(course_id) REFERENCES learning_courses (id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_learning_assignments_employee_id ON learning_assignments (employee_id);

CREATE INDEX ix_learning_assignments_id ON learning_assignments (id);

CREATE INDEX ix_learning_assignments_status ON learning_assignments (status);

CREATE INDEX ix_learning_assignments_course_id ON learning_assignments (course_id);

CREATE TABLE learning_certifications (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	course_id INTEGER, 
	title VARCHAR(220) NOT NULL, 
	certificate_url VARCHAR(500), 
	issued_on DATE, 
	expires_on DATE, 
	status VARCHAR(30), 
	renewal_required BOOLEAN, 
	renewal_due_on DATE, 
	reminder_days INTEGER, 
	renewal_status VARCHAR(30), 
	last_reminder_at TIMESTAMP WITH TIME ZONE, 
	verified_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(verified_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(course_id) REFERENCES learning_courses (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_learning_certifications_id ON learning_certifications (id);

CREATE INDEX ix_learning_certifications_expires_on ON learning_certifications (expires_on);

CREATE INDEX ix_learning_certifications_employee_id ON learning_certifications (employee_id);

CREATE INDEX ix_learning_certifications_renewal_due_on ON learning_certifications (renewal_due_on);

CREATE INDEX ix_learning_certifications_status ON learning_certifications (status);

CREATE INDEX ix_learning_certifications_renewal_status ON learning_certifications (renewal_status);

CREATE TABLE announcement_acknowledgements (
	id SERIAL NOT NULL, 
	announcement_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	acknowledged_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(announcement_id) REFERENCES announcements (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_announcement_acknowledgements_id ON announcement_acknowledgements (id);

CREATE INDEX ix_announcement_acknowledgements_employee_id ON announcement_acknowledgements (employee_id);

CREATE INDEX ix_announcement_acknowledgements_announcement_id ON announcement_acknowledgements (announcement_id);

CREATE TABLE engagement_survey_responses (
	id SERIAL NOT NULL, 
	survey_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	score NUMERIC(5, 2), 
	comments TEXT, 
	submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(survey_id) REFERENCES engagement_surveys (id) ON DELETE CASCADE
);

CREATE INDEX ix_engagement_survey_responses_survey_id ON engagement_survey_responses (survey_id);

CREATE INDEX ix_engagement_survey_responses_id ON engagement_survey_responses (id);

CREATE INDEX ix_engagement_survey_responses_employee_id ON engagement_survey_responses (employee_id);

CREATE TABLE recognitions (
	id SERIAL NOT NULL, 
	from_employee_id INTEGER, 
	to_employee_id INTEGER NOT NULL, 
	title VARCHAR(180) NOT NULL, 
	message TEXT, 
	badge VARCHAR(80), 
	points INTEGER, 
	is_public BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(to_employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(from_employee_id) REFERENCES employees (id) ON DELETE SET NULL
);

CREATE INDEX ix_recognitions_to_employee_id ON recognitions (to_employee_id);

CREATE INDEX ix_recognitions_id ON recognitions (id);

CREATE TABLE whatsapp_ess_sessions (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	phone_number VARCHAR(30) NOT NULL, 
	status VARCHAR(30), 
	last_intent VARCHAR(80), 
	last_message_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_whatsapp_ess_sessions_employee_id ON whatsapp_ess_sessions (employee_id);

CREATE INDEX ix_whatsapp_ess_sessions_id ON whatsapp_ess_sessions (id);

CREATE INDEX ix_whatsapp_ess_sessions_phone_number ON whatsapp_ess_sessions (phone_number);

CREATE INDEX ix_whatsapp_ess_sessions_status ON whatsapp_ess_sessions (status);

CREATE TABLE whatsapp_ess_opt_ins (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	phone_number VARCHAR(30) NOT NULL, 
	status VARCHAR(30), 
	source VARCHAR(80), 
	consent_text TEXT, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_whatsapp_ess_opt_ins_employee_id ON whatsapp_ess_opt_ins (employee_id);

CREATE INDEX ix_whatsapp_ess_opt_ins_phone_number ON whatsapp_ess_opt_ins (phone_number);

CREATE INDEX ix_whatsapp_ess_opt_ins_id ON whatsapp_ess_opt_ins (id);

CREATE INDEX ix_whatsapp_ess_opt_ins_status ON whatsapp_ess_opt_ins (status);

CREATE TABLE form16_documents (
	id SERIAL NOT NULL, 
	legal_entity_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	part_a_url VARCHAR(500), 
	part_b_url VARCHAR(500), 
	combined_pdf_url VARCHAR(500), 
	taxable_income NUMERIC(14, 2), 
	tax_deducted NUMERIC(14, 2), 
	status VARCHAR(30), 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE, 
	published_at TIMESTAMP WITH TIME ZONE, 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(legal_entity_id) REFERENCES payroll_legal_entities (id) ON DELETE CASCADE, 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_form16_documents_financial_year ON form16_documents (financial_year);

CREATE INDEX ix_form16_documents_status ON form16_documents (status);

CREATE INDEX ix_form16_documents_id ON form16_documents (id);

CREATE INDEX ix_form16_documents_employee_id ON form16_documents (employee_id);

CREATE INDEX ix_form16_documents_legal_entity_id ON form16_documents (legal_entity_id);

CREATE TABLE form16_records (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	part_a_file_path VARCHAR(500), 
	part_b_file_path VARCHAR(500), 
	combined_file_path VARCHAR(500), 
	status VARCHAR(30), 
	taxable_income NUMERIC(14, 2), 
	tax_deducted NUMERIC(14, 2), 
	generated_by INTEGER, 
	generated_at TIMESTAMP WITH TIME ZONE, 
	published_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(organization_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX ix_form16_records_organization_id ON form16_records (organization_id);

CREATE INDEX ix_form16_records_financial_year ON form16_records (financial_year);

CREATE INDEX ix_form16_records_status ON form16_records (status);

CREATE INDEX ix_form16_records_employee_id ON form16_records (employee_id);

CREATE INDEX ix_form16_records_id ON form16_records (id);

CREATE TABLE employee_benefit_enrollments (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	benefit_plan_id INTEGER NOT NULL, 
	coverage_level VARCHAR(80), 
	enrolled_amount NUMERIC(12, 2), 
	employee_contribution NUMERIC(12, 2), 
	employer_contribution NUMERIC(12, 2), 
	start_date DATE NOT NULL, 
	end_date DATE, 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(benefit_plan_id) REFERENCES benefit_plans (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_benefit_enrollments_id ON employee_benefit_enrollments (id);

CREATE INDEX ix_employee_benefit_enrollments_status ON employee_benefit_enrollments (status);

CREATE INDEX ix_employee_benefit_enrollments_benefit_plan_id ON employee_benefit_enrollments (benefit_plan_id);

CREATE INDEX ix_employee_benefit_enrollments_employee_id ON employee_benefit_enrollments (employee_id);

CREATE TABLE employee_flexi_benefit_allocations (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	policy_id INTEGER NOT NULL, 
	financial_year VARCHAR(20) NOT NULL, 
	allocated_amount NUMERIC(12, 2) NOT NULL, 
	claimed_amount NUMERIC(12, 2), 
	taxable_fallback_amount NUMERIC(12, 2), 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(policy_id) REFERENCES flexi_benefit_policies (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_flexi_benefit_allocations_financial_year ON employee_flexi_benefit_allocations (financial_year);

CREATE INDEX ix_employee_flexi_benefit_allocations_id ON employee_flexi_benefit_allocations (id);

CREATE INDEX ix_employee_flexi_benefit_allocations_employee_id ON employee_flexi_benefit_allocations (employee_id);

CREATE INDEX ix_employee_flexi_benefit_allocations_status ON employee_flexi_benefit_allocations (status);

CREATE INDEX ix_employee_flexi_benefit_allocations_policy_id ON employee_flexi_benefit_allocations (policy_id);

CREATE TABLE esop_grants (
	id SERIAL NOT NULL, 
	esop_plan_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	grant_date DATE NOT NULL, 
	granted_units NUMERIC(14, 2) NOT NULL, 
	vested_units NUMERIC(14, 2), 
	exercised_units NUMERIC(14, 2), 
	forfeited_units NUMERIC(14, 2), 
	status VARCHAR(30), 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(esop_plan_id) REFERENCES esop_plans (id) ON DELETE CASCADE
);

CREATE INDEX ix_esop_grants_esop_plan_id ON esop_grants (esop_plan_id);

CREATE INDEX ix_esop_grants_id ON esop_grants (id);

CREATE INDEX ix_esop_grants_employee_id ON esop_grants (employee_id);

CREATE INDEX ix_esop_grants_status ON esop_grants (status);

CREATE TABLE crm_quotation_items (
	id SERIAL NOT NULL, 
	quotation_id INTEGER NOT NULL, 
	quote_id INTEGER, 
	item_type VARCHAR(30), 
	product_id INTEGER, 
	service_id INTEGER, 
	name VARCHAR(180) NOT NULL, 
	description TEXT, 
	quantity NUMERIC(12, 2), 
	unit_price NUMERIC(14, 2), 
	discount_type VARCHAR(20), 
	discount_value NUMERIC(14, 2), 
	discount_amount NUMERIC(12, 2), 
	tax_rate NUMERIC(5, 2), 
	line_total NUMERIC(14, 2), 
	total_amount NUMERIC(12, 2), 
	estimated_cost NUMERIC(14, 2), 
	margin_amount NUMERIC(14, 2), 
	margin_percentage NUMERIC(6, 2), 
	billing_type VARCHAR(30), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(service_id) REFERENCES crm_services (id) ON DELETE SET NULL, 
	FOREIGN KEY(quote_id) REFERENCES crm_quotations (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES crm_products (id) ON DELETE SET NULL, 
	FOREIGN KEY(quotation_id) REFERENCES crm_quotations (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_quotation_items_quote_id ON crm_quotation_items (quote_id);

CREATE INDEX ix_crm_quotation_items_item_type ON crm_quotation_items (item_type);

CREATE INDEX ix_crm_quotation_items_quotation_id ON crm_quotation_items (quotation_id);

CREATE INDEX ix_crm_quotation_items_product_id ON crm_quotation_items (product_id);

CREATE INDEX ix_crm_quotation_items_id ON crm_quotation_items (id);

CREATE INDEX ix_crm_quotation_items_service_id ON crm_quotation_items (service_id);

CREATE TABLE crm_quote_versions (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	quote_id INTEGER NOT NULL, 
	version_number INTEGER NOT NULL, 
	snapshot_json JSON, 
	created_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_by_user_id INTEGER, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(quote_id) REFERENCES crm_quotations (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_quote_versions_organization_id ON crm_quote_versions (organization_id);

CREATE INDEX ix_crm_quote_versions_version_number ON crm_quote_versions (version_number);

CREATE INDEX ix_crm_quote_versions_id ON crm_quote_versions (id);

CREATE INDEX ix_crm_quote_versions_quote_id ON crm_quote_versions (quote_id);

CREATE TABLE crm_quote_approvals (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	quote_id INTEGER NOT NULL, 
	status VARCHAR(30), 
	reason TEXT, 
	submitted_by INTEGER, 
	approver_user_id INTEGER, 
	approved_by INTEGER, 
	comments TEXT, 
	submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	decided_at TIMESTAMP WITH TIME ZONE, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(approver_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(quote_id) REFERENCES crm_quotations (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_quote_approvals_status ON crm_quote_approvals (status);

CREATE INDEX ix_crm_quote_approvals_organization_id ON crm_quote_approvals (organization_id);

CREATE INDEX ix_crm_quote_approvals_quote_id ON crm_quote_approvals (quote_id);

CREATE INDEX ix_crm_quote_approvals_id ON crm_quote_approvals (id);

CREATE TABLE crm_quote_srm_conversion_logs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	quote_id INTEGER NOT NULL, 
	deal_id INTEGER, 
	srm_sales_order_id INTEGER, 
	srm_contract_id INTEGER, 
	srm_engagement_id INTEGER, 
	srm_billing_plan_id INTEGER, 
	idempotency_key VARCHAR(160), 
	status VARCHAR(40), 
	message TEXT, 
	payload_json JSON, 
	created_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_by_user_id INTEGER, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(quote_id) REFERENCES crm_quotations (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_quote_srm_conversion_logs_organization_id ON crm_quote_srm_conversion_logs (organization_id);

CREATE INDEX ix_crm_quote_srm_conversion_logs_quote_id ON crm_quote_srm_conversion_logs (quote_id);

CREATE INDEX ix_crm_quote_srm_conversion_logs_srm_engagement_id ON crm_quote_srm_conversion_logs (srm_engagement_id);

CREATE INDEX ix_crm_quote_srm_conversion_logs_status ON crm_quote_srm_conversion_logs (status);

CREATE INDEX ix_crm_quote_srm_conversion_logs_id ON crm_quote_srm_conversion_logs (id);

CREATE INDEX ix_crm_quote_srm_conversion_logs_srm_contract_id ON crm_quote_srm_conversion_logs (srm_contract_id);

CREATE INDEX ix_crm_quote_srm_conversion_logs_srm_billing_plan_id ON crm_quote_srm_conversion_logs (srm_billing_plan_id);

CREATE INDEX ix_crm_quote_srm_conversion_logs_deal_id ON crm_quote_srm_conversion_logs (deal_id);

CREATE INDEX ix_crm_quote_srm_conversion_logs_srm_sales_order_id ON crm_quote_srm_conversion_logs (srm_sales_order_id);

CREATE INDEX ix_crm_quote_srm_conversion_logs_idempotency_key ON crm_quote_srm_conversion_logs (idempotency_key);

CREATE TABLE crm_activities (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	assigned_team_id INTEGER, 
	entity_type VARCHAR(40), 
	entity_id INTEGER, 
	lead_id INTEGER, 
	contact_id INTEGER, 
	company_id INTEGER, 
	deal_id INTEGER, 
	activity_type VARCHAR(40) NOT NULL, 
	title VARCHAR(220), 
	subject VARCHAR(180) NOT NULL, 
	body TEXT, 
	description TEXT, 
	metadata_json JSON, 
	status VARCHAR(30), 
	priority VARCHAR(30), 
	activity_date TIMESTAMP WITH TIME ZONE, 
	due_date TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	outcome TEXT, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_activities_branch_id ON crm_activities (branch_id);

CREATE INDEX ix_crm_activities_department_id ON crm_activities (department_id);

CREATE INDEX ix_crm_activities_lead_id ON crm_activities (lead_id);

CREATE INDEX ix_crm_activities_deal_id ON crm_activities (deal_id);

CREATE INDEX ix_crm_activities_priority ON crm_activities (priority);

CREATE INDEX ix_crm_activities_organization_id ON crm_activities (organization_id);

CREATE INDEX ix_crm_activities_owner_user_id ON crm_activities (owner_user_id);

CREATE INDEX ix_crm_activities_entity_type ON crm_activities (entity_type);

CREATE INDEX ix_crm_activities_contact_id ON crm_activities (contact_id);

CREATE INDEX ix_crm_activities_activity_type ON crm_activities (activity_type);

CREATE INDEX ix_crm_activities_activity_date ON crm_activities (activity_date);

CREATE INDEX ix_crm_activities_id ON crm_activities (id);

CREATE INDEX ix_crm_activities_assigned_team_id ON crm_activities (assigned_team_id);

CREATE INDEX ix_crm_activities_entity_id ON crm_activities (entity_id);

CREATE INDEX ix_crm_activities_company_id ON crm_activities (company_id);

CREATE INDEX ix_crm_activities_status ON crm_activities (status);

CREATE INDEX ix_crm_activities_due_date ON crm_activities (due_date);

CREATE TABLE crm_tasks (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	branch_id INTEGER, 
	department_id INTEGER, 
	assigned_team_id INTEGER, 
	lead_id INTEGER, 
	contact_id INTEGER, 
	company_id INTEGER, 
	deal_id INTEGER, 
	title VARCHAR(220) NOT NULL, 
	description TEXT, 
	status VARCHAR(30), 
	priority VARCHAR(30), 
	due_date TIMESTAMP WITH TIME ZONE, 
	reminder_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_tasks_branch_id ON crm_tasks (branch_id);

CREATE INDEX ix_crm_tasks_department_id ON crm_tasks (department_id);

CREATE INDEX ix_crm_tasks_company_id ON crm_tasks (company_id);

CREATE INDEX ix_crm_tasks_priority ON crm_tasks (priority);

CREATE INDEX ix_crm_tasks_organization_id ON crm_tasks (organization_id);

CREATE INDEX ix_crm_tasks_owner_user_id ON crm_tasks (owner_user_id);

CREATE INDEX ix_crm_tasks_lead_id ON crm_tasks (lead_id);

CREATE INDEX ix_crm_tasks_deal_id ON crm_tasks (deal_id);

CREATE INDEX ix_crm_tasks_due_date ON crm_tasks (due_date);

CREATE INDEX ix_crm_tasks_id ON crm_tasks (id);

CREATE INDEX ix_crm_tasks_assigned_team_id ON crm_tasks (assigned_team_id);

CREATE INDEX ix_crm_tasks_contact_id ON crm_tasks (contact_id);

CREATE INDEX ix_crm_tasks_status ON crm_tasks (status);

CREATE TABLE crm_notes (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	author_user_id INTEGER, 
	lead_id INTEGER, 
	contact_id INTEGER, 
	company_id INTEGER, 
	deal_id INTEGER, 
	ticket_id INTEGER, 
	body TEXT NOT NULL, 
	is_pinned BOOLEAN, 
	is_internal BOOLEAN, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(ticket_id) REFERENCES crm_tickets (id) ON DELETE CASCADE, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_notes_author_user_id ON crm_notes (author_user_id);

CREATE INDEX ix_crm_notes_contact_id ON crm_notes (contact_id);

CREATE INDEX ix_crm_notes_ticket_id ON crm_notes (ticket_id);

CREATE INDEX ix_crm_notes_id ON crm_notes (id);

CREATE INDEX ix_crm_notes_organization_id ON crm_notes (organization_id);

CREATE INDEX ix_crm_notes_company_id ON crm_notes (company_id);

CREATE INDEX ix_crm_notes_is_internal ON crm_notes (is_internal);

CREATE INDEX ix_crm_notes_lead_id ON crm_notes (lead_id);

CREATE INDEX ix_crm_notes_deal_id ON crm_notes (deal_id);

CREATE TABLE crm_lead_conversion_logs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	lead_id INTEGER NOT NULL, 
	converted_account_id INTEGER, 
	converted_contact_id INTEGER, 
	converted_deal_id INTEGER, 
	converted_by_user_id INTEGER, 
	conversion_status VARCHAR(40), 
	notes TEXT, 
	metadata_json JSON, 
	converted_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(converted_deal_id) REFERENCES crm_deals (id) ON DELETE SET NULL, 
	FOREIGN KEY(converted_account_id) REFERENCES crm_companies (id) ON DELETE SET NULL, 
	FOREIGN KEY(converted_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(converted_contact_id) REFERENCES crm_contacts (id) ON DELETE SET NULL, 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_lead_conversion_logs_converted_account_id ON crm_lead_conversion_logs (converted_account_id);

CREATE INDEX ix_crm_lead_conversion_logs_converted_contact_id ON crm_lead_conversion_logs (converted_contact_id);

CREATE INDEX ix_crm_lead_conversion_logs_conversion_status ON crm_lead_conversion_logs (conversion_status);

CREATE INDEX ix_crm_lead_conversion_logs_organization_id ON crm_lead_conversion_logs (organization_id);

CREATE INDEX ix_crm_lead_conversion_logs_lead_id ON crm_lead_conversion_logs (lead_id);

CREATE INDEX ix_crm_lead_conversion_logs_converted_by_user_id ON crm_lead_conversion_logs (converted_by_user_id);

CREATE INDEX ix_crm_lead_conversion_logs_converted_at ON crm_lead_conversion_logs (converted_at);

CREATE INDEX ix_crm_lead_conversion_logs_id ON crm_lead_conversion_logs (id);

CREATE INDEX ix_crm_lead_conversion_logs_converted_deal_id ON crm_lead_conversion_logs (converted_deal_id);

CREATE TABLE crm_email_logs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	entity_type VARCHAR(40), 
	entity_id INTEGER, 
	subject VARCHAR(220) NOT NULL, 
	body TEXT, 
	from_email VARCHAR(150), 
	to_email VARCHAR(150) NOT NULL, 
	cc VARCHAR(500), 
	bcc VARCHAR(500), 
	direction VARCHAR(20), 
	status VARCHAR(30), 
	provider_message_id VARCHAR(160), 
	failure_reason TEXT, 
	sent_by_user_id INTEGER, 
	lead_id INTEGER, 
	contact_id INTEGER, 
	company_id INTEGER, 
	deal_id INTEGER, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(sent_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_email_logs_lead_id ON crm_email_logs (lead_id);

CREATE INDEX ix_crm_email_logs_deal_id ON crm_email_logs (deal_id);

CREATE INDEX ix_crm_email_logs_organization_id ON crm_email_logs (organization_id);

CREATE INDEX ix_crm_email_logs_owner_user_id ON crm_email_logs (owner_user_id);

CREATE INDEX ix_crm_email_logs_direction ON crm_email_logs (direction);

CREATE INDEX ix_crm_email_logs_contact_id ON crm_email_logs (contact_id);

CREATE INDEX ix_crm_email_logs_id ON crm_email_logs (id);

CREATE INDEX ix_crm_email_logs_to_email ON crm_email_logs (to_email);

CREATE INDEX ix_crm_email_logs_status ON crm_email_logs (status);

CREATE INDEX ix_crm_email_logs_company_id ON crm_email_logs (company_id);

CREATE INDEX ix_crm_email_logs_entity_type ON crm_email_logs (entity_type);

CREATE INDEX ix_crm_email_logs_entity_id ON crm_email_logs (entity_id);

CREATE TABLE crm_call_logs (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	direction VARCHAR(20) NOT NULL, 
	phone_number VARCHAR(40) NOT NULL, 
	duration_seconds INTEGER, 
	outcome VARCHAR(160), 
	notes TEXT, 
	lead_id INTEGER, 
	contact_id INTEGER, 
	company_id INTEGER, 
	deal_id INTEGER, 
	call_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_call_logs_direction ON crm_call_logs (direction);

CREATE INDEX ix_crm_call_logs_contact_id ON crm_call_logs (contact_id);

CREATE INDEX ix_crm_call_logs_call_time ON crm_call_logs (call_time);

CREATE INDEX ix_crm_call_logs_organization_id ON crm_call_logs (organization_id);

CREATE INDEX ix_crm_call_logs_owner_user_id ON crm_call_logs (owner_user_id);

CREATE INDEX ix_crm_call_logs_company_id ON crm_call_logs (company_id);

CREATE INDEX ix_crm_call_logs_id ON crm_call_logs (id);

CREATE INDEX ix_crm_call_logs_lead_id ON crm_call_logs (lead_id);

CREATE INDEX ix_crm_call_logs_deal_id ON crm_call_logs (deal_id);

CREATE TABLE crm_meetings (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	owner_user_id INTEGER, 
	title VARCHAR(180) NOT NULL, 
	description TEXT, 
	location VARCHAR(240), 
	start_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	end_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	outcome TEXT, 
	status VARCHAR(30), 
	external_provider VARCHAR(40), 
	external_event_id VARCHAR(180), 
	sync_status VARCHAR(30), 
	last_synced_at TIMESTAMP WITH TIME ZONE, 
	lead_id INTEGER, 
	contact_id INTEGER, 
	company_id INTEGER, 
	deal_id INTEGER, 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_crm_meetings_organization_id ON crm_meetings (organization_id);

CREATE INDEX ix_crm_meetings_external_provider ON crm_meetings (external_provider);

CREATE INDEX ix_crm_meetings_sync_status ON crm_meetings (sync_status);

CREATE INDEX ix_crm_meetings_company_id ON crm_meetings (company_id);

CREATE INDEX ix_crm_meetings_start_time ON crm_meetings (start_time);

CREATE INDEX ix_crm_meetings_status ON crm_meetings (status);

CREATE INDEX ix_crm_meetings_lead_id ON crm_meetings (lead_id);

CREATE INDEX ix_crm_meetings_deal_id ON crm_meetings (deal_id);

CREATE INDEX ix_crm_meetings_id ON crm_meetings (id);

CREATE INDEX ix_crm_meetings_owner_user_id ON crm_meetings (owner_user_id);

CREATE INDEX ix_crm_meetings_external_event_id ON crm_meetings (external_event_id);

CREATE INDEX ix_crm_meetings_contact_id ON crm_meetings (contact_id);

CREATE TABLE crm_campaign_leads (
	id SERIAL NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	lead_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE, 
	CONSTRAINT uq_crm_campaign_lead UNIQUE (campaign_id, lead_id), 
	FOREIGN KEY(campaign_id) REFERENCES crm_campaigns (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_campaign_leads_campaign_id ON crm_campaign_leads (campaign_id);

CREATE INDEX ix_crm_campaign_leads_lead_id ON crm_campaign_leads (lead_id);

CREATE INDEX ix_crm_campaign_leads_id ON crm_campaign_leads (id);

CREATE TABLE crm_file_assets (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	uploaded_by_user_id INTEGER, 
	lead_id INTEGER, 
	contact_id INTEGER, 
	company_id INTEGER, 
	deal_id INTEGER, 
	ticket_id INTEGER, 
	file_name VARCHAR(240) NOT NULL, 
	original_name VARCHAR(240) NOT NULL, 
	mime_type VARCHAR(120), 
	size_bytes INTEGER, 
	storage_path VARCHAR(500) NOT NULL, 
	visibility VARCHAR(40), 
	created_by_user_id INTEGER, 
	updated_by_user_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES crm_companies (id) ON DELETE CASCADE, 
	FOREIGN KEY(lead_id) REFERENCES crm_leads (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(deal_id) REFERENCES crm_deals (id) ON DELETE CASCADE, 
	FOREIGN KEY(contact_id) REFERENCES crm_contacts (id) ON DELETE CASCADE, 
	FOREIGN KEY(uploaded_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(ticket_id) REFERENCES crm_tickets (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_file_assets_lead_id ON crm_file_assets (lead_id);

CREATE INDEX ix_crm_file_assets_company_id ON crm_file_assets (company_id);

CREATE INDEX ix_crm_file_assets_visibility ON crm_file_assets (visibility);

CREATE INDEX ix_crm_file_assets_organization_id ON crm_file_assets (organization_id);

CREATE INDEX ix_crm_file_assets_uploaded_by_user_id ON crm_file_assets (uploaded_by_user_id);

CREATE INDEX ix_crm_file_assets_deal_id ON crm_file_assets (deal_id);

CREATE INDEX ix_crm_file_assets_id ON crm_file_assets (id);

CREATE INDEX ix_crm_file_assets_contact_id ON crm_file_assets (contact_id);

CREATE INDEX ix_crm_file_assets_ticket_id ON crm_file_assets (ticket_id);

CREATE TABLE pms_tasks (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	board_id INTEGER, 
	column_id INTEGER, 
	milestone_id INTEGER, 
	sprint_id INTEGER, 
	epic_id INTEGER, 
	component_id INTEGER, 
	release_id INTEGER, 
	parent_task_id INTEGER, 
	assignee_user_id INTEGER, 
	reporter_user_id INTEGER, 
	title VARCHAR(220) NOT NULL, 
	description TEXT, 
	task_key VARCHAR(30) NOT NULL, 
	work_type VARCHAR(40), 
	epic_key VARCHAR(60), 
	initiative VARCHAR(160), 
	component VARCHAR(120), 
	severity VARCHAR(20), 
	environment VARCHAR(80), 
	affected_version VARCHAR(80), 
	fix_version VARCHAR(80), 
	release_name VARCHAR(120), 
	status VARCHAR(50), 
	priority VARCHAR(30), 
	start_date DATE, 
	due_date DATE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	estimated_hours NUMERIC(8, 2), 
	actual_hours NUMERIC(8, 2), 
	original_estimate_hours NUMERIC(8, 2), 
	remaining_estimate_hours NUMERIC(8, 2), 
	story_points INTEGER, 
	rank INTEGER, 
	security_level VARCHAR(40), 
	development_branch VARCHAR(200), 
	development_commits INTEGER, 
	development_prs INTEGER, 
	development_deployments INTEGER, 
	development_build VARCHAR(30), 
	position INTEGER, 
	is_client_visible BOOLEAN, 
	is_blocking BOOLEAN, 
	recurrence_rule VARCHAR(40), 
	recurrence_interval INTEGER, 
	recurrence_until DATE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES pms_components (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(sprint_id) REFERENCES pms_sprints (id) ON DELETE SET NULL, 
	FOREIGN KEY(column_id) REFERENCES pms_board_columns (id) ON DELETE SET NULL, 
	CONSTRAINT uq_pms_task_project_key UNIQUE (project_id, task_key), 
	FOREIGN KEY(assignee_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(release_id) REFERENCES pms_releases (id) ON DELETE SET NULL, 
	FOREIGN KEY(board_id) REFERENCES pms_boards (id) ON DELETE SET NULL, 
	FOREIGN KEY(epic_id) REFERENCES pms_epics (id) ON DELETE SET NULL, 
	FOREIGN KEY(milestone_id) REFERENCES pms_milestones (id) ON DELETE SET NULL, 
	FOREIGN KEY(reporter_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(parent_task_id) REFERENCES pms_tasks (id) ON DELETE SET NULL
);

CREATE INDEX ix_pms_tasks_reporter_user_id ON pms_tasks (reporter_user_id);

CREATE INDEX ix_pms_tasks_security_level ON pms_tasks (security_level);

CREATE INDEX ix_pms_tasks_task_key ON pms_tasks (task_key);

CREATE INDEX ix_pms_tasks_development_build ON pms_tasks (development_build);

CREATE INDEX ix_pms_tasks_work_type ON pms_tasks (work_type);

CREATE INDEX ix_pms_tasks_is_blocking ON pms_tasks (is_blocking);

CREATE INDEX ix_pms_tasks_board_id ON pms_tasks (board_id);

CREATE INDEX ix_pms_tasks_epic_key ON pms_tasks (epic_key);

CREATE INDEX ix_pms_tasks_recurrence_rule ON pms_tasks (recurrence_rule);

CREATE INDEX ix_pms_tasks_column_id ON pms_tasks (column_id);

CREATE INDEX ix_pms_tasks_component ON pms_tasks (component);

CREATE INDEX ix_pms_tasks_sprint_id ON pms_tasks (sprint_id);

CREATE INDEX ix_pms_tasks_severity ON pms_tasks (severity);

CREATE INDEX ix_pms_tasks_milestone_id ON pms_tasks (milestone_id);

CREATE INDEX ix_pms_tasks_fix_version ON pms_tasks (fix_version);

CREATE INDEX ix_pms_tasks_id ON pms_tasks (id);

CREATE INDEX ix_pms_tasks_epic_id ON pms_tasks (epic_id);

CREATE INDEX ix_pms_tasks_release_name ON pms_tasks (release_name);

CREATE INDEX ix_pms_tasks_project_id ON pms_tasks (project_id);

CREATE INDEX ix_pms_tasks_component_id ON pms_tasks (component_id);

CREATE INDEX ix_pms_tasks_status ON pms_tasks (status);

CREATE INDEX ix_pms_tasks_release_id ON pms_tasks (release_id);

CREATE INDEX ix_pms_tasks_priority ON pms_tasks (priority);

CREATE INDEX ix_pms_tasks_parent_task_id ON pms_tasks (parent_task_id);

CREATE INDEX ix_pms_tasks_due_date ON pms_tasks (due_date);

CREATE INDEX ix_pms_tasks_assignee_user_id ON pms_tasks (assignee_user_id);

CREATE INDEX ix_pms_tasks_rank ON pms_tasks (rank);

CREATE TABLE srm_invoices (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	invoice_number VARCHAR(80) NOT NULL, 
	invoice_draft_id INTEGER, 
	sales_order_id INTEGER, 
	engagement_id INTEGER, 
	customer_id INTEGER, 
	status VARCHAR(40), 
	issue_date DATE, 
	due_date DATE, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	currency VARCHAR(10), 
	subtotal NUMERIC(14, 2), 
	discount_amount NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	total_amount NUMERIC(14, 2), 
	paid_amount NUMERIC(14, 2), 
	balance_amount NUMERIC(14, 2), 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_draft_id) REFERENCES srm_invoice_drafts (id) ON DELETE SET NULL, 
	CONSTRAINT uq_srm_invoice_org_number UNIQUE (organization_id, invoice_number), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(sales_order_id) REFERENCES srm_sales_orders (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_invoices_sales_order_id ON srm_invoices (sales_order_id);

CREATE INDEX ix_srm_invoices_issue_date ON srm_invoices (issue_date);

CREATE INDEX ix_srm_invoices_created_at ON srm_invoices (created_at);

CREATE INDEX ix_srm_invoices_invoice_draft_id ON srm_invoices (invoice_draft_id);

CREATE INDEX ix_srm_invoices_invoice_number ON srm_invoices (invoice_number);

CREATE INDEX ix_srm_invoices_customer_id ON srm_invoices (customer_id);

CREATE INDEX ix_srm_invoices_due_date ON srm_invoices (due_date);

CREATE INDEX ix_srm_invoices_id ON srm_invoices (id);

CREATE INDEX ix_srm_invoices_engagement_id ON srm_invoices (engagement_id);

CREATE INDEX ix_srm_invoices_status ON srm_invoices (status);

CREATE INDEX ix_srm_invoices_organization_id ON srm_invoices (organization_id);

CREATE TABLE attendance_punch_proofs (
	id SERIAL NOT NULL, 
	punch_id INTEGER NOT NULL, 
	proof_type VARCHAR(30) NOT NULL, 
	proof_url VARCHAR(500), 
	latitude NUMERIC(10, 7), 
	longitude NUMERIC(10, 7), 
	qr_code VARCHAR(120), 
	validation_status VARCHAR(30), 
	validation_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(punch_id) REFERENCES attendance_punches (id) ON DELETE CASCADE
);

CREATE INDEX ix_attendance_punch_proofs_id ON attendance_punch_proofs (id);

CREATE INDEX ix_attendance_punch_proofs_validation_status ON attendance_punch_proofs (validation_status);

CREATE INDEX ix_attendance_punch_proofs_punch_id ON attendance_punch_proofs (punch_id);

CREATE TABLE attendance_regularizations (
	id SERIAL NOT NULL, 
	attendance_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	requested_check_in TIMESTAMP WITH TIME ZONE, 
	requested_check_out TIMESTAMP WITH TIME ZONE, 
	reason TEXT NOT NULL, 
	status VARCHAR(20), 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(attendance_id) REFERENCES attendances (id) ON DELETE CASCADE
);

CREATE INDEX ix_attendance_regularizations_id ON attendance_regularizations (id);

CREATE TABLE leave_balance_ledger (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	leave_type_id INTEGER NOT NULL, 
	leave_balance_id INTEGER, 
	leave_request_id INTEGER, 
	year INTEGER NOT NULL, 
	transaction_type VARCHAR(40) NOT NULL, 
	amount NUMERIC(5, 1) NOT NULL, 
	balance_after NUMERIC(5, 1) NOT NULL, 
	reason TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(leave_request_id) REFERENCES leave_requests (id) ON DELETE SET NULL, 
	FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(leave_balance_id) REFERENCES leave_balances (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_leave_balance_ledger_year ON leave_balance_ledger (year);

CREATE INDEX ix_leave_balance_ledger_leave_type_id ON leave_balance_ledger (leave_type_id);

CREATE INDEX ix_leave_balance_ledger_id ON leave_balance_ledger (id);

CREATE INDEX ix_leave_balance_ledger_employee_id ON leave_balance_ledger (employee_id);

CREATE TABLE employee_salary_component_overrides (
	id SERIAL NOT NULL, 
	assignment_id INTEGER NOT NULL, 
	component_id INTEGER NOT NULL, 
	override_type VARCHAR(30) NOT NULL, 
	amount NUMERIC(12, 2), 
	percentage NUMERIC(8, 4), 
	formula_expression TEXT, 
	reason TEXT, 
	approved_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES salary_components (id) ON DELETE CASCADE, 
	FOREIGN KEY(assignment_id) REFERENCES employee_salary_template_assignments (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_employee_salary_component_overrides_assignment_id ON employee_salary_component_overrides (assignment_id);

CREATE INDEX ix_employee_salary_component_overrides_id ON employee_salary_component_overrides (id);

CREATE INDEX ix_employee_salary_component_overrides_component_id ON employee_salary_component_overrides (component_id);

CREATE TABLE employee_tax_worksheet_lines (
	id SERIAL NOT NULL, 
	worksheet_id INTEGER NOT NULL, 
	line_type VARCHAR(50) NOT NULL, 
	section_code VARCHAR(40), 
	description TEXT, 
	amount NUMERIC(14, 2), 
	taxable_amount NUMERIC(14, 2), 
	tax_saving_amount NUMERIC(14, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(worksheet_id) REFERENCES employee_tax_worksheets (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_tax_worksheet_lines_id ON employee_tax_worksheet_lines (id);

CREATE INDEX ix_employee_tax_worksheet_lines_worksheet_id ON employee_tax_worksheet_lines (worksheet_id);

CREATE TABLE payroll_statutory_contribution_lines (
	id SERIAL NOT NULL, 
	payroll_record_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	component VARCHAR(40) NOT NULL, 
	wage_base NUMERIC(12, 2), 
	employee_amount NUMERIC(12, 2), 
	employer_amount NUMERIC(12, 2), 
	admin_charge NUMERIC(12, 2), 
	edli_amount NUMERIC(12, 2), 
	rule_id INTEGER, 
	rule_type VARCHAR(40), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_statutory_contribution_lines_employee_id ON payroll_statutory_contribution_lines (employee_id);

CREATE INDEX ix_payroll_statutory_contribution_lines_payroll_record_id ON payroll_statutory_contribution_lines (payroll_record_id);

CREATE INDEX ix_payroll_statutory_contribution_lines_component ON payroll_statutory_contribution_lines (component);

CREATE INDEX ix_payroll_statutory_contribution_lines_id ON payroll_statutory_contribution_lines (id);

CREATE TABLE overtime_pay_lines (
	id SERIAL NOT NULL, 
	period_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	policy_id INTEGER, 
	payroll_record_id INTEGER, 
	approved_overtime_request_id INTEGER, 
	ot_date DATE, 
	hours NUMERIC(8, 2), 
	multiplier NUMERIC(6, 2), 
	hourly_rate NUMERIC(12, 2), 
	amount NUMERIC(12, 2), 
	source VARCHAR(40), 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_overtime_request_id) REFERENCES overtime_requests (id) ON DELETE SET NULL, 
	FOREIGN KEY(policy_id) REFERENCES overtime_policies (id) ON DELETE SET NULL, 
	FOREIGN KEY(period_id) REFERENCES payroll_periods (id) ON DELETE CASCADE
);

CREATE INDEX ix_overtime_pay_lines_employee_id ON overtime_pay_lines (employee_id);

CREATE INDEX ix_overtime_pay_lines_status ON overtime_pay_lines (status);

CREATE INDEX ix_overtime_pay_lines_id ON overtime_pay_lines (id);

CREATE INDEX ix_overtime_pay_lines_policy_id ON overtime_pay_lines (policy_id);

CREATE INDEX ix_overtime_pay_lines_period_id ON overtime_pay_lines (period_id);

CREATE INDEX ix_overtime_pay_lines_payroll_record_id ON overtime_pay_lines (payroll_record_id);

CREATE TABLE leave_encashment_lines (
	id SERIAL NOT NULL, 
	period_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	policy_id INTEGER, 
	leave_type_id INTEGER, 
	payroll_record_id INTEGER, 
	days NUMERIC(6, 2), 
	rate_per_day NUMERIC(12, 2), 
	amount NUMERIC(12, 2), 
	tax_treatment VARCHAR(50), 
	status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(policy_id) REFERENCES leave_encashment_policies (id) ON DELETE SET NULL, 
	FOREIGN KEY(period_id) REFERENCES payroll_periods (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_leave_encashment_lines_period_id ON leave_encashment_lines (period_id);

CREATE INDEX ix_leave_encashment_lines_status ON leave_encashment_lines (status);

CREATE INDEX ix_leave_encashment_lines_policy_id ON leave_encashment_lines (policy_id);

CREATE INDEX ix_leave_encashment_lines_payroll_record_id ON leave_encashment_lines (payroll_record_id);

CREATE INDEX ix_leave_encashment_lines_id ON leave_encashment_lines (id);

CREATE INDEX ix_leave_encashment_lines_employee_id ON leave_encashment_lines (employee_id);

CREATE TABLE payroll_lwp_entries (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	payroll_month VARCHAR(7) NOT NULL, 
	lwp_days NUMERIC(6, 2), 
	source VARCHAR(40), 
	amount_deducted NUMERIC(12, 2), 
	payroll_run_id INTEGER, 
	payroll_attendance_input_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_attendance_input_id) REFERENCES payroll_attendance_inputs (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_lwp_entries_payroll_month ON payroll_lwp_entries (payroll_month);

CREATE INDEX ix_payroll_lwp_entries_source ON payroll_lwp_entries (source);

CREATE INDEX ix_payroll_lwp_entries_id ON payroll_lwp_entries (id);

CREATE INDEX ix_payroll_lwp_entries_employee_id ON payroll_lwp_entries (employee_id);

CREATE INDEX ix_payroll_lwp_entries_payroll_attendance_input_id ON payroll_lwp_entries (payroll_attendance_input_id);

CREATE INDEX ix_payroll_lwp_entries_organization_id ON payroll_lwp_entries (organization_id);

CREATE INDEX ix_payroll_lwp_entries_payroll_run_id ON payroll_lwp_entries (payroll_run_id);

CREATE TABLE salary_revision_requests (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	current_salary_id INTEGER, 
	proposed_structure_id INTEGER, 
	current_ctc NUMERIC(14, 2), 
	proposed_ctc NUMERIC(14, 2) NOT NULL, 
	effective_from DATE NOT NULL, 
	reason TEXT, 
	status VARCHAR(30), 
	requested_by INTEGER, 
	checked_by INTEGER, 
	checked_at TIMESTAMP WITH TIME ZONE, 
	checker_remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(checked_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(proposed_structure_id) REFERENCES salary_structures (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(current_salary_id) REFERENCES employee_salaries (id) ON DELETE SET NULL
);

CREATE INDEX ix_salary_revision_requests_status ON salary_revision_requests (status);

CREATE INDEX ix_salary_revision_requests_id ON salary_revision_requests (id);

CREATE INDEX ix_salary_revision_requests_employee_id ON salary_revision_requests (employee_id);

CREATE TABLE payroll_components (
	id SERIAL NOT NULL, 
	record_id INTEGER NOT NULL, 
	component_id INTEGER, 
	component_name VARCHAR(100), 
	component_type VARCHAR(50), 
	amount NUMERIC(12, 2), 
	source_type VARCHAR(50), 
	source_id INTEGER, 
	taxable_amount NUMERIC(12, 2), 
	exempt_amount NUMERIC(12, 2), 
	wage_base_flags JSON, 
	calculation_order INTEGER, 
	formula_trace_json JSON, 
	is_manual BOOLEAN, 
	is_arrear BOOLEAN, 
	is_reversal BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES salary_components (id) ON DELETE SET NULL, 
	FOREIGN KEY(record_id) REFERENCES payroll_records (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_components_id ON payroll_components (id);

CREATE TABLE payroll_run_employees (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	payroll_record_id INTEGER, 
	status VARCHAR(30), 
	hold_reason TEXT, 
	skip_reason TEXT, 
	input_status VARCHAR(30), 
	calculation_status VARCHAR(30), 
	approval_status VARCHAR(30), 
	gross_salary NUMERIC(12, 2), 
	total_deductions NUMERIC(12, 2), 
	net_salary NUMERIC(12, 2), 
	variance_status VARCHAR(30), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_run_employees_employee_id ON payroll_run_employees (employee_id);

CREATE INDEX ix_payroll_run_employees_calculation_status ON payroll_run_employees (calculation_status);

CREATE INDEX ix_payroll_run_employees_payroll_record_id ON payroll_run_employees (payroll_record_id);

CREATE INDEX ix_payroll_run_employees_status ON payroll_run_employees (status);

CREATE INDEX ix_payroll_run_employees_approval_status ON payroll_run_employees (approval_status);

CREATE INDEX ix_payroll_run_employees_payroll_run_id ON payroll_run_employees (payroll_run_id);

CREATE INDEX ix_payroll_run_employees_id ON payroll_run_employees (id);

CREATE INDEX ix_payroll_run_employees_input_status ON payroll_run_employees (input_status);

CREATE TABLE payroll_arrear_lines (
	id SERIAL NOT NULL, 
	arrear_run_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	component_id INTEGER, 
	component_name VARCHAR(120) NOT NULL, 
	arrear_type VARCHAR(50), 
	from_date DATE, 
	to_date DATE, 
	amount NUMERIC(12, 2), 
	reason TEXT, 
	status VARCHAR(30), 
	payroll_record_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(component_id) REFERENCES salary_components (id) ON DELETE SET NULL, 
	FOREIGN KEY(arrear_run_id) REFERENCES payroll_arrear_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_arrear_lines_id ON payroll_arrear_lines (id);

CREATE INDEX ix_payroll_arrear_lines_status ON payroll_arrear_lines (status);

CREATE INDEX ix_payroll_arrear_lines_arrear_run_id ON payroll_arrear_lines (arrear_run_id);

CREATE INDEX ix_payroll_arrear_lines_employee_id ON payroll_arrear_lines (employee_id);

CREATE TABLE payroll_payment_lines (
	id SERIAL NOT NULL, 
	batch_id INTEGER NOT NULL, 
	payroll_record_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	net_amount NUMERIC(14, 2), 
	bank_account VARCHAR(120), 
	ifsc VARCHAR(20), 
	payment_status VARCHAR(30), 
	utr_number VARCHAR(120), 
	failure_reason TEXT, 
	paid_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(batch_id) REFERENCES payroll_payment_batches (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_payment_lines_payroll_record_id ON payroll_payment_lines (payroll_record_id);

CREATE INDEX ix_payroll_payment_lines_employee_id ON payroll_payment_lines (employee_id);

CREATE INDEX ix_payroll_payment_lines_utr_number ON payroll_payment_lines (utr_number);

CREATE INDEX ix_payroll_payment_lines_id ON payroll_payment_lines (id);

CREATE INDEX ix_payroll_payment_lines_batch_id ON payroll_payment_lines (batch_id);

CREATE INDEX ix_payroll_payment_lines_payment_status ON payroll_payment_lines (payment_status);

CREATE TABLE payroll_variance_items (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	previous_payroll_record_id INTEGER, 
	current_gross NUMERIC(12, 2), 
	previous_gross NUMERIC(12, 2), 
	gross_delta NUMERIC(12, 2), 
	gross_delta_percent NUMERIC(8, 2), 
	current_net NUMERIC(12, 2), 
	previous_net NUMERIC(12, 2), 
	net_delta NUMERIC(12, 2), 
	net_delta_percent NUMERIC(8, 2), 
	severity VARCHAR(20), 
	reason TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(previous_payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_variance_items_employee_id ON payroll_variance_items (employee_id);

CREATE INDEX ix_payroll_variance_items_id ON payroll_variance_items (id);

CREATE INDEX ix_payroll_variance_items_payroll_run_id ON payroll_variance_items (payroll_run_id);

CREATE TABLE reimbursements (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	category VARCHAR(100), 
	amount NUMERIC(12, 2) NOT NULL, 
	date DATE, 
	description TEXT, 
	receipt_url VARCHAR(500), 
	status VARCHAR(20), 
	approved_by INTEGER, 
	payroll_record_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_reimbursements_id ON reimbursements (id);

CREATE TABLE employee_loan_installments (
	id SERIAL NOT NULL, 
	loan_id INTEGER NOT NULL, 
	installment_number INTEGER NOT NULL, 
	due_month INTEGER NOT NULL, 
	due_year INTEGER NOT NULL, 
	due_amount NUMERIC(12, 2) NOT NULL, 
	principal_component NUMERIC(12, 2), 
	interest_component NUMERIC(12, 2), 
	status VARCHAR(30), 
	payroll_record_id INTEGER, 
	paid_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(loan_id) REFERENCES employee_loans (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_loan_installments_status ON employee_loan_installments (status);

CREATE INDEX ix_employee_loan_installments_loan_id ON employee_loan_installments (loan_id);

CREATE INDEX ix_employee_loan_installments_id ON employee_loan_installments (id);

CREATE TABLE employee_loan_ledgers (
	id SERIAL NOT NULL, 
	loan_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	amount NUMERIC(12, 2), 
	balance_after NUMERIC(14, 2), 
	payroll_record_id INTEGER, 
	actor_user_id INTEGER, 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(loan_id) REFERENCES employee_loans (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_loan_ledgers_id ON employee_loan_ledgers (id);

CREATE INDEX ix_employee_loan_ledgers_employee_id ON employee_loan_ledgers (employee_id);

CREATE INDEX ix_employee_loan_ledgers_action ON employee_loan_ledgers (action);

CREATE INDEX ix_employee_loan_ledgers_loan_id ON employee_loan_ledgers (loan_id);

CREATE TABLE full_final_settlements (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	exit_record_id INTEGER, 
	settlement_date DATE NOT NULL, 
	last_working_date DATE, 
	status VARCHAR(30), 
	unpaid_salary NUMERIC(12, 2), 
	leave_encashment_amount NUMERIC(12, 2), 
	notice_recovery_amount NUMERIC(12, 2), 
	gratuity_amount NUMERIC(12, 2), 
	loan_recovery_amount NUMERIC(12, 2), 
	reimbursement_payable NUMERIC(12, 2), 
	bonus_payable NUMERIC(12, 2), 
	other_earnings NUMERIC(12, 2), 
	other_deductions NUMERIC(12, 2), 
	other_payables NUMERIC(12, 2), 
	other_recoveries NUMERIC(12, 2), 
	net_payable NUMERIC(14, 2), 
	settlement_letter_url VARCHAR(500), 
	prepared_by INTEGER, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	rejected_by INTEGER, 
	rejected_at TIMESTAMP WITH TIME ZONE, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	paid_at TIMESTAMP WITH TIME ZONE, 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(rejected_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(prepared_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(exit_record_id) REFERENCES exit_records (id) ON DELETE SET NULL
);

CREATE INDEX ix_full_final_settlements_id ON full_final_settlements (id);

CREATE INDEX ix_full_final_settlements_status ON full_final_settlements (status);

CREATE INDEX ix_full_final_settlements_organization_id ON full_final_settlements (organization_id);

CREATE INDEX ix_full_final_settlements_employee_id ON full_final_settlements (employee_id);

CREATE TABLE tax_declaration_proofs (
	id SERIAL NOT NULL, 
	declaration_id INTEGER NOT NULL, 
	file_url VARCHAR(500) NOT NULL, 
	original_filename VARCHAR(255), 
	status VARCHAR(30), 
	verified_by INTEGER, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	verification_remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(verified_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(declaration_id) REFERENCES tax_declarations (id) ON DELETE CASCADE
);

CREATE INDEX ix_tax_declaration_proofs_declaration_id ON tax_declaration_proofs (declaration_id);

CREATE INDEX ix_tax_declaration_proofs_id ON tax_declaration_proofs (id);

CREATE TABLE employee_tax_declaration_items (
	id SERIAL NOT NULL, 
	declaration_id INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	declared_amount NUMERIC(14, 2), 
	approved_amount NUMERIC(14, 2), 
	remarks TEXT, 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES tax_declaration_categories (id) ON DELETE CASCADE, 
	FOREIGN KEY(declaration_id) REFERENCES employee_tax_declarations (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_tax_declaration_items_id ON employee_tax_declaration_items (id);

CREATE INDEX ix_employee_tax_declaration_items_category_id ON employee_tax_declaration_items (category_id);

CREATE INDEX ix_employee_tax_declaration_items_status ON employee_tax_declaration_items (status);

CREATE INDEX ix_employee_tax_declaration_items_declaration_id ON employee_tax_declaration_items (declaration_id);

CREATE TABLE payslip_delivery_logs (
	id SERIAL NOT NULL, 
	payroll_record_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	channel VARCHAR(30) NOT NULL, 
	destination VARCHAR(180), 
	status VARCHAR(30), 
	message TEXT, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_payslip_delivery_logs_employee_id ON payslip_delivery_logs (employee_id);

CREATE INDEX ix_payslip_delivery_logs_status ON payslip_delivery_logs (status);

CREATE INDEX ix_payslip_delivery_logs_id ON payslip_delivery_logs (id);

CREATE INDEX ix_payslip_delivery_logs_channel ON payslip_delivery_logs (channel);

CREATE INDEX ix_payslip_delivery_logs_payroll_record_id ON payslip_delivery_logs (payroll_record_id);

CREATE TABLE payslip_queries (
	id SERIAL NOT NULL, 
	payroll_record_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	subject VARCHAR(180) NOT NULL, 
	description TEXT NOT NULL, 
	status VARCHAR(30), 
	priority VARCHAR(20), 
	resolution TEXT, 
	created_by INTEGER, 
	assigned_to INTEGER, 
	resolved_by INTEGER, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(resolved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE CASCADE
);

CREATE INDEX ix_payslip_queries_employee_id ON payslip_queries (employee_id);

CREATE INDEX ix_payslip_queries_payroll_record_id ON payslip_queries (payroll_record_id);

CREATE INDEX ix_payslip_queries_id ON payslip_queries (id);

CREATE INDEX ix_payslip_queries_status ON payslip_queries (status);

CREATE INDEX ix_payslip_queries_priority ON payslip_queries (priority);

CREATE TABLE salary_advances (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	requested_amount NUMERIC(14, 2) NOT NULL, 
	approved_amount NUMERIC(14, 2), 
	reason TEXT, 
	requested_deduction_month INTEGER NOT NULL, 
	requested_deduction_year INTEGER NOT NULL, 
	status VARCHAR(30), 
	payroll_record_id INTEGER, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL
);

CREATE INDEX ix_salary_advances_status ON salary_advances (status);

CREATE INDEX ix_salary_advances_id ON salary_advances (id);

CREATE INDEX ix_salary_advances_employee_id ON salary_advances (employee_id);

CREATE INDEX ix_salary_advances_payroll_record_id ON salary_advances (payroll_record_id);

CREATE TABLE timesheets (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	status VARCHAR(30), 
	total_hours NUMERIC(6, 2), 
	billable_hours NUMERIC(6, 2), 
	non_billable_hours NUMERIC(6, 2), 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_timesheets_id ON timesheets (id);

CREATE INDEX ix_timesheets_status ON timesheets (status);

CREATE INDEX ix_timesheets_period_start ON timesheets (period_start);

CREATE INDEX ix_timesheets_employee_id ON timesheets (employee_id);

CREATE INDEX ix_timesheets_project_id ON timesheets (project_id);

CREATE TABLE recruitment_requisitions (
	id SERIAL NOT NULL, 
	requisition_number VARCHAR(50) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	department_id INTEGER, 
	designation_id INTEGER, 
	branch_id INTEGER, 
	openings INTEGER, 
	justification TEXT, 
	target_joining_date DATE, 
	status VARCHAR(30), 
	requested_by INTEGER, 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	job_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE SET NULL, 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(designation_id) REFERENCES designations (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(branch_id) REFERENCES branches (id) ON DELETE SET NULL, 
	FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX ix_recruitment_requisitions_requisition_number ON recruitment_requisitions (requisition_number);

CREATE INDEX ix_recruitment_requisitions_status ON recruitment_requisitions (status);

CREATE INDEX ix_recruitment_requisitions_id ON recruitment_requisitions (id);

CREATE TABLE candidates (
	id SERIAL NOT NULL, 
	job_id INTEGER NOT NULL, 
	first_name VARCHAR(80) NOT NULL, 
	last_name VARCHAR(80) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	phone VARCHAR(20), 
	current_company VARCHAR(200), 
	current_designation VARCHAR(150), 
	total_experience NUMERIC(4, 1), 
	current_ctc NUMERIC(12, 2), 
	expected_ctc NUMERIC(12, 2), 
	notice_period_days INTEGER, 
	current_location VARCHAR(150), 
	linkedin_url VARCHAR(500), 
	portfolio_url VARCHAR(500), 
	resume_url VARCHAR(500), 
	resume_parsed_data TEXT, 
	ai_score NUMERIC(5, 2), 
	ai_summary TEXT, 
	source VARCHAR(50), 
	status VARCHAR(30), 
	applied_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	referred_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(referred_by) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX ix_candidates_id ON candidates (id);

CREATE TABLE employee_onboarding_tasks (
	id SERIAL NOT NULL, 
	employee_onboarding_id INTEGER NOT NULL, 
	template_task_id INTEGER, 
	task_name VARCHAR(200) NOT NULL, 
	category VARCHAR(50), 
	due_date DATE, 
	assigned_to_user_id INTEGER, 
	status VARCHAR(30), 
	completed_at TIMESTAMP WITH TIME ZONE, 
	completed_by INTEGER, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_to_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_onboarding_id) REFERENCES employee_onboardings (id) ON DELETE CASCADE, 
	FOREIGN KEY(completed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(template_task_id) REFERENCES onboarding_template_tasks (id) ON DELETE SET NULL
);

CREATE INDEX ix_employee_onboarding_tasks_category ON employee_onboarding_tasks (category);

CREATE INDEX ix_employee_onboarding_tasks_due_date ON employee_onboarding_tasks (due_date);

CREATE INDEX ix_employee_onboarding_tasks_status ON employee_onboarding_tasks (status);

CREATE INDEX ix_employee_onboarding_tasks_employee_onboarding_id ON employee_onboarding_tasks (employee_onboarding_id);

CREATE INDEX ix_employee_onboarding_tasks_id ON employee_onboarding_tasks (id);

CREATE INDEX ix_employee_onboarding_tasks_assigned_to_user_id ON employee_onboarding_tasks (assigned_to_user_id);

CREATE TABLE performance_rating_criteria (
	id SERIAL NOT NULL, 
	review_id INTEGER NOT NULL, 
	criteria_name VARCHAR(150) NOT NULL, 
	criteria_category VARCHAR(80), 
	rating NUMERIC(3, 1), 
	comments TEXT, 
	weightage NUMERIC(5, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(review_id) REFERENCES performance_reviews (id) ON DELETE CASCADE
);

CREATE INDEX ix_performance_rating_criteria_id ON performance_rating_criteria (id);

CREATE INDEX ix_performance_rating_criteria_review_id ON performance_rating_criteria (review_id);

CREATE TABLE goal_check_ins (
	id SERIAL NOT NULL, 
	goal_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	progress_percent NUMERIC(5, 2), 
	confidence VARCHAR(30), 
	update_text TEXT, 
	blocker_text TEXT, 
	manager_comment TEXT, 
	checked_in_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(goal_id) REFERENCES performance_goals (id) ON DELETE CASCADE
);

CREATE INDEX ix_goal_check_ins_employee_id ON goal_check_ins (employee_id);

CREATE INDEX ix_goal_check_ins_id ON goal_check_ins (id);

CREATE INDEX ix_goal_check_ins_checked_in_at ON goal_check_ins (checked_in_at);

CREATE INDEX ix_goal_check_ins_goal_id ON goal_check_ins (goal_id);

CREATE TABLE succession_candidates (
	id SERIAL NOT NULL, 
	critical_role_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	readiness_level VARCHAR(40), 
	readiness_score NUMERIC(4, 2), 
	development_actions_json JSON, 
	mentor_employee_id INTEGER, 
	status VARCHAR(30), 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mentor_employee_id) REFERENCES employees (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(critical_role_id) REFERENCES critical_roles (id) ON DELETE CASCADE
);

CREATE INDEX ix_succession_candidates_critical_role_id ON succession_candidates (critical_role_id);

CREATE INDEX ix_succession_candidates_readiness_level ON succession_candidates (readiness_level);

CREATE INDEX ix_succession_candidates_status ON succession_candidates (status);

CREATE INDEX ix_succession_candidates_employee_id ON succession_candidates (employee_id);

CREATE INDEX ix_succession_candidates_id ON succession_candidates (id);

CREATE TABLE helpdesk_replies (
	id SERIAL NOT NULL, 
	ticket_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	message TEXT NOT NULL, 
	is_internal BOOLEAN, 
	attachment_url VARCHAR(500), 
	is_ai_generated BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(ticket_id) REFERENCES helpdesk_tickets (id) ON DELETE CASCADE
);

CREATE INDEX ix_helpdesk_replies_id ON helpdesk_replies (id);

CREATE TABLE exit_checklist_items (
	id SERIAL NOT NULL, 
	exit_record_id INTEGER NOT NULL, 
	task_name VARCHAR(200) NOT NULL, 
	assigned_to_role VARCHAR(50), 
	assigned_to_user INTEGER, 
	is_completed BOOLEAN, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_to_user) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(exit_record_id) REFERENCES exit_records (id) ON DELETE CASCADE
);

CREATE INDEX ix_exit_checklist_items_id ON exit_checklist_items (id);

CREATE TABLE exit_interviews (
	id SERIAL NOT NULL, 
	exit_record_id INTEGER NOT NULL, 
	conducted_by INTEGER, 
	interview_date DATE, 
	reason_for_leaving VARCHAR(100), 
	job_satisfaction INTEGER, 
	management_satisfaction INTEGER, 
	work_environment_satisfaction INTEGER, 
	growth_satisfaction INTEGER, 
	would_rejoin BOOLEAN, 
	feedback TEXT, 
	suggestions TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(exit_record_id) REFERENCES exit_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(conducted_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_exit_interviews_id ON exit_interviews (id);

CREATE TABLE certification_renewals (
	id SERIAL NOT NULL, 
	certification_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	due_on DATE NOT NULL, 
	status VARCHAR(30), 
	reminder_sent_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	evidence_url VARCHAR(500), 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(certification_id) REFERENCES learning_certifications (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_certification_renewals_due_on ON certification_renewals (due_on);

CREATE INDEX ix_certification_renewals_status ON certification_renewals (status);

CREATE INDEX ix_certification_renewals_id ON certification_renewals (id);

CREATE INDEX ix_certification_renewals_employee_id ON certification_renewals (employee_id);

CREATE INDEX ix_certification_renewals_certification_id ON certification_renewals (certification_id);

CREATE TABLE recognition_reactions (
	id SERIAL NOT NULL, 
	recognition_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	emoji VARCHAR(20), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(recognition_id) REFERENCES recognitions (id) ON DELETE CASCADE
);

CREATE INDEX ix_recognition_reactions_recognition_id ON recognition_reactions (recognition_id);

CREATE INDEX ix_recognition_reactions_id ON recognition_reactions (id);

CREATE INDEX ix_recognition_reactions_employee_id ON recognition_reactions (employee_id);

CREATE TABLE whatsapp_ess_messages (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	direction VARCHAR(20) NOT NULL, 
	phone_number VARCHAR(30) NOT NULL, 
	message_text TEXT NOT NULL, 
	intent VARCHAR(80), 
	status VARCHAR(30), 
	provider_message_id VARCHAR(150), 
	response_text TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(session_id) REFERENCES whatsapp_ess_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_whatsapp_ess_messages_id ON whatsapp_ess_messages (id);

CREATE INDEX ix_whatsapp_ess_messages_employee_id ON whatsapp_ess_messages (employee_id);

CREATE INDEX ix_whatsapp_ess_messages_session_id ON whatsapp_ess_messages (session_id);

CREATE INDEX ix_whatsapp_ess_messages_direction ON whatsapp_ess_messages (direction);

CREATE INDEX ix_whatsapp_ess_messages_status ON whatsapp_ess_messages (status);

CREATE TABLE benefit_dependents (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	enrollment_id INTEGER, 
	full_name VARCHAR(150) NOT NULL, 
	relationship VARCHAR(50) NOT NULL, 
	date_of_birth DATE, 
	gender VARCHAR(20), 
	identity_number VARCHAR(80), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(enrollment_id) REFERENCES employee_benefit_enrollments (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_benefit_dependents_id ON benefit_dependents (id);

CREATE INDEX ix_benefit_dependents_enrollment_id ON benefit_dependents (enrollment_id);

CREATE INDEX ix_benefit_dependents_is_active ON benefit_dependents (is_active);

CREATE INDEX ix_benefit_dependents_employee_id ON benefit_dependents (employee_id);

CREATE TABLE benefit_payroll_deductions (
	id SERIAL NOT NULL, 
	enrollment_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	payroll_record_id INTEGER, 
	month INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	employee_amount NUMERIC(12, 2), 
	employer_amount NUMERIC(12, 2), 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(enrollment_id) REFERENCES employee_benefit_enrollments (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL
);

CREATE INDEX ix_benefit_payroll_deductions_id ON benefit_payroll_deductions (id);

CREATE INDEX ix_benefit_payroll_deductions_payroll_record_id ON benefit_payroll_deductions (payroll_record_id);

CREATE INDEX ix_benefit_payroll_deductions_status ON benefit_payroll_deductions (status);

CREATE INDEX ix_benefit_payroll_deductions_employee_id ON benefit_payroll_deductions (employee_id);

CREATE INDEX ix_benefit_payroll_deductions_enrollment_id ON benefit_payroll_deductions (enrollment_id);

CREATE TABLE benefit_claims (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	benefit_plan_id INTEGER, 
	policy_id INTEGER, 
	claim_type VARCHAR(60) NOT NULL, 
	claim_date DATE NOT NULL, 
	claim_amount NUMERIC(12, 2) NOT NULL, 
	approved_amount NUMERIC(12, 2), 
	taxable_amount NUMERIC(12, 2), 
	tax_exempt_amount NUMERIC(12, 2), 
	receipt_url VARCHAR(500), 
	status VARCHAR(30), 
	submitted_by INTEGER, 
	reviewed_by INTEGER, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	review_remarks TEXT, 
	payroll_record_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(policy_id) REFERENCES flexi_benefit_policies (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(benefit_plan_id) REFERENCES benefit_plans (id) ON DELETE SET NULL
);

CREATE INDEX ix_benefit_claims_id ON benefit_claims (id);

CREATE INDEX ix_benefit_claims_claim_type ON benefit_claims (claim_type);

CREATE INDEX ix_benefit_claims_policy_id ON benefit_claims (policy_id);

CREATE INDEX ix_benefit_claims_status ON benefit_claims (status);

CREATE INDEX ix_benefit_claims_employee_id ON benefit_claims (employee_id);

CREATE INDEX ix_benefit_claims_benefit_plan_id ON benefit_claims (benefit_plan_id);

CREATE INDEX ix_benefit_claims_payroll_record_id ON benefit_claims (payroll_record_id);

CREATE TABLE esop_vesting_schedules (
	id SERIAL NOT NULL, 
	grant_id INTEGER NOT NULL, 
	vesting_date DATE NOT NULL, 
	units NUMERIC(14, 2) NOT NULL, 
	status VARCHAR(30), 
	vested_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(grant_id) REFERENCES esop_grants (id) ON DELETE CASCADE
);

CREATE INDEX ix_esop_vesting_schedules_grant_id ON esop_vesting_schedules (grant_id);

CREATE INDEX ix_esop_vesting_schedules_vesting_date ON esop_vesting_schedules (vesting_date);

CREATE INDEX ix_esop_vesting_schedules_id ON esop_vesting_schedules (id);

CREATE INDEX ix_esop_vesting_schedules_status ON esop_vesting_schedules (status);

CREATE TABLE crm_note_mentions (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	note_id INTEGER, 
	activity_id INTEGER, 
	mentioned_user_id INTEGER NOT NULL, 
	mentioned_by INTEGER, 
	entity_type VARCHAR(40), 
	entity_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	read_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mentioned_user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(note_id) REFERENCES crm_notes (id) ON DELETE CASCADE, 
	FOREIGN KEY(mentioned_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(activity_id) REFERENCES crm_activities (id) ON DELETE CASCADE
);

CREATE INDEX ix_crm_note_mentions_organization_id ON crm_note_mentions (organization_id);

CREATE INDEX ix_crm_note_mentions_mentioned_by ON crm_note_mentions (mentioned_by);

CREATE INDEX ix_crm_note_mentions_entity_id ON crm_note_mentions (entity_id);

CREATE INDEX ix_crm_note_mentions_mentioned_user_id ON crm_note_mentions (mentioned_user_id);

CREATE INDEX ix_crm_note_mentions_created_at ON crm_note_mentions (created_at);

CREATE INDEX ix_crm_note_mentions_id ON crm_note_mentions (id);

CREATE INDEX ix_crm_note_mentions_activity_id ON crm_note_mentions (activity_id);

CREATE INDEX ix_crm_note_mentions_note_id ON crm_note_mentions (note_id);

CREATE INDEX ix_crm_note_mentions_entity_type ON crm_note_mentions (entity_type);

CREATE TABLE pms_sprint_retro_action_items (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	sprint_id INTEGER NOT NULL, 
	title VARCHAR(220) NOT NULL, 
	owner_user_id INTEGER, 
	due_date DATE, 
	created_task_id INTEGER, 
	status VARCHAR(30), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_task_id) REFERENCES pms_tasks (id) ON DELETE SET NULL, 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(sprint_id) REFERENCES pms_sprints (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_sprint_retro_action_items_organization_id ON pms_sprint_retro_action_items (organization_id);

CREATE INDEX ix_pms_sprint_retro_action_items_sprint_id ON pms_sprint_retro_action_items (sprint_id);

CREATE INDEX ix_pms_sprint_retro_action_items_id ON pms_sprint_retro_action_items (id);

CREATE INDEX ix_pms_sprint_retro_action_items_status ON pms_sprint_retro_action_items (status);

CREATE INDEX ix_pms_sprint_retro_action_items_owner_user_id ON pms_sprint_retro_action_items (owner_user_id);

CREATE INDEX ix_pms_sprint_retro_action_items_created_task_id ON pms_sprint_retro_action_items (created_task_id);

CREATE TABLE pms_task_dependencies (
	id SERIAL NOT NULL, 
	task_id INTEGER NOT NULL, 
	depends_on_task_id INTEGER NOT NULL, 
	dependency_type VARCHAR(40), 
	lag_days INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(depends_on_task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE, 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE, 
	CONSTRAINT uq_pms_task_dependency UNIQUE (task_id, depends_on_task_id)
);

CREATE INDEX ix_pms_task_dependencies_id ON pms_task_dependencies (id);

CREATE INDEX ix_pms_task_dependencies_task_id ON pms_task_dependencies (task_id);

CREATE INDEX ix_pms_task_dependencies_depends_on_task_id ON pms_task_dependencies (depends_on_task_id);

CREATE TABLE pms_dev_links (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	task_id INTEGER NOT NULL, 
	provider VARCHAR(30) NOT NULL, 
	link_type VARCHAR(30) NOT NULL, 
	external_id VARCHAR(240) NOT NULL, 
	title VARCHAR(300), 
	url VARCHAR(800), 
	status VARCHAR(60), 
	author VARCHAR(160), 
	metadata_json TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pms_dev_link_external UNIQUE (task_id, provider, link_type, external_id), 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_dev_links_link_type ON pms_dev_links (link_type);

CREATE INDEX ix_pms_dev_links_external_id ON pms_dev_links (external_id);

CREATE INDEX ix_pms_dev_links_task_id ON pms_dev_links (task_id);

CREATE INDEX ix_pms_dev_links_provider ON pms_dev_links (provider);

CREATE INDEX ix_pms_dev_links_status ON pms_dev_links (status);

CREATE INDEX ix_pms_dev_links_id ON pms_dev_links (id);

CREATE INDEX ix_pms_dev_links_organization_id ON pms_dev_links (organization_id);

CREATE TABLE pms_activities (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	task_id INTEGER, 
	sprint_id INTEGER, 
	actor_user_id INTEGER, 
	action VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(40) NOT NULL, 
	entity_id INTEGER, 
	summary VARCHAR(300) NOT NULL, 
	metadata_json TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE, 
	FOREIGN KEY(sprint_id) REFERENCES pms_sprints (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_activities_task_id ON pms_activities (task_id);

CREATE INDEX ix_pms_activities_entity_id ON pms_activities (entity_id);

CREATE INDEX ix_pms_activities_id ON pms_activities (id);

CREATE INDEX ix_pms_activities_project_id ON pms_activities (project_id);

CREATE INDEX ix_pms_activities_actor_user_id ON pms_activities (actor_user_id);

CREATE INDEX ix_pms_activities_created_at ON pms_activities (created_at);

CREATE INDEX ix_pms_activities_sprint_id ON pms_activities (sprint_id);

CREATE INDEX ix_pms_activities_action ON pms_activities (action);

CREATE INDEX ix_pms_activities_entity_type ON pms_activities (entity_type);

CREATE TABLE pms_checklist_items (
	id SERIAL NOT NULL, 
	task_id INTEGER NOT NULL, 
	title VARCHAR(220) NOT NULL, 
	is_completed BOOLEAN, 
	position INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_checklist_items_id ON pms_checklist_items (id);

CREATE INDEX ix_pms_checklist_items_task_id ON pms_checklist_items (task_id);

CREATE TABLE pms_task_tags (
	task_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, 
	PRIMARY KEY (task_id, tag_id), 
	FOREIGN KEY(tag_id) REFERENCES pms_tags (id) ON DELETE CASCADE, 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE
);

CREATE TABLE pms_file_assets (
	id SERIAL NOT NULL, 
	uploaded_by_user_id INTEGER, 
	project_id INTEGER, 
	task_id INTEGER, 
	milestone_id INTEGER, 
	file_name VARCHAR(240) NOT NULL, 
	original_name VARCHAR(240) NOT NULL, 
	mime_type VARCHAR(120), 
	size_bytes INTEGER, 
	storage_path VARCHAR(500) NOT NULL, 
	version_number INTEGER, 
	visibility VARCHAR(40), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE, 
	FOREIGN KEY(uploaded_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(milestone_id) REFERENCES pms_milestones (id) ON DELETE CASCADE, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_file_assets_id ON pms_file_assets (id);

CREATE INDEX ix_pms_file_assets_task_id ON pms_file_assets (task_id);

CREATE INDEX ix_pms_file_assets_project_id ON pms_file_assets (project_id);

CREATE INDEX ix_pms_file_assets_milestone_id ON pms_file_assets (milestone_id);

CREATE INDEX ix_pms_file_assets_uploaded_by_user_id ON pms_file_assets (uploaded_by_user_id);

CREATE INDEX ix_pms_file_assets_visibility ON pms_file_assets (visibility);

CREATE TABLE pms_comments (
	id SERIAL NOT NULL, 
	author_user_id INTEGER, 
	project_id INTEGER, 
	task_id INTEGER, 
	milestone_id INTEGER, 
	parent_comment_id INTEGER, 
	body TEXT NOT NULL, 
	body_format VARCHAR(20), 
	is_internal BOOLEAN, 
	is_edited BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_comment_id) REFERENCES pms_comments (id) ON DELETE CASCADE, 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(milestone_id) REFERENCES pms_milestones (id) ON DELETE CASCADE, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_comments_task_id ON pms_comments (task_id);

CREATE INDEX ix_pms_comments_milestone_id ON pms_comments (milestone_id);

CREATE INDEX ix_pms_comments_id ON pms_comments (id);

CREATE INDEX ix_pms_comments_project_id ON pms_comments (project_id);

CREATE INDEX ix_pms_comments_body_format ON pms_comments (body_format);

CREATE INDEX ix_pms_comments_author_user_id ON pms_comments (author_user_id);

CREATE INDEX ix_pms_comments_parent_comment_id ON pms_comments (parent_comment_id);

CREATE INDEX ix_pms_comments_is_internal ON pms_comments (is_internal);

CREATE TABLE pms_time_logs (
	id SERIAL NOT NULL, 
	timesheet_id INTEGER, 
	user_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	task_id INTEGER, 
	log_date DATE NOT NULL, 
	start_time TIMESTAMP WITH TIME ZONE, 
	end_time TIMESTAMP WITH TIME ZONE, 
	duration_minutes INTEGER NOT NULL, 
	description TEXT, 
	is_billable BOOLEAN, 
	approval_status VARCHAR(30), 
	approved_by_user_id INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(timesheet_id) REFERENCES pms_timesheets (id) ON DELETE SET NULL, 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_pms_time_logs_id ON pms_time_logs (id);

CREATE INDEX ix_pms_time_logs_project_id ON pms_time_logs (project_id);

CREATE INDEX ix_pms_time_logs_is_billable ON pms_time_logs (is_billable);

CREATE INDEX ix_pms_time_logs_user_id ON pms_time_logs (user_id);

CREATE INDEX ix_pms_time_logs_task_id ON pms_time_logs (task_id);

CREATE INDEX ix_pms_time_logs_approval_status ON pms_time_logs (approval_status);

CREATE INDEX ix_pms_time_logs_timesheet_id ON pms_time_logs (timesheet_id);

CREATE INDEX ix_pms_time_logs_log_date ON pms_time_logs (log_date);

CREATE TABLE pms_risks (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	project_id INTEGER NOT NULL, 
	linked_task_id INTEGER, 
	title VARCHAR(220) NOT NULL, 
	description TEXT, 
	category VARCHAR(80), 
	probability INTEGER, 
	impact INTEGER, 
	risk_score INTEGER, 
	status VARCHAR(30), 
	owner_user_id INTEGER, 
	mitigation_plan TEXT, 
	contingency_plan TEXT, 
	due_date DATE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(linked_task_id) REFERENCES pms_tasks (id) ON DELETE SET NULL, 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_risks_due_date ON pms_risks (due_date);

CREATE INDEX ix_pms_risks_project_id ON pms_risks (project_id);

CREATE INDEX ix_pms_risks_probability ON pms_risks (probability);

CREATE INDEX ix_pms_risks_status ON pms_risks (status);

CREATE INDEX ix_pms_risks_id ON pms_risks (id);

CREATE INDEX ix_pms_risks_linked_task_id ON pms_risks (linked_task_id);

CREATE INDEX ix_pms_risks_impact ON pms_risks (impact);

CREATE INDEX ix_pms_risks_owner_user_id ON pms_risks (owner_user_id);

CREATE INDEX ix_pms_risks_organization_id ON pms_risks (organization_id);

CREATE INDEX ix_pms_risks_category ON pms_risks (category);

CREATE INDEX ix_pms_risks_risk_score ON pms_risks (risk_score);

CREATE TABLE srm_invoice_lines (
	id SERIAL NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	source_type VARCHAR(60), 
	source_id INTEGER, 
	description TEXT NOT NULL, 
	quantity NUMERIC(12, 2), 
	unit_price NUMERIC(14, 2), 
	tax_amount NUMERIC(14, 2), 
	line_total NUMERIC(14, 2), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_srm_invoice_line_source UNIQUE (source_type, source_id), 
	FOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_invoice_lines_id ON srm_invoice_lines (id);

CREATE INDEX ix_srm_invoice_lines_source_id ON srm_invoice_lines (source_id);

CREATE INDEX ix_srm_invoice_lines_source_type ON srm_invoice_lines (source_type);

CREATE INDEX ix_srm_invoice_lines_invoice_id ON srm_invoice_lines (invoice_id);

CREATE TABLE srm_invoice_history (
	id SERIAL NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	from_status VARCHAR(40), 
	to_status VARCHAR(40) NOT NULL, 
	actor_user_id INTEGER, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_invoice_history_id ON srm_invoice_history (id);

CREATE INDEX ix_srm_invoice_history_to_status ON srm_invoice_history (to_status);

CREATE INDEX ix_srm_invoice_history_created_at ON srm_invoice_history (created_at);

CREATE INDEX ix_srm_invoice_history_invoice_id ON srm_invoice_history (invoice_id);

CREATE TABLE srm_receipt_allocations (
	id SERIAL NOT NULL, 
	receipt_id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	amount NUMERIC(14, 2), 
	allocated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	allocated_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE CASCADE, 
	FOREIGN KEY(allocated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(receipt_id) REFERENCES srm_receipts (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_receipt_allocations_invoice_id ON srm_receipt_allocations (invoice_id);

CREATE INDEX ix_srm_receipt_allocations_allocated_at ON srm_receipt_allocations (allocated_at);

CREATE INDEX ix_srm_receipt_allocations_id ON srm_receipt_allocations (id);

CREATE INDEX ix_srm_receipt_allocations_receipt_id ON srm_receipt_allocations (receipt_id);

CREATE TABLE srm_collection_reminders (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	customer_id INTEGER, 
	invoice_id INTEGER, 
	status VARCHAR(40), 
	reminder_type VARCHAR(60), 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	message TEXT, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE CASCADE
);

CREATE INDEX ix_srm_collection_reminders_customer_id ON srm_collection_reminders (customer_id);

CREATE INDEX ix_srm_collection_reminders_created_at ON srm_collection_reminders (created_at);

CREATE INDEX ix_srm_collection_reminders_id ON srm_collection_reminders (id);

CREATE INDEX ix_srm_collection_reminders_scheduled_at ON srm_collection_reminders (scheduled_at);

CREATE INDEX ix_srm_collection_reminders_organization_id ON srm_collection_reminders (organization_id);

CREATE INDEX ix_srm_collection_reminders_invoice_id ON srm_collection_reminders (invoice_id);

CREATE INDEX ix_srm_collection_reminders_status ON srm_collection_reminders (status);

CREATE TABLE srm_revenue_events (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	engagement_id INTEGER, 
	invoice_id INTEGER, 
	event_type VARCHAR(80) NOT NULL, 
	amount NUMERIC(14, 2), 
	currency VARCHAR(10), 
	recognized_on DATE, 
	metadata_json JSON, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES srm_invoices (id) ON DELETE SET NULL, 
	FOREIGN KEY(engagement_id) REFERENCES srm_engagements (id) ON DELETE SET NULL
);

CREATE INDEX ix_srm_revenue_events_organization_id ON srm_revenue_events (organization_id);

CREATE INDEX ix_srm_revenue_events_recognized_on ON srm_revenue_events (recognized_on);

CREATE INDEX ix_srm_revenue_events_invoice_id ON srm_revenue_events (invoice_id);

CREATE INDEX ix_srm_revenue_events_event_type ON srm_revenue_events (event_type);

CREATE INDEX ix_srm_revenue_events_id ON srm_revenue_events (id);

CREATE INDEX ix_srm_revenue_events_engagement_id ON srm_revenue_events (engagement_id);

CREATE INDEX ix_srm_revenue_events_created_at ON srm_revenue_events (created_at);

CREATE TABLE onboarding_task_completions (
	id SERIAL NOT NULL, 
	onboarding_id INTEGER NOT NULL, 
	task_id INTEGER NOT NULL, 
	is_completed BOOLEAN, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_by INTEGER, 
	remarks TEXT, 
	document_url VARCHAR(500), 
	PRIMARY KEY (id), 
	CONSTRAINT onboarding_task_completions_ibfk_1 FOREIGN KEY(onboarding_id) REFERENCES employee_onboardings (id) ON DELETE CASCADE, 
	CONSTRAINT onboarding_task_completions_ibfk_3 FOREIGN KEY(completed_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT onboarding_task_completions_ibfk_2 FOREIGN KEY(task_id) REFERENCES onboarding_tasks (id) ON DELETE CASCADE
);

CREATE INDEX onboarding_id ON onboarding_task_completions (onboarding_id);

CREATE INDEX task_id ON onboarding_task_completions (task_id);

CREATE INDEX ix_onboarding_task_completions_id ON onboarding_task_completions (id);

CREATE INDEX completed_by ON onboarding_task_completions (completed_by);

CREATE TABLE expense_claims (
	id SERIAL NOT NULL, 
	employee_id INTEGER NOT NULL, 
	claim_number VARCHAR(50) NOT NULL, 
	claim_type VARCHAR(60) NOT NULL, 
	expense_date DATE NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	approved_amount NUMERIC(12, 2), 
	currency VARCHAR(10), 
	description TEXT, 
	receipt_url VARCHAR(500), 
	status VARCHAR(30), 
	manager_approved_by INTEGER, 
	manager_approved_at TIMESTAMP WITH TIME ZONE, 
	finance_approved_by INTEGER, 
	finance_approved_at TIMESTAMP WITH TIME ZONE, 
	payroll_reimbursement_id INTEGER, 
	payroll_run_id INTEGER, 
	reimbursed_at TIMESTAMP WITH TIME ZONE, 
	reimbursement_reference VARCHAR(120), 
	remarks TEXT, 
	submitted_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE SET NULL, 
	FOREIGN KEY(finance_approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(payroll_reimbursement_id) REFERENCES reimbursements (id) ON DELETE SET NULL, 
	FOREIGN KEY(manager_approved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_expense_claims_id ON expense_claims (id);

CREATE INDEX ix_expense_claims_payroll_reimbursement_id ON expense_claims (payroll_reimbursement_id);

CREATE INDEX ix_expense_claims_claim_type ON expense_claims (claim_type);

CREATE INDEX ix_expense_claims_status ON expense_claims (status);

CREATE INDEX ix_expense_claims_employee_id ON expense_claims (employee_id);

CREATE UNIQUE INDEX ix_expense_claims_claim_number ON expense_claims (claim_number);

CREATE INDEX ix_expense_claims_payroll_run_id ON expense_claims (payroll_run_id);

CREATE TABLE leave_encashment_requests (
	id SERIAL NOT NULL, 
	organization_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	leave_type_id INTEGER NOT NULL, 
	days_to_encash NUMERIC(6, 2) NOT NULL, 
	encashment_rate NUMERIC(12, 2), 
	amount NUMERIC(12, 2), 
	status VARCHAR(30), 
	requested_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	approved_by INTEGER, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	payroll_run_id INTEGER, 
	leave_encashment_line_id INTEGER, 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(leave_encashment_line_id) REFERENCES leave_encashment_lines (id) ON DELETE SET NULL, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE SET NULL, 
	FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE CASCADE
);

CREATE INDEX ix_leave_encashment_requests_employee_id ON leave_encashment_requests (employee_id);

CREATE INDEX ix_leave_encashment_requests_leave_encashment_line_id ON leave_encashment_requests (leave_encashment_line_id);

CREATE INDEX ix_leave_encashment_requests_id ON leave_encashment_requests (id);

CREATE INDEX ix_leave_encashment_requests_payroll_run_id ON leave_encashment_requests (payroll_run_id);

CREATE INDEX ix_leave_encashment_requests_leave_type_id ON leave_encashment_requests (leave_type_id);

CREATE INDEX ix_leave_encashment_requests_status ON leave_encashment_requests (status);

CREATE INDEX ix_leave_encashment_requests_organization_id ON leave_encashment_requests (organization_id);

CREATE TABLE payroll_calculation_snapshots (
	id SERIAL NOT NULL, 
	payroll_run_id INTEGER NOT NULL, 
	run_employee_id INTEGER, 
	employee_id INTEGER NOT NULL, 
	snapshot_type VARCHAR(50), 
	salary_template_json JSON, 
	tax_worksheet_json JSON, 
	attendance_input_json JSON, 
	statutory_profile_json JSON, 
	formula_version_json JSON, 
	result_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(run_employee_id) REFERENCES payroll_run_employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_calculation_snapshots_employee_id ON payroll_calculation_snapshots (employee_id);

CREATE INDEX ix_payroll_calculation_snapshots_snapshot_type ON payroll_calculation_snapshots (snapshot_type);

CREATE INDEX ix_payroll_calculation_snapshots_payroll_run_id ON payroll_calculation_snapshots (payroll_run_id);

CREATE INDEX ix_payroll_calculation_snapshots_run_employee_id ON payroll_calculation_snapshots (run_employee_id);

CREATE INDEX ix_payroll_calculation_snapshots_id ON payroll_calculation_snapshots (id);

CREATE TABLE reimbursement_ledgers (
	id SERIAL NOT NULL, 
	reimbursement_id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	amount NUMERIC(12, 2), 
	status_from VARCHAR(30), 
	status_to VARCHAR(30), 
	payroll_record_id INTEGER, 
	actor_user_id INTEGER, 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(payroll_record_id) REFERENCES payroll_records (id) ON DELETE SET NULL, 
	FOREIGN KEY(reimbursement_id) REFERENCES reimbursements (id) ON DELETE CASCADE
);

CREATE INDEX ix_reimbursement_ledgers_action ON reimbursement_ledgers (action);

CREATE INDEX ix_reimbursement_ledgers_id ON reimbursement_ledgers (id);

CREATE INDEX ix_reimbursement_ledgers_reimbursement_id ON reimbursement_ledgers (reimbursement_id);

CREATE INDEX ix_reimbursement_ledgers_employee_id ON reimbursement_ledgers (employee_id);

CREATE TABLE full_final_settlement_lines (
	id SERIAL NOT NULL, 
	settlement_id INTEGER NOT NULL, 
	line_type VARCHAR(30) NOT NULL, 
	component_name VARCHAR(120) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	source VARCHAR(80), 
	is_manual_adjustment BOOLEAN, 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(settlement_id) REFERENCES full_final_settlements (id) ON DELETE CASCADE
);

CREATE INDEX ix_full_final_settlement_lines_id ON full_final_settlement_lines (id);

CREATE INDEX ix_full_final_settlement_lines_settlement_id ON full_final_settlement_lines (settlement_id);

CREATE TABLE employee_tax_proofs (
	id SERIAL NOT NULL, 
	declaration_item_id INTEGER NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	file_type VARCHAR(120), 
	uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(declaration_item_id) REFERENCES employee_tax_declaration_items (id) ON DELETE CASCADE
);

CREATE INDEX ix_employee_tax_proofs_declaration_item_id ON employee_tax_proofs (declaration_item_id);

CREATE INDEX ix_employee_tax_proofs_id ON employee_tax_proofs (id);

CREATE TABLE timesheet_entries (
	id SERIAL NOT NULL, 
	timesheet_id INTEGER NOT NULL, 
	work_date DATE NOT NULL, 
	hours NUMERIC(4, 2) NOT NULL, 
	is_billable BOOLEAN, 
	task_name VARCHAR(200), 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(timesheet_id) REFERENCES timesheets (id) ON DELETE CASCADE
);

CREATE INDEX ix_timesheet_entries_timesheet_id ON timesheet_entries (timesheet_id);

CREATE INDEX ix_timesheet_entries_id ON timesheet_entries (id);

CREATE INDEX ix_timesheet_entries_work_date ON timesheet_entries (work_date);

CREATE TABLE interviews (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	round_number INTEGER NOT NULL, 
	round_name VARCHAR(100), 
	interview_type VARCHAR(30), 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	duration_minutes INTEGER, 
	interviewer_ids TEXT, 
	meet_link VARCHAR(500), 
	venue VARCHAR(300), 
	status VARCHAR(30), 
	result VARCHAR(30), 
	overall_rating NUMERIC(3, 1), 
	remarks TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id) ON DELETE CASCADE
);

CREATE INDEX ix_interviews_id ON interviews (id);

CREATE TABLE offer_letters (
	id SERIAL NOT NULL, 
	candidate_id INTEGER NOT NULL, 
	offer_date DATE, 
	joining_date DATE, 
	designation VARCHAR(150), 
	department VARCHAR(150), 
	ctc NUMERIC(12, 2), 
	basic NUMERIC(12, 2), 
	template_id INTEGER, 
	letter_url VARCHAR(500), 
	status VARCHAR(30), 
	expiry_date DATE, 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(template_id) REFERENCES document_templates (id) ON DELETE SET NULL, 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id) ON DELETE CASCADE
);

CREATE INDEX ix_offer_letters_id ON offer_letters (id);

CREATE TABLE whatsapp_ess_delivery_events (
	id SERIAL NOT NULL, 
	message_id INTEGER, 
	provider_message_id VARCHAR(150), 
	status VARCHAR(30) NOT NULL, 
	raw_payload TEXT, 
	received_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(message_id) REFERENCES whatsapp_ess_messages (id) ON DELETE CASCADE
);

CREATE INDEX ix_whatsapp_ess_delivery_events_status ON whatsapp_ess_delivery_events (status);

CREATE INDEX ix_whatsapp_ess_delivery_events_id ON whatsapp_ess_delivery_events (id);

CREATE INDEX ix_whatsapp_ess_delivery_events_provider_message_id ON whatsapp_ess_delivery_events (provider_message_id);

CREATE INDEX ix_whatsapp_ess_delivery_events_message_id ON whatsapp_ess_delivery_events (message_id);

CREATE TABLE background_verification_requests (
	id SERIAL NOT NULL, 
	vendor_id INTEGER, 
	candidate_id INTEGER, 
	employee_id INTEGER, 
	package_name VARCHAR(120) NOT NULL, 
	status VARCHAR(30), 
	vendor_status VARCHAR(80), 
	initiated_by INTEGER, 
	initiated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	consent_status VARCHAR(30), 
	consent_captured_at TIMESTAMP WITH TIME ZONE, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	last_synced_at TIMESTAMP WITH TIME ZONE, 
	expected_completion_date DATE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	overall_result VARCHAR(30), 
	vendor_reference VARCHAR(120), 
	report_url VARCHAR(500), 
	consent_url VARCHAR(500), 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(vendor_id) REFERENCES background_verification_vendors (id) ON DELETE SET NULL, 
	FOREIGN KEY(initiated_by) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(candidate_id) REFERENCES candidates (id) ON DELETE CASCADE
);

CREATE INDEX ix_background_verification_requests_id ON background_verification_requests (id);

CREATE INDEX ix_background_verification_requests_vendor_id ON background_verification_requests (vendor_id);

CREATE INDEX ix_background_verification_requests_status ON background_verification_requests (status);

CREATE INDEX ix_background_verification_requests_candidate_id ON background_verification_requests (candidate_id);

CREATE INDEX ix_background_verification_requests_consent_status ON background_verification_requests (consent_status);

CREATE INDEX ix_background_verification_requests_employee_id ON background_verification_requests (employee_id);

CREATE TABLE pms_mentions (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	task_id INTEGER NOT NULL, 
	comment_id INTEGER, 
	mentioned_user_id INTEGER NOT NULL, 
	mentioned_by_user_id INTEGER, 
	notification_id INTEGER, 
	read_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES pms_projects (id) ON DELETE CASCADE, 
	FOREIGN KEY(notification_id) REFERENCES notifications (id) ON DELETE SET NULL, 
	FOREIGN KEY(mentioned_user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(task_id) REFERENCES pms_tasks (id) ON DELETE CASCADE, 
	FOREIGN KEY(mentioned_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(comment_id) REFERENCES pms_comments (id) ON DELETE CASCADE
);

CREATE INDEX ix_pms_mentions_project_id ON pms_mentions (project_id);

CREATE INDEX ix_pms_mentions_task_id ON pms_mentions (task_id);

CREATE INDEX ix_pms_mentions_notification_id ON pms_mentions (notification_id);

CREATE INDEX ix_pms_mentions_id ON pms_mentions (id);

CREATE INDEX ix_pms_mentions_mentioned_by_user_id ON pms_mentions (mentioned_by_user_id);

CREATE INDEX ix_pms_mentions_created_at ON pms_mentions (created_at);

CREATE INDEX ix_pms_mentions_comment_id ON pms_mentions (comment_id);

CREATE INDEX ix_pms_mentions_mentioned_user_id ON pms_mentions (mentioned_user_id);

CREATE TABLE interview_feedbacks (
	id SERIAL NOT NULL, 
	interview_id INTEGER NOT NULL, 
	interviewer_id INTEGER NOT NULL, 
	technical_score NUMERIC(3, 1), 
	communication_score NUMERIC(3, 1), 
	attitude_score NUMERIC(3, 1), 
	overall_score NUMERIC(3, 1), 
	strengths TEXT, 
	weaknesses TEXT, 
	recommendation VARCHAR(20), 
	comments TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(interviewer_id) REFERENCES employees (id) ON DELETE CASCADE, 
	FOREIGN KEY(interview_id) REFERENCES interviews (id) ON DELETE CASCADE
);

CREATE INDEX ix_interview_feedbacks_id ON interview_feedbacks (id);

CREATE TABLE background_verification_checks (
	id SERIAL NOT NULL, 
	request_id INTEGER NOT NULL, 
	check_type VARCHAR(80) NOT NULL, 
	status VARCHAR(30), 
	result VARCHAR(30), 
	score NUMERIC(5, 2), 
	document_url VARCHAR(500), 
	verified_by VARCHAR(150), 
	verified_at TIMESTAMP WITH TIME ZONE, 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES background_verification_requests (id) ON DELETE CASCADE
);

CREATE INDEX ix_background_verification_checks_status ON background_verification_checks (status);

CREATE INDEX ix_background_verification_checks_id ON background_verification_checks (id);

CREATE INDEX ix_background_verification_checks_check_type ON background_verification_checks (check_type);

CREATE INDEX ix_background_verification_checks_request_id ON background_verification_checks (request_id);

CREATE TABLE background_verification_connector_events (
	id SERIAL NOT NULL, 
	request_id INTEGER NOT NULL, 
	vendor_id INTEGER, 
	event_type VARCHAR(80) NOT NULL, 
	vendor_reference VARCHAR(120), 
	payload_json JSON NOT NULL, 
	processing_status VARCHAR(30), 
	error_message TEXT, 
	received_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES background_verification_requests (id) ON DELETE CASCADE, 
	FOREIGN KEY(vendor_id) REFERENCES background_verification_vendors (id) ON DELETE SET NULL
);

CREATE INDEX ix_background_verification_connector_events_id ON background_verification_connector_events (id);

CREATE INDEX ix_background_verification_connector_events_vendor_id ON background_verification_connector_events (vendor_id);

CREATE INDEX ix_background_verification_connector_events_request_id ON background_verification_connector_events (request_id);

CREATE INDEX ix_background_verification_connector_events_processing_status ON background_verification_connector_events (processing_status);

CREATE INDEX ix_background_verification_connector_events_event_type ON background_verification_connector_events (event_type);

CREATE INDEX ix_background_verification_connector_events_vendor_reference ON background_verification_connector_events (vendor_reference);

ALTER TABLE business_units ADD FOREIGN KEY(head_employee_id) REFERENCES employees (id) ON DELETE SET NULL;

ALTER TABLE positions ADD FOREIGN KEY(incumbent_employee_id) REFERENCES employees (id) ON DELETE SET NULL;

ALTER TABLE cost_centers ADD FOREIGN KEY(owner_employee_id) REFERENCES employees (id) ON DELETE SET NULL;

ALTER TABLE departments ADD FOREIGN KEY(head_employee_id) REFERENCES employees (id) ON DELETE SET NULL;