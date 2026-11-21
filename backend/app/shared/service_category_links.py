"""Both catalog and HRMS edit the same branch-scoped service policy."""
from typing import Annotated, Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.shared.employee_categories import WorkCategories

class StaffChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_resource_id: Annotated[int, Field(strict=True, gt=0)]
    employee_id: Annotated[int, Field(strict=True, gt=0)]
    active: bool = True
    expected_revision: Annotated[int, Field(strict=True, gt=0)] | None = None


class SchedulingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["none","optional","required"] = "none"
    duration: Annotated[int,Field(strict=True,ge=5,le=720)] = 30
    employee_categories: WorkCategories = Field(default_factory=list)
    expected_revision: Annotated[int,Field(strict=True,gt=0)] | None = None
    staff_changes: list[StaffChange] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_staff_changes(self):
        if len({change.provider_resource_id for change in self.staff_changes}) != len(self.staff_changes):
            raise ValueError("Each staff assignment can be changed once")
        return self

class ServiceLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: Annotated[int,Field(strict=True,gt=0)]
    category_ids: list[Annotated[str,Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]] = Field(max_length=20)
    expected_revision: Annotated[int,Field(strict=True,gt=0)] | None = None

def current_policy(db,actor,service_id,write=False):
    from app.apps.srm.service_checkout import _authority,_scope,_source_scope
    from app.apps.srm.service_checkout_models import ServiceBookingPolicy
    company,branch,scope=_authority(db,actor,configuration=write,write=write)
    query=_scope(db.query(ServiceBookingPolicy),ServiceBookingPolicy,company,branch,scope).filter_by(service_product_id=service_id)
    row=(query.with_for_update().populate_existing() if write else query).first()
    if row:_source_scope(db,scope,company,branch,type(row),row.id)
    return row

def save_scheduling(db,actor,service_id,data):
    from app.apps.srm.service_checkout import save_eligibility, save_policy
    from app.apps.srm.service_checkout_schemas import EligibilityInput, PolicyInput
    from app.shared.employee_category_taxonomy import options
    row=current_policy(db,actor,service_id,write=True)
    valid=set(options(db,actor)["items"]) | set(row.employee_categories or [] if row else [])
    if any(value not in valid for value in data.employee_categories):
        raise HTTPException(422,"Select existing active employee categories and subcategories")
    result=save_policy(PolicyInput(service_product_id=service_id,expected_revision=data.expected_revision,
        default_duration_minutes=data.duration,
        min_duration_minutes=min(row.min_duration_minutes,data.duration) if row else 5,
        max_duration_minutes=max(row.max_duration_minutes,data.duration) if row else 720,
        allow_duration_override=row.allow_duration_override if row else False,
        employee_categories=data.employee_categories,active=data.mode!="none",booking_required=data.mode=="required"),db,actor,commit=False)
    for change in data.staff_changes:
        save_eligibility(
            EligibilityInput(policy_id=result["id"], expected_policy_revision=result["revision"], **change.model_dump()),
            db, actor, commit=False, catalog_configuration=True,
        )
    return {**data.model_dump(exclude={"staff_changes"}), "expected_revision":result["revision"]}

def catalog_scheduling(db,actor,data,result):
    if data.service_scheduling is None:return result
    if data.kind!="service":raise HTTPException(422,"Scheduling belongs to a service")
    return {**result,"service_scheduling":save_scheduling(db,actor,result["id"],data.service_scheduling)}

def service_choices(db,actor,search="",page=1,per_page=50):
    from app.shared.catalog import list_items
    from app.shared.employee_category_taxonomy import options
    tree=options(db,actor)["categories"]
    values={node["value"]:node["id"] for category in tree for node in [category,*category["children"]]}
    result=list_items(source="srm",kind="service",search=search,category="",status="Active",workspace_id=None,sort="name",direction="asc",page=page,per_page=per_page,tag="",item_keys=None,key_order=False,include_facets=False,price_book_id=None,db=db,user=actor)
    from app.apps.srm.service_checkout import _authority,_scope,_source_scope
    from app.apps.srm.service_checkout_models import ServiceBookingPolicy
    company,branch,scope=_authority(db,actor,write=False)
    policies={p.service_product_id:p for p in _scope(db.query(ServiceBookingPolicy),ServiceBookingPolicy,company,branch,scope).filter(ServiceBookingPolicy.service_product_id.in_([item['id'] for item in result['items']])).all()}
    rows=[]
    # Read and write authority is checked independently: HRMS viewing does not grant SRM writes.
    for item in result["items"]:
        policy=policies.get(item["id"])
        if policy:_source_scope(db,scope,company,branch,type(policy),policy.id)
        rows.append({"id":item["id"],"name":item["name"],"code":item["code"],"category_ids":[values[name] for name in (policy.employee_categories or [] if policy else []) if name in values],
            "revision":policy.revision if policy else None,"duration":policy.default_duration_minutes if policy else 30,
            "mode":("required" if policy.booking_required else "optional") if policy and policy.active else "none"})
    return {"items":rows,"total":result["total"],"pages":result["pages"],"page":page}

def save_links(db,actor,links,tree):
    names={node["id"]:node["value"] for category in tree for node in [category,*category["children"]] if category["active"] and node["active"]}
    for link in links:
        if any(ident not in names for ident in link.category_ids):raise HTTPException(422,"Select active employee categories")
        row=current_policy(db,actor,link.service_id,write=True)
        data=SchedulingInput(mode=("required" if row.booking_required else "optional") if row and row.active else "none",duration=row.default_duration_minutes if row else 30,
            employee_categories=[names[ident] for ident in dict.fromkeys(link.category_ids)],expected_revision=link.expected_revision)
        save_scheduling(db,actor,link.service_id,data)
