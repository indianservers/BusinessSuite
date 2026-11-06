"""Public signup review queue. Signup does not create an authenticated account."""
import sqlalchemy as sa


def upgrade(op):
    op.create_table("suite_signup_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("applicant_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("company_name", sa.String(180)),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("phone_country_code", sa.String(5), nullable=False),
        sa.Column("requested_modules", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("review_reason", sa.String(500)),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_suite_signup_requests_email", "suite_signup_requests", ["email"], unique=True)
    op.create_index("ix_suite_signup_requests_status", "suite_signup_requests", ["status"])
    op.create_index("ix_suite_signup_requests_company_id", "suite_signup_requests", ["company_id"])


def downgrade(op):
    op.drop_table("suite_signup_requests")
