"""Own communication forms and optional-template rules explicitly."""
from alembic import op
import sqlalchemy as sa

revision = "20261101_050_comm_tenant"
down_revision = "20261101_049_ai_log_tenant"
branch_labels = None
depends_on = None
TABLES = ("communication_whatsapp_templates", "communication_auto_response_rules", "communication_webforms")


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(f"fk_{table}_organization", "companies", ["organization_id"], ["id"], ondelete="SET NULL")
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
        inspector = sa.inspect(op.get_bind())
        columns = {c["name"] for c in inspector.get_columns(table)}
        sources = []
        if inspector.has_table("security_resource_ownership"):
            sources.append(f"SELECT company_id FROM security_resource_ownership WHERE resource_table = '{table}' AND resource_id = {table}.id")
        if table == "communication_auto_response_rules" and "template_id" in columns and inspector.has_table("communication_email_templates"):
            sources.append(f"SELECT organization_id AS company_id FROM communication_email_templates WHERE id = {table}.template_id AND organization_id IS NOT NULL")
        if table == "communication_webforms":
            if "auto_response_rule_id" in columns:
                sources.append(f"SELECT organization_id AS company_id FROM communication_auto_response_rules WHERE id = {table}.auto_response_rule_id AND organization_id IS NOT NULL")
            if inspector.has_table("communication_timeline_events"):
                sources.append(f"SELECT organization_id AS company_id FROM communication_timeline_events WHERE record_type = 'webform' AND record_id = {table}.id AND channel = 'webform' AND event_type = 'created' AND organization_id IS NOT NULL")
        if sources:
            # Recorded ownership and creation events may agree. A conflict is
            # quarantined; current actor membership is never historical proof.
            union = " UNION ALL ".join(sources)
            op.execute(sa.text(f"UPDATE {table} SET organization_id = (SELECT MIN(company_id) FROM ({union}) AS evidence HAVING COUNT(DISTINCT company_id) = 1) WHERE organization_id IS NULL"))


def downgrade():
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_organization", type_="foreignkey")
            batch.drop_column("organization_id")
