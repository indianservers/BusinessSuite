from alembic import context
from flask import current_app

db = current_app.extensions['migrate'].db
config = context.config
config.set_main_option('sqlalchemy.url', db.engine.url.render_as_string(hide_password=False).replace('%', '%%'))
if context.is_offline_mode():
    context.configure(url=config.get_main_option('sqlalchemy.url'), target_metadata=db.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with db.engine.connect() as connection:
        context.configure(connection=connection,target_metadata=db.metadata,compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
