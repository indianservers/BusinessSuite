from dotenv import load_dotenv
load_dotenv('/srv/business-suite/shared/backend.env')
from datetime import timedelta
from app.core.security import create_access_token
from app.db.session import engine
from sqlalchemy import text
import httpx,json
with engine.connect() as db:
 actor=db.execute(text("select id from users where lower(email)=lower(:email) and is_active=true"),{'email':'saisatish@indianservers.com'}).scalar_one()
 print('actor_id',actor)
h={'Authorization':'Bearer '+create_access_token(actor,timedelta(minutes=5)),'X-Suite-Organization':'1','X-Suite-Branch':'1'}
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',headers=h,timeout=30) as client:
 for path in ['/srm/industry/employee-options','/srm/industry/capabilities','/srm/service-checkout/options/9']:
  res=client.get(path);print(path,res.status_code,res.text[:6000])
