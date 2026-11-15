from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.apps.crm.lead_management import core,check_owner
with SessionLocal() as db:
    admin=db.get(User,1)
    for ident in [10,11]:
        user=db.get(User,ident)
        try:
            check_owner(db,admin,ident)
            print({'id':ident,'canAssign':core()._crm_can_assign_beyond_self(user),'permissions':sorted(core()._crm_permission_names(user))})
        except Exception as error: print({'id':ident,'error':str(error)})
