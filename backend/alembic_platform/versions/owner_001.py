"""Independent Indian Servers owner identities, signup queue, and audit trail."""
from alembic import op
import sqlalchemy as sa

revision = "owner_001"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    op.create_table("platform_admins", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(150), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("token_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("platform_signup_requests", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("applicant_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(180), nullable=False), sa.Column("company_name", sa.String(180)),
        sa.Column("email", sa.String(150), nullable=False), sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("phone_country_code", sa.String(5), nullable=False),
        sa.Column("requested_modules", sa.JSON, nullable=False), sa.Column("notes", sa.Text),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("company_id", sa.Integer), sa.Column("user_id", sa.Integer),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("platform_admins.id")),
        sa.Column("review_reason", sa.String(500)), sa.Column("trial_ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_platform_signup_requests_email", "platform_signup_requests", ["email"], unique=True)
    op.create_index("ix_platform_signup_requests_status", "platform_signup_requests", ["status"])
    op.create_table("platform_approval_history", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("signup_id", sa.Integer, sa.ForeignKey("platform_signup_requests.id"), nullable=False),
        sa.Column("admin_id", sa.Integer, sa.ForeignKey("platform_admins.id"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False), sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("security_rate_buckets", sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window", sa.BigInteger, primary_key=True), sa.Column("count", sa.Integer, nullable=False),
        sa.Column("expires", sa.BigInteger, nullable=False), sa.CheckConstraint("count >= 1", name="ck_security_rate_count_positive"))
    op.create_index("ix_security_rate_buckets_expires", "security_rate_buckets", ["expires"])


def downgrade():
    for name in ["security_rate_buckets", "platform_approval_history", "platform_signup_requests", "platform_admins"]:
        op.drop_table(name)
