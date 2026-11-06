from alembic import context
from app.platform_owner.models import PlatformBase
from app.platform_owner.session import platform_factory

with platform_factory()().get_bind().connect() as connection:
    context.configure(connection=connection, target_metadata=PlatformBase.metadata)
    with context.begin_transaction():
        context.run_migrations()
