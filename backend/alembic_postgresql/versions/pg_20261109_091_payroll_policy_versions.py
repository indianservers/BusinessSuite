"""Effective-dated payroll policies and calculation provenance; no history rewrite."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261109_091_payroll_policies'
down_revision = 'pg_20261108_090_employee_bgv'
branch_labels = depends_on = None


def upgrade():
    op.create_table('payroll_policy_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pay_group_id', sa.Integer(), sa.ForeignKey('payroll_pay_groups.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('rules', sa.JSON(), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('pay_group_id','effective_from',name='uq_payroll_policy_group_date'))
    op.create_index('ix_payroll_policy_versions_pay_group_id','payroll_policy_versions',['pay_group_id'])
    op.add_column('payroll_runs',sa.Column('policy_snapshot',sa.JSON()))
    op.add_column('payroll_attendance_inputs',sa.Column('policy_trace',sa.JSON()))


def downgrade():
    raise RuntimeError('Payroll policy history must be retained; restore a pre-migration backup to roll back')
