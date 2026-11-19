"""Scoped Sales report views, explicit test flags, exports and schedules."""
from alembic import op
import sqlalchemy as sa

revision='pg_20261118_125_srm_reports'
down_revision='pg_20261116_124_telegram_exp'
branch_labels=depends_on=None


def _scope():
    return [sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),
        sa.Column('branch_id',sa.Integer(),sa.ForeignKey('branches.id'),nullable=False)]


def upgrade():
    op.create_table('srm_report_views',*_scope(),
        sa.Column('owner_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('name',sa.String(100),nullable=False),sa.Column('report',sa.String(40),nullable=False),
        sa.Column('filters_json',sa.JSON(),nullable=False),sa.Column('columns_json',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_table('srm_report_flags',*_scope(),sa.Column('entity',sa.String(30),nullable=False),
        sa.Column('resource_id',sa.Integer(),nullable=False),sa.Column('is_test',sa.Boolean(),nullable=False),
        sa.Column('reason',sa.String(500),nullable=False),sa.Column('updated_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('organization_id','entity','resource_id',name='uq_srm_report_test_flag'))
    op.create_table('srm_report_jobs',*_scope(),sa.Column('owner_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.String(36),nullable=False),sa.Column('report',sa.String(40),nullable=False),
        sa.Column('format',sa.String(10),nullable=False),sa.Column('filters_json',sa.JSON(),nullable=False),
        sa.Column('columns_json',sa.JSON(),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.Column('row_count',sa.Integer(),nullable=False),sa.Column('file_path',sa.Text()),
        sa.Column('content_sha256',sa.String(64)),sa.Column('error',sa.String(500)),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('completed_at',sa.DateTime(timezone=True)),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('organization_id','request_key',name='uq_srm_report_job_request'))
    op.create_table('srm_report_schedules',*_scope(),sa.Column('owner_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('enabled',sa.Boolean(),nullable=False),sa.Column('config_json',sa.JSON(),nullable=False),
        sa.Column('state_json',sa.JSON(),nullable=False),sa.Column('next_run_at',sa.DateTime(timezone=True)),
        sa.Column('last_run_at',sa.DateTime(timezone=True)),sa.Column('last_error',sa.String(500)),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('organization_id','branch_id','owner_id',name='uq_srm_report_owner_schedule'))
    for table in ('srm_report_views','srm_report_flags','srm_report_jobs','srm_report_schedules'):
        for column in ('organization_id','branch_id'):
            op.create_index(f'ix_{table}_{column}',table,[column])
        if table!='srm_report_flags':op.create_index(f'ix_{table}_owner_id',table,['owner_id'])
    op.create_index('ix_srm_report_job_queue','srm_report_jobs',['status','created_at'])
    op.create_index('ix_srm_report_jobs_status','srm_report_jobs',['status'])
    op.create_index('ix_srm_report_schedules_next_run_at','srm_report_schedules',['next_run_at'])


def downgrade():
    for name in ('srm_report_schedules','srm_report_jobs','srm_report_flags','srm_report_views'):op.drop_table(name)

