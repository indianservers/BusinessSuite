from app.db.base_class import Base  # noqa: F401
from app.module_registry import import_model_modules

# Import enabled models so SQLAlchemy and Alembic see only the selected product set.
import_model_modules()
from app.shared import master_data_sync  # noqa: F401,E402
from app.module_registry import is_app_enabled
if all(is_app_enabled(key) for key in ("crm", "srm", "project_management")):
    # Compatibility synchronization must be registered after every process start,
    # rather than depending on which legacy endpoint is visited first.
    from app.apps.srm.services import customer_identity  # noqa: F401,E402

from app.apps.interns_hub.branch_ownership import install as install_public_intake_ownership
install_public_intake_ownership()

# Register transactional email events for all enabled product models.
from app.services import email_events  # noqa: E402,F401
from app.apps.communication import customer_events  # noqa: E402,F401

