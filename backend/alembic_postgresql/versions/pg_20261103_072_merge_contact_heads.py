"""Merge concurrent contact identity and local schema repair migrations."""
revision = 'pg_20261103_072_merge_contacts'
down_revision = ('pg_20261103_067_contacts', 'pg_20261103_071_contact_links')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
