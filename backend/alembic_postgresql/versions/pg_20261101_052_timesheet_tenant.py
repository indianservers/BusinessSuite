"""Give timesheet projects explicit company ownership without guessing creators."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261101_052_timesheet_tenant"
down_revision = "pg_20261101_051_comm_tenant"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("organization_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("projects") as batch:
        batch.create_foreign_key("fk_projects_organization", "companies", ["organization_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    inspector = sa.inspect(op.get_bind())
    sources = []
    if inspector.has_table("employees") and inspector.has_table("branches"):
        sources.append("SELECT b.company_id FROM employees e JOIN branches b ON b.id=e.branch_id WHERE e.id=projects.owner_employee_id AND b.company_id IS NOT NULL")
    if inspector.has_table("security_resource_ownership"):
        sources.append("SELECT company_id FROM security_resource_ownership WHERE resource_table='projects' AND resource_id=projects.id")
    if sources:
        union = " UNION ALL ".join(sources)
        op.execute(sa.text(f"UPDATE projects SET organization_id=(SELECT MIN(company_id) FROM ({union}) AS evidence HAVING COUNT(DISTINCT company_id)=1) WHERE organization_id IS NULL"))


def downgrade():
    op.drop_index("ix_projects_organization_id", table_name="projects")
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_projects_organization", type_="foreignkey")
        batch.drop_column("organization_id")
