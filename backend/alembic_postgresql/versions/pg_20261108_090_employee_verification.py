"""Connect existing employee verification and exit history."""
revision = 'pg_20261108_090_employee_bgv'
down_revision = 'pg_20261108_089_partner_claims'
branch_labels = depends_on = None
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("background_verification_vendors", sa.Column("organization_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, server_default="1"))
    op.create_index("ix_background_verification_vendors_organization_id", "background_verification_vendors", ["organization_id"])
    # Shared legacy vendors stay in the original company; do not silently expose
    # another company's vendor configuration after this migration.
    for constraint in sa.inspect(op.get_bind()).get_unique_constraints("background_verification_vendors"):
        if constraint["column_names"] == ["name"]:
            op.drop_constraint(constraint["name"], "background_verification_vendors", type_="unique")
    op.create_unique_constraint("uq_bgv_vendor_company_name", "background_verification_vendors", ["organization_id", "name"])
    for column in [
        sa.Column("purpose", sa.String(80), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_notes", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ]: op.add_column("background_verification_requests", column)
    op.add_column("background_verification_checks", sa.Column("employee_document_id", sa.Integer(), sa.ForeignKey("employee_documents.id", ondelete="RESTRICT")))
    # Repeated employment uses existing exit rows rather than overwriting them.
    for constraint in sa.inspect(op.get_bind()).get_unique_constraints("exit_records"):
        if constraint["column_names"] == ["employee_id"]:
            op.drop_constraint(constraint["name"], "exit_records", type_="unique")
    op.create_index("ix_exit_records_employee_id", "exit_records", ["employee_id"])


def downgrade():
    # A downgrade cannot safely collapse multiple employment periods into one.
    raise RuntimeError("Employee verification history must be retained; restore a pre-migration backup to roll back")
