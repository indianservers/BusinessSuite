from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.access.service import primary_company
from app.apps.saas.models import TenantSubscriptionPlan, TenantSubscription

router = APIRouter(prefix="/onboarding", tags=["Approved trial onboarding"])


def plan_for(db, user):
    subscription = db.query(TenantSubscription).filter_by(company_id=primary_company(user)).first()
    plan = db.get(TenantSubscriptionPlan, subscription.plan_id) if subscription else None
    receipt = (plan.config_json or {}).get("platform_provisioning", {}) if plan else {}
    return plan if receipt.get("user_id") == user.id and receipt.get("signin_ready") else None


@router.get("")
def read(user=Depends(get_current_user),db:Session=Depends(get_db)):
    plan=plan_for(db,user)
    if not plan:
        return {"available":False}
    subscription=db.query(TenantSubscription).filter_by(company_id=primary_company(user),plan_id=plan.id).one()
    completed=subscription.config_json.get("onboarding",{})
    links={"hrms":"/hrms","crm":"/crm","project_management":"/pms","srm":"/srm","fam":"/fam"}
    return {"available":True,"completed":completed,"modules":[{"key":m,"url":links[m]} for m in plan.config_json.get("modules",[]) if m in links],
            "sample_data_requested":plan.config_json.get("sample_data_requested",False),"done":bool(completed.get("dismissed"))}


class Complete(BaseModel):
    step:str=Field(pattern="^(profile|team|first_action|sample_data|dismissed)$")
    complete:bool=True


@router.post("")
def update(data:Complete,user=Depends(get_current_user),db:Session=Depends(get_db)):
    plan=plan_for(db,user)
    if not plan:
        raise HTTPException(404,"No signup onboarding is available for this account")
    from app.platform_owner import service as s
    subscription=db.query(TenantSubscription).filter_by(company_id=primary_company(user),plan_id=plan.id).with_for_update().one()
    completed={**subscription.config_json.get("onboarding",{}),data.step:s.now().isoformat() if data.complete else None}
    subscription.config_json={**subscription.config_json,"onboarding":completed}
    db.commit()
    return read(user,db)
