"""Payroll delivery settings, durable payout attempts and verified Form 16 signing."""
import sqlalchemy as sa


def upgrade(op):
    op.create_table("payroll_delivery_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("ytd_basis", sa.String(20), nullable=False, server_default="financial"),
        sa.Column("fy_start_month", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("regular_template", sa.JSON(), nullable=False), sa.Column("settlement_template", sa.JSON(), nullable=False),
        sa.Column("branding", sa.JSON(), nullable=False), sa.Column("payout_key_id", sa.String(120)),
        sa.Column("payout_secret_encrypted", sa.Text()), sa.Column("payout_account", sa.String(120)),
        sa.Column("payout_mode", sa.String(10), nullable=False, server_default="test"),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("payroll_payout_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("payroll_payment_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payroll_record_id", sa.Integer(), sa.ForeignKey("payroll_records.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("provider_id", sa.String(100), unique=True), sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="prepared"),
        sa.Column("error", sa.String(300)), sa.Column("utr", sa.String(120)), sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("payroll_record_id", "mode", name="uq_payroll_payout_record_mode"))
    op.create_index("ix_payroll_payout_attempts_batch_id", "payroll_payout_attempts", ["batch_id"])
    with op.batch_alter_table("payroll_payment_batches") as batch:
        batch.add_column(sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", name="fk_payroll_payment_batches_company_id", ondelete="SET NULL")))
    op.execute(sa.text("UPDATE payroll_payment_batches SET company_id = (SELECT company_id FROM payroll_runs WHERE payroll_runs.id = payroll_payment_batches.payroll_run_id)"))
    with op.batch_alter_table("form16_records") as batch:
        for column in [sa.Column("signed_file_path", sa.String(500)),
                   sa.Column("signature_status", sa.String(30), nullable=False, server_default="pending"),
                   sa.Column("signed_sha256", sa.String(64)), sa.Column("signature_evidence_json", sa.Text()),
                   sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", name="fk_form16_records_reviewed_by_users", ondelete="SET NULL")),
                   sa.Column("reviewed_at", sa.DateTime(timezone=True))]:
            batch.add_column(column)


def downgrade(op):
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM payroll_payout_attempts")).scalar():
        raise RuntimeError("Retain payout idempotency records; do not downgrade after preparing payments")
    with op.batch_alter_table("form16_records") as batch:
        for name in ["reviewed_at", "reviewed_by", "signature_evidence_json", "signed_sha256", "signature_status", "signed_file_path"]:
            batch.drop_column(name)
    op.drop_table("payroll_payout_attempts")
    with op.batch_alter_table("payroll_payment_batches") as batch:
        batch.drop_column("company_id")
    op.drop_table("payroll_delivery_profiles")
