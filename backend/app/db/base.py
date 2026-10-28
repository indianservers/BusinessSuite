from app.db.base_class import Base  # noqa: F401
from app.module_registry import import_model_modules

# Import enabled models so SQLAlchemy and Alembic see only the selected product set.
import_model_modules()

# Register transactional email events for all enabled product models.
from app.services import email_events  # noqa: E402,F401

