"""Request audit context and task associations."""
from alembic import op
import sqlalchemy as sa

revision = "20261024_002"
down_revision = "20261024_001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {column['name'] for column in sa.inspect(bind).get_columns('audit_logs')}
    fields = [('request_id', sa.String(64)), ('actor_email', sa.String(100)), ('actor_role', sa.String(80)),
              ('actor_authenticated', sa.Boolean()), ('module', sa.String(80)), ('task_id', sa.Integer()),
              ('project_id', sa.Integer()), ('workspace_id', sa.Integer()), ('error_type', sa.String(160)),
              ('ip_source', sa.String(40)), ('forwarded_ip', sa.String(50))]
    for name, kind in fields:
        if name not in existing:
            op.add_column('audit_logs', sa.Column(name, kind, nullable=True))
            existing.add(name)
    indexes = {item['name'] for item in sa.inspect(bind).get_indexes('audit_logs')}
    for name in ['request_id', 'actor_role', 'module', 'task_id', 'project_id', 'workspace_id', 'user_id', 'status_code']:
        index = f'ix_audit_logs_{name}'
        if name in existing and index not in indexes:
            op.create_index(index, 'audit_logs', [name])
    if not sa.inspect(bind).has_table('audit_log_tasks'):
        op.create_table('audit_log_tasks',
                        sa.Column('audit_log_id', sa.Integer(), sa.ForeignKey('audit_logs.id', ondelete='CASCADE'), primary_key=True),
                        sa.Column('task_id', sa.Integer(), primary_key=True))
        op.create_index('ix_audit_log_tasks_task_id', 'audit_log_tasks', ['task_id'])


def downgrade():
    # Audit records are evidence; reversal must not silently remove retained metadata.
    pass  # Additive metadata stays intact when rolling application code back.
