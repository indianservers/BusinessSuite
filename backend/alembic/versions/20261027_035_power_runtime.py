"""Add isolated Power Apps runtime tables; preserve every existing draft and snapshot."""
from alembic import op
import sqlalchemy as sa
revision = '20261027_035_power_runtime'
down_revision = '20261027_034_custom_columns'
branch_labels = None
depends_on = None

def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if 'power_automation_deployments' not in existing:
        op.create_table('power_automation_deployments',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('resource_id', sa.Integer(), sa.ForeignKey('power_apps_resources.id'), nullable=False),
            sa.Column('version_id', sa.Integer(), sa.ForeignKey('power_apps_versions.id')),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('validated_version', sa.Integer()),
            sa.Column('revision', sa.Integer(), nullable=False),
            sa.Column('policy', sa.JSON(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.UniqueConstraint('resource_id'),
        )
    if 'power_automation_run_states' not in existing:
        op.create_table('power_automation_run_states',
            sa.Column('id', sa.Integer(), sa.ForeignKey('power_apps_executions.id'), primary_key=True, nullable=False),
            sa.Column('version_id', sa.Integer(), sa.ForeignKey('power_apps_versions.id'), nullable=False),
            sa.Column('trigger_id', sa.Integer()),
            sa.Column('trigger_kind', sa.String(length=30), nullable=False),
            sa.Column('effective_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('correlation_id', sa.String(length=36), nullable=False),
            sa.Column('plan', sa.JSON(), nullable=False),
            sa.Column('input_payload', sa.JSON(), nullable=False),
            sa.Column('variables', sa.JSON(), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True)),
            sa.Column('finished_at', sa.DateTime(timezone=True)),
            sa.Column('deadline', sa.DateTime(timezone=True), nullable=False),
            sa.Column('error_type', sa.String(length=100)),
            sa.Column('error', sa.Text()),
            sa.Column('payloads_purged_at', sa.DateTime(timezone=True)),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.UniqueConstraint('correlation_id'),
        )
        op.create_index('ix_power_automation_run_states_payloads_purged_at', 'power_automation_run_states', ['payloads_purged_at'], unique=False)
        op.create_index('ix_power_run_tenant_time', 'power_automation_run_states', ['organization_id', 'environment', 'started_at'], unique=False)
    if 'power_automation_steps' not in existing:
        op.create_table('power_automation_steps',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('run_id', sa.Integer(), sa.ForeignKey('power_apps_executions.id'), nullable=False),
            sa.Column('node_id', sa.String(length=180), nullable=False),
            sa.Column('original_node_id', sa.String(length=80), nullable=False),
            sa.Column('scope', sa.String(length=160), nullable=False),
            sa.Column('local_context', sa.JSON(), nullable=False),
            sa.Column('status', sa.String(length=24), nullable=False),
            sa.Column('attempt', sa.Integer(), nullable=False),
            sa.Column('input_payload', sa.JSON()),
            sa.Column('output', sa.JSON()),
            sa.Column('active_ports', sa.JSON(), nullable=False),
            sa.Column('error_type', sa.String(length=100)),
            sa.Column('error', sa.Text()),
            sa.Column('started_at', sa.DateTime(timezone=True)),
            sa.Column('finished_at', sa.DateTime(timezone=True)),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.UniqueConstraint('run_id', 'node_id', name='uq_power_step_node'),
        )
    if 'power_automation_jobs' not in existing:
        op.create_table('power_automation_jobs',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('run_id', sa.Integer(), sa.ForeignKey('power_apps_executions.id'), nullable=False),
            sa.Column('step_id', sa.Integer(), sa.ForeignKey('power_automation_steps.id'), nullable=False),
            sa.Column('status', sa.String(length=24), nullable=False),
            sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('lease_token', sa.String(length=36)),
            sa.Column('lease_until', sa.DateTime(timezone=True)),
            sa.Column('heartbeat_at', sa.DateTime(timezone=True)),
            sa.Column('claims', sa.Integer(), nullable=False),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.UniqueConstraint('step_id'),
        )
        op.create_index('ix_power_job_claim', 'power_automation_jobs', ['status', 'available_at', 'lease_until'], unique=False)
        op.create_index('ix_power_job_tenant', 'power_automation_jobs', ['organization_id', 'environment', 'status'], unique=False)
    if 'power_automation_waits' not in existing:
        op.create_table('power_automation_waits',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('run_id', sa.Integer(), sa.ForeignKey('power_apps_executions.id'), nullable=False),
            sa.Column('step_id', sa.Integer(), sa.ForeignKey('power_automation_steps.id'), nullable=False),
            sa.Column('wake_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('event_key', sa.String(length=120)),
            sa.Column('kind', sa.String(length=24), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.UniqueConstraint('step_id'),
        )
        op.create_index('ix_power_wait_due', 'power_automation_waits', ['status', 'wake_at'], unique=False)
    if 'power_automation_triggers' not in existing:
        op.create_table('power_automation_triggers',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('resource_id', sa.Integer(), sa.ForeignKey('power_apps_resources.id'), nullable=False),
            sa.Column('kind', sa.String(length=30), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.Column('endpoint', sa.String(length=64)),
            sa.Column('encrypted_secret', sa.Text()),
            sa.Column('secret_version', sa.Integer(), nullable=False),
            sa.Column('config', sa.JSON(), nullable=False),
            sa.Column('next_at', sa.DateTime(timezone=True)),
            sa.Column('last_at', sa.DateTime(timezone=True)),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.UniqueConstraint('endpoint'),
            sa.UniqueConstraint('resource_id', 'kind', name='uq_power_trigger_kind'),
        )
        op.create_index('ix_power_trigger_due', 'power_automation_triggers', ['kind', 'enabled', 'next_at'], unique=False)
    if 'power_automation_events' not in existing:
        op.create_table('power_automation_events',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('run_id', sa.Integer(), sa.ForeignKey('power_apps_executions.id')),
            sa.Column('resource_id', sa.Integer(), nullable=False),
            sa.Column('step_id', sa.Integer()),
            sa.Column('kind', sa.String(length=40), nullable=False),
            sa.Column('details', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        )
        op.create_index('ix_power_event_run', 'power_automation_events', ['run_id', 'id'], unique=False)
    if 'power_automation_dead_letters' not in existing:
        op.create_table('power_automation_dead_letters',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('run_id', sa.Integer(), sa.ForeignKey('power_apps_executions.id'), nullable=False),
            sa.Column('job_id', sa.Integer(), sa.ForeignKey('power_automation_jobs.id'), nullable=False),
            sa.Column('reason', sa.String(length=100), nullable=False),
            sa.Column('resolved_at', sa.DateTime(timezone=True)),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        )
    if 'power_automation_replays' not in existing:
        op.create_table('power_automation_replays',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('trigger_id', sa.Integer(), sa.ForeignKey('power_automation_triggers.id'), nullable=False),
            sa.Column('nonce_hash', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
            sa.Column('environment', sa.String(length=20), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.UniqueConstraint('trigger_id', 'nonce_hash', name='uq_power_trigger_replay'),
        )
    if 'power_automation_workers' not in existing:
        op.create_table('power_automation_workers',
            sa.Column('id', sa.String(length=100), primary_key=True, nullable=False),
            sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('scheduler_at', sa.DateTime(timezone=True)),
            sa.Column('processed', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
        )

def downgrade():
    # Explicit operator rollback only; runtime never drops its durable history.
    op.drop_table('power_automation_workers')
    op.drop_table('power_automation_replays')
    op.drop_table('power_automation_dead_letters')
    op.drop_table('power_automation_events')
    op.drop_table('power_automation_triggers')
    op.drop_table('power_automation_waits')
    op.drop_table('power_automation_jobs')
    op.drop_table('power_automation_steps')
    op.drop_table('power_automation_run_states')
    op.drop_table('power_automation_deployments')
