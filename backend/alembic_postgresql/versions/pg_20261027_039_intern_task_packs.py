"""Reusable intern task packs, skill variants and audited deadline extensions."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261027_039_intern_packs"
down_revision = "pg_20261027_038_doc_studio"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "pms_bulk_deadline_changes" not in existing:
        op.create_table('pms_bulk_deadline_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('changes', sa.JSON(), nullable=False),
        sa.Column('request_key', sa.String(length=100), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['pms_projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'request_key', name='uq_pms_bulk_deadline_request')
        )
        op.create_index(op.f('ix_pms_bulk_deadline_changes_organization_id'), 'pms_bulk_deadline_changes', ['organization_id'], unique=False)
    if "pms_intern_task_packs" not in existing:
        op.create_table('pms_intern_task_packs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['pms_projects.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_pms_intern_task_packs_organization_id'), 'pms_intern_task_packs', ['organization_id'], unique=False)
        op.create_index(op.f('ix_pms_intern_task_packs_project_id'), 'pms_intern_task_packs', ['project_id'], unique=False)
    if "pms_intern_pack_runs" not in existing:
        op.create_table('pms_intern_pack_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('pack_id', sa.Integer(), nullable=False),
        sa.Column('pack_version', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('request_key', sa.String(length=100), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['pack_id'], ['pms_intern_task_packs.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['pms_projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'request_key', name='uq_pms_intern_pack_run')
        )
        op.create_index(op.f('ix_pms_intern_pack_runs_organization_id'), 'pms_intern_pack_runs', ['organization_id'], unique=False)
    if "pms_intern_assignment_plans" not in existing:
        op.create_table('pms_intern_assignment_plans',
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('step_key', sa.String(length=40), nullable=False),
        sa.Column('skill_level', sa.String(length=20), nullable=False),
        sa.Column('prerequisites', sa.JSON(), nullable=False),
        sa.Column('rubric', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['pms_intern_pack_runs.id'], ),
        sa.ForeignKeyConstraint(['task_id'], ['pms_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('task_id', 'user_id')
        )
        op.create_index(op.f('ix_pms_intern_assignment_plans_run_id'), 'pms_intern_assignment_plans', ['run_id'], unique=False)


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "pms_intern_assignment_plans" in existing:
        op.drop_table("pms_intern_assignment_plans")
    if "pms_intern_pack_runs" in existing:
        op.drop_table("pms_intern_pack_runs")
    if "pms_intern_task_packs" in existing:
        op.drop_table("pms_intern_task_packs")
    if "pms_bulk_deadline_changes" in existing:
        op.drop_table("pms_bulk_deadline_changes")
