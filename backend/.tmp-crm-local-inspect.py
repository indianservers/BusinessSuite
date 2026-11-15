from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.apps.crm.models import CRMLead,CRMMeeting
from app.apps.crm.lead_models import CRMLeadManagementConfig
from app.apps.crm.lead_management import core
with SessionLocal() as db:
    for u in db.query(User).filter(User.is_active.is_(True),User.is_superuser.is_(True)).limit(5):
        print({'adminId':u.id,'organization':core()._organization_id(db,u)})
    print({'leads':db.query(CRMLead).count(),'meetings':db.query(CRMMeeting).count(),'configs':db.query(CRMLeadManagementConfig).count()})

