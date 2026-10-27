"""Shared atomic security throttles and expiring work leases."""

from alembic import op
import sqlalchemy as sa

revision = "20261027_030_security"
down_revision = "20261026_029_workforce_ops"
branch_labels = None
depends_on = None
LEGACY_ROOTS = (
    "accounting_ledgers",
    "admin_audit_logs",
    "admin_compliance_settings",
    "admin_data_retention_rules",
    "admin_data_sharing_rules",
    "admin_duplicate_rules",
    "admin_export_controls",
    "admin_import_jobs",
    "admin_ip_restrictions",
    "admin_manual_record_shares",
    "admin_profiles",
    "admin_record_sharing_rules",
    "ai_operator_providers",
    "ai_prompt_templates",
    "ai_provider_settings",
    "analytics_anomaly_rules",
    "asset_categories",
    "background_verification_vendors",
    "bank_advice_formats",
    "benefit_enrollment_windows",
    "benefit_plans",
    "biometric_devices",
    "communication_consents",
    "communication_opt_outs",
    "communication_whatsapp_templates",
    "compensation_cycles",
    "competencies",
    "custom_field_definitions",
    "custom_form_definitions",
    "customization_audit_logs",
    "customization_buttons",
    "customization_fields",
    "customization_formula_fields",
    "customization_global_picklists",
    "customization_kanban_views",
    "customization_layouts",
    "customization_modules",
    "customization_related_lists",
    "customization_rollup_fields",
    "customization_validation_rules",
    "data_retention_policies",
    "developer_webhooks",
    "engagement_surveys",
    "esop_plans",
    "feature_catalog",
    "flexi_benefit_policies",
    "geo_attendance_policies",
    "helpdesk_categories",
    "holidays",
    "industry_targets",
    "job_families",
    "learning_courses",
    "leave_types",
    "marketplace_apps",
    "metric_definitions",
    "mobile_sales_visit_checkins",
    "payroll_compliance_rules",
    "payroll_exchange_rates",
    "payroll_report_definitions",
    "pms_collaboration_events",
    "portal_users",
    "report_definitions",
    "review_templates",
    "salary_component_categories",
    "sandbox_environments",
    "schedule_boards",
    "scheduled_job_runs",
    "shifts",
    "sso_providers",
    "tax_declaration_cycles",
    "tax_section_limits",
    "tax_slabs",
    "tenant_company_settings",
    "tenant_feature_flags",
    "tenant_usage_metrics",
    "webhook_subscriptions",
    "whatsapp_ess_configs",
)


def upgrade():
    op.create_table(
        "security_resource_ownership",
        sa.Column("resource_table", sa.String(100), primary_key=True),
        sa.Column("resource_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_security_resource_ownership_company_id",
        "security_resource_ownership",
        ["company_id"],
    )
    # Existing unowned configuration is attributable only in single-company DBs.
    bind = op.get_bind()
    companies = (
        bind.execute(sa.text("SELECT id FROM companies LIMIT 2")).scalars().all()
    )
    if len(companies) == 1:
        available = set(sa.inspect(bind).get_table_names())
        for table in LEGACY_ROOTS:
            if table in available:
                bind.execute(
                    sa.text(
                        'INSERT INTO security_resource_ownership (resource_table, resource_id, company_id) SELECT :table_name, id, :company FROM "'
                        + table
                        + '"'
                    ),
                    {"table_name": table, "company": companies[0]},
                )
    op.create_table(
        "security_rate_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window", sa.BigInteger(), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("count >= 1", name="ck_security_rate_count_positive"),
    )
    op.create_index(
        "ix_security_rate_buckets_expires", "security_rate_buckets", ["expires"]
    )
    op.create_table(
        "security_work_leases",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("slot >= 0", name="ck_security_work_slot_nonnegative"),
    )
    op.create_index(
        "ix_security_work_leases_expires", "security_work_leases", ["expires"]
    )


def downgrade():
    op.drop_table("security_resource_ownership")
    op.drop_table("security_work_leases")
    op.drop_table("security_rate_buckets")
