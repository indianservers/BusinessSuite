"""Company database directory, independently placed across registered servers."""
from alembic import op
import sqlalchemy as sa

revision = "owner_003"
down_revision = "owner_002"
branch_labels = depends_on = None


def upgrade():
    op.create_table("platform_database_servers",
        sa.Column("id",sa.Integer,primary_key=True), sa.Column("code",sa.String(50),unique=True,nullable=False),
        sa.Column("name",sa.String(150),nullable=False),sa.Column("host",sa.String(255),nullable=False),
        sa.Column("port",sa.Integer,nullable=False),sa.Column("provisioning_env",sa.String(100),nullable=False),
        sa.Column("template_database",sa.String(63),nullable=False),sa.Column("active",sa.Boolean,nullable=False),
        sa.Column("max_databases",sa.Integer,nullable=False))
    op.create_table("platform_tenant_databases",
        sa.Column("id",sa.Integer,primary_key=True),sa.Column("signup_id",sa.Integer,unique=True,nullable=False),
        sa.Column("tenant_uuid",sa.String(36),unique=True,nullable=False),sa.Column("workspace_code",sa.String(64),unique=True,nullable=False),
        sa.Column("company_id",sa.Integer,unique=True,nullable=False),sa.Column("server_id",sa.Integer,sa.ForeignKey("platform_database_servers.id"),nullable=False),
        sa.Column("database_name",sa.String(63),unique=True,nullable=False),sa.Column("runtime_role",sa.String(63),unique=True,nullable=False),
        sa.Column("encrypted_password",sa.Text,nullable=False),sa.Column("status",sa.String(30),nullable=False,index=True),
        sa.Column("routing_version",sa.Integer,nullable=False),sa.Column("schema_version",sa.String(150),nullable=False),
        sa.Column("last_error",sa.String(250)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))


def downgrade():
    # Database data is never dropped by downgrading this directory migration.
    op.drop_table("platform_tenant_databases")
    op.drop_table("platform_database_servers")
