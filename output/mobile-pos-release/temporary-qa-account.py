from pathlib import Path
import json,secrets
import app.db.base
from app.db.session import SessionLocal
from app.models.user import User,UserSession
from app.models.company import Branch
from app.access.models import AccessPolicy,AccessMembership
from app.branches.models import BranchGrant,BranchPolicy
from app.access import service
from app.api.v1.auth import create_user
from app.schemas.auth import UserCreate
from app.core.deps import get_current_active_superuser
from app.common.services.identity import SharedIdentityService
BASE=Path('/srv/business-suite/shared/sample-hrms-categories-20261118')
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--disable',action='store_true');args=parser.parse_args()
with SessionLocal() as db:
 actor=db.query(User).filter(User.email=='saisatish@indianservers.com',User.is_active.is_(True)).one()
 get_current_active_superuser(actor)
 if service.primary_company(actor)!=1:raise RuntimeError('Wrong administrator company')
 if args.disable:
  data=json.loads((BASE/'qa-login.json').read_text());user=db.get(User,data['id'])
  if not user or user.email!=data['email'] or not user.email.startswith('sample-mobile-qa-'):raise RuntimeError('Refusing to alter a non-QA user')
  user.is_active=False
  db.query(UserSession).filter_by(user_id=user.id).update({UserSession.status:'Revoked'})
  policy=service.policy_for(db,user,1)
  if policy:policy.status='suspended';policy.version+=1
  for membership in db.query(AccessMembership).filter_by(user_id=user.id).all():membership.active=False
  for branch_grant in db.query(BranchGrant).filter_by(user_id=user.id).all():branch_grant.can_write=False
  service.audit(db,actor,1,'user.qa.disabled','Temporary mobile category verification complete',target=user.id)
  db.commit();(BASE/'qa-login.json').unlink();print(json.dumps({'qa_user_id':user.id,'active':False,'sessions':'revoked'}));raise SystemExit(0)
 if (BASE/'qa-login.json').exists():raise RuntimeError('A QA login already exists; reuse or disable it before creating another')
 password='Aa9!'+secrets.token_urlsafe(22);email='sample-mobile-qa-'+secrets.token_hex(5)+'@example.com'
 grants=service.validate_grants(db,{'srm':{'enabled':True,'role':'Temporary mobile QA','permissions':['srm_view','srm_manage'],'actions':['view','create'],'scope':'own'}},1)
 user=create_user(UserCreate(email=email,password=password,is_superuser=False),db,actor)
 SharedIdentityService.ensure_person_for_user(db,user,organization_id=1)
 branch=db.query(Branch).filter(Branch.company_id==1,Branch.name=='Main',Branch.is_active.is_(True)).one()
 policy=service.policy_for(db,user,1)
 if policy:raise RuntimeError('Unexpected existing access policy on brand-new QA user')
 db.add(AccessPolicy(user_id=user.id,company_id=1,grants=grants,status='active',version=1,updated_by=actor.id))
 db.add(AccessMembership(user_id=user.id,company_id=1,active=True,is_admin=False))
 db.add(BranchPolicy(user_id=user.id,company_id=1,all_branches=False,manage_access=False,use_home_branch=False,version=1))
 db.add(BranchGrant(user_id=user.id,company_id=1,branch_id=branch.id,can_write=True))
 service.audit(db,actor,1,'user.qa.created','User-authorized temporary local login for mobile Add Service verification',target=user.id,after={'modules':['srm'],'actions':['view','create'],'branch_id':branch.id,'is_superuser':False})
 db.commit()
 data={'id':user.id,'email':email,'password':password,'company_id':1,'branch_id':branch.id}
 (BASE/'qa-login.json').write_text(json.dumps(data));(BASE/'qa-login.json').chmod(0o600)
 print(json.dumps({'qa_user_id':user.id,'account_created':True,'is_superuser':False,'module':'srm','actions':['view','create'],'will_disable_after_check':True}))
