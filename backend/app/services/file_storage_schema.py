"""Additive schema shared by both migration chains. No existing tables or files change."""
import sqlalchemy as sa


def upgrade(op):
    if sa.inspect(op.get_bind()).has_table("pms_private_note_attachments"):
        op.add_column("pms_private_note_attachments", sa.Column("storage_path", sa.String(1000), nullable=True))
    op.create_table("file_storage_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False), sa.Column("label", sa.String(160), nullable=False),
        sa.Column("account", sa.String(250)), sa.Column("encrypted_value", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("connected", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("file_storage_policies",
        sa.Column("organization_id", sa.Integer(), primary_key=True), sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("default_provider", sa.String(30), nullable=False), sa.Column("routes", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False))
    op.create_table("file_storage_oauth_states",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)))
    op.create_table("file_storage_objects",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(30), nullable=False), sa.Column("relative_path", sa.String(1000), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False), sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False), sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("connection_id", sa.Integer()), sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("folder_id", sa.String(250)), sa.Column("remote_id", sa.String(500)),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("error", sa.String(250)),
        sa.Column("versions", sa.JSON(), nullable=False), sa.Column("uploaded_by", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "relative_path", name="uq_file_storage_locator"))
    for name in ("connections", "oauth_states", "objects"):
        op.create_index(f"ix_file_storage_{name}_organization_id", f"file_storage_{name}", ["organization_id"])


def downgrade(op):
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM file_storage_objects")).scalar():
        raise RuntimeError("Retain storage metadata while registered files exist; restore file references before downgrading")
    if sa.inspect(bind).has_table("pms_private_note_attachments"):
        if bind.execute(sa.text("SELECT COUNT(*) FROM pms_private_note_attachments WHERE storage_path IS NOT NULL")).scalar():
            raise RuntimeError("Retain private-note file locators before downgrading")
        op.drop_column("pms_private_note_attachments", "storage_path")
    for name in ("objects", "oauth_states", "policies", "connections"):
        op.drop_table(f"file_storage_{name}")
