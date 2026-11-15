from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.apps.crm.models import CRMLead,CRMMeeting
from app.apps.crm.lead_management import get_settings
from app.core.security import create_access_token
import json
from pathlib import Path
with SessionLocal() as db:
    user=db.get(User,1)
    info=get_settings(db,user)
    print({'owners':[{'id':o['id'],'name':o['name']} for o in info['owners']]})
    print({'meetings':{status:sum(1 for m in db.query(CRMMeeting) if m.status==status) for status in ['Scheduled','Confirmed','Completed','Attended','No-show','Rescheduled']}})
    token=create_access_token(str(user.id))
    Path('.tmp-crm-local-auth.json').write_text(json.dumps({'token':token,'user':{'id':user.id,'email':user.email,'is_superuser':user.is_superuser,'role':{'name':'admin'}}}))
