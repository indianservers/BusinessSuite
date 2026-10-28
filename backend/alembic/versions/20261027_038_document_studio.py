"""Database-backed letterheads, templates and immutable issuance snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "20261027_038_doc_studio"
down_revision = "20261027_037_approvals"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "document_studio_assets" not in existing:
        op.create_table('document_studio_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('content_type', sa.String(length=80), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_document_studio_assets_organization_id'), 'document_studio_assets', ['organization_id'], unique=False)
    if "document_studio_letterheads" not in existing:
        op.create_table('document_studio_letterheads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('header_text', sa.Text(), nullable=False),
        sa.Column('footer_text', sa.Text(), nullable=False),
        sa.Column('accent_color', sa.String(length=7), nullable=False),
        sa.Column('show_company_header', sa.Boolean(), nullable=False),
        sa.Column('logo_asset_id', sa.Integer(), nullable=True),
        sa.Column('background_asset_id', sa.Integer(), nullable=True),
        sa.Column('signature_asset_id', sa.Integer(), nullable=True),
        sa.Column('signatory_name', sa.String(length=150), nullable=False),
        sa.Column('signatory_title', sa.String(length=150), nullable=False),
        sa.Column('top_margin_mm', sa.Integer(), nullable=False),
        sa.Column('bottom_margin_mm', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(['background_asset_id'], ['document_studio_assets.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['logo_asset_id'], ['document_studio_assets.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['signature_asset_id'], ['document_studio_assets.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_document_studio_letterheads_organization_id'), 'document_studio_letterheads', ['organization_id'], unique=False)
    if "document_studio_templates" not in existing:
        op.create_table('document_studio_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('document_type', sa.String(length=80), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('orientation', sa.String(length=20), nullable=False),
        sa.Column('recipient_scope', sa.String(length=20), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('custom_fields', sa.JSON(), nullable=False),
        sa.Column('letterhead_id', sa.Integer(), nullable=True),
        sa.Column('starter_key', sa.String(length=60), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['letterhead_id'], ['document_studio_letterheads.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'starter_key', name='uq_studio_template_starter')
        )
        op.create_index(op.f('ix_document_studio_templates_organization_id'), 'document_studio_templates', ['organization_id'], unique=False)
    if "document_studio_documents" not in existing:
        op.create_table('document_studio_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(length=60), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('template_version', sa.Integer(), nullable=False),
        sa.Column('recipient_type', sa.String(length=20), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('recipient_name', sa.String(length=250), nullable=False),
        sa.Column('title', sa.String(length=250), nullable=False),
        sa.Column('document_type', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('request_key', sa.String(length=100), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('issued_by', sa.Integer(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column('revoked_by', sa.Integer(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoke_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['issued_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['template_id'], ['document_studio_templates.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'request_key', name='uq_studio_document_request'),
        sa.UniqueConstraint('reference')
        )
        op.create_index(op.f('ix_document_studio_documents_organization_id'), 'document_studio_documents', ['organization_id'], unique=False)
        op.create_index(op.f('ix_document_studio_documents_recipient_id'), 'document_studio_documents', ['recipient_id'], unique=False)


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "document_studio_documents" in existing:
        op.drop_table("document_studio_documents")
    if "document_studio_templates" in existing:
        op.drop_table("document_studio_templates")
    if "document_studio_letterheads" in existing:
        op.drop_table("document_studio_letterheads")
    if "document_studio_assets" in existing:
        op.drop_table("document_studio_assets")
