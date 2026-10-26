"""Public applications do not create employee accounts until HRMS approves them."""
from app.access.catalog import permission_objects
import base64
import hashlib
from datetime import date, datetime, timezone, timedelta
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile, Form, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator, field_validator, ValidationInfo
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import get_password_hash, verify_password
from app.models.user import User, Role, LoginAttempt
from app.models.employee import Employee, EmployeeEducation, EmployeeSkill
from app.models.company import Branch, Department, Designation
from app.api.v1.auth import _validate_password_policy, _check_ip_policy, _log_attempt
from .models import InternApplication
from .management_models import ApplicationEvent,ApplicationDocument
from app.apps.srm.services.commercial import tenant
from app.core.input_validation import NationalPhone,CallingCode,EmailAddress,CONTRACT,clean_text,identity_number,national_phone,calling_code

router = APIRouter()


def today():
    return datetime.now(ZoneInfo(settings.CELERY_TIMEZONE)).date()


def application_admin(user=Depends(get_current_user)):
    role = user.role.name.lower() if user.role else ""
    permissions = {p.name for p in permission_objects(user)}
    if not user.is_superuser and not permissions.intersection({'employee_create','intern_management_manage'}):
        raise HTTPException(403, "HRMS recruitment approval permission required")
    if user.employee and (user.employee.employment_type or "").lower() == "intern":
        raise HTTPException(403, "Interns cannot review applications")
    return user


class ApplicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=1, max_length=160)
    parent_name: str = Field(min_length=1, max_length=160)
    mobile: NationalPhone
    mobile_country_code: CallingCode
    email: EmailAddress = Field(max_length=150)
    identity_type: Literal["Aadhaar", "PAN", "Voter ID", "Passport", "Other"]
    identity_number: str = Field(min_length=4, max_length=40)
    gender: Literal["Male", "Female", "Other"]
    date_of_birth: date
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    tenth_marks: float = Field(ge=0, le=100)
    twelfth_marks: float | None = Field(None, ge=0, le=100)
    degree: str = Field(min_length=1, max_length=100)
    current_year: str = Field(min_length=1, max_length=50)
    college: str = Field(min_length=2, max_length=200)
    specialization: str = Field(min_length=1, max_length=150)
    passout_year: int = Field(ge=1970, le=2100)
    area_of_interest: str = Field(min_length=1, max_length=150)
    skills: str = Field(min_length=1, max_length=1000)
    role: str = Field(min_length=1, max_length=150)
    mode: Literal["On-site", "Remote", "Hybrid"]
    available_from: date
    duration: Literal["1 Month", "2 Months", "3 Months", "6 Months", "12 Months"]
    address: str = Field(min_length=5, max_length=200)
    linkedin: HttpUrl | None = None
    emergency_contact: NationalPhone
    emergency_contact_country_code: CallingCode
    password: str = Field(min_length=8, max_length=72)
    employment_type: Literal["Intern","Full-time","Part-time","Contract"]="Intern"
    department: str=Field("",max_length=150)
    portfolio: HttpUrl|None=None
    github: HttpUrl|None=None
    document_tokens:list[str]=Field(default_factory=list,max_length=10)
    consent: Literal[True]

    @field_validator("full_name", "parent_name", "city", "state", "college", "specialization", "skills", "role", "address", mode="before")
    @classmethod
    def trim_text(cls, value):
        return clean_text(value,1500,multiline=True) if isinstance(value,str) else value

    @field_validator('full_name','parent_name','city','state','college','specialization','skills','role')
    @classmethod
    def plain_text(cls,value):return clean_text(value,1000)

    @field_validator('tenth_marks','twelfth_marks',mode='before')
    @classmethod
    def percentage(cls,value):
        if value is None:return value
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not __import__('math').isfinite(value):raise ValueError('Enter a finite percentage from 0 to 100')
        return value

    @field_validator('skills')
    @classmethod
    def skill_items(cls,value):
        items=[item.strip() for item in value.split(',')]
        if len(items)>30 or any(not item or len(item)>80 for item in items):raise ValueError('Enter up to 30 comma-separated skills, each 1–80 characters')
        return ', '.join(dict.fromkeys(items))

    @field_validator('identity_number')
    @classmethod
    def valid_identity(cls,value,info: ValidationInfo):
        return identity_number(info.data.get('identity_type'),value)

    @field_validator('state','degree','current_year','area_of_interest')
    @classmethod
    def valid_choice(cls,value,info: ValidationInfo):
        key={'state':'states','degree':'degrees','current_year':'current_years','area_of_interest':'areas'}[info.field_name]
        if value not in CONTRACT[key]:raise ValueError('Select a supported option')
        return value

    @field_validator('date_of_birth','available_from')
    @classmethod
    def valid_date(cls,value,info: ValidationInfo):
        if info.field_name=='date_of_birth' and value>=today():raise ValueError('Date of birth must be in the past')
        if info.field_name=='available_from' and value<today():raise ValueError('Availability must be today or later')
        return value

    @field_validator('passout_year')
    @classmethod
    def valid_passout(cls,value,info: ValidationInfo):
        if info.data.get('current_year')=='Graduated' and value>today().year:raise ValueError('A completed degree cannot have a future pass-out year')
        return value



def receipt(item, db):
    employee = db.get(Employee, item.employee_id) if item.employee_id else None
    return {"lifecycle":item.lifecycle,"history":[{"state":e.state,"note":e.note,"created_at":e.created_at} for e in db.query(ApplicationEvent).filter_by(application_id=item.id).order_by(ApplicationEvent.id)],"reference": item.reference, "status": item.status, "intern_id": employee.employee_id if employee else None,
            "review_note": item.review_note, "can_login": item.status == "Approved" and employee is not None and employee.status in {"Active", "Probation"} and employee.deleted_at is None and bool(employee.user and employee.user.is_active)}


@router.get("/application-options")
def options(db: Session = Depends(get_db)):
    return {"roles": application_settings(db, settings.INTERN_HUB_ORGANIZATION_ID)["roles"], "validation": CONTRACT, "today": str(today())}


DEFAULT_APPLICATION_ROLES = ["Software Development Intern", "Software Testing Intern", "Web Development Intern", "AI / ML Intern", "Mobile Application Intern", "Data Analytics Intern", "Regular Employee", "Other"]


def application_settings(db, organization_id):
    from app.shared.models import ServicePolicy
    policy = db.query(ServicePolicy).filter_by(scope_key=f"intern-recruitment:{organization_id}", organization_id=organization_id).first()
    if policy:
        return {"roles": policy.values_json.get("roles", []), "version": policy.version}
    existing = db.query(Designation.name).join(Department, Designation.department_id == Department.id).join(Branch, Department.branch_id == Branch.id).filter(Branch.company_id == organization_id, Designation.is_active.is_(True), Designation.name.ilike("%intern%")).all()
    return {"roles": sorted(set(DEFAULT_APPLICATION_ROLES + [row[0] for row in existing])), "version": 0}


class ApplicationSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roles: list[str] = Field(max_length=100)
    version: int = Field(ge=0)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, roles):
        cleaned = [clean_text(role, 150) for role in roles]
        if len({role.casefold() for role in cleaned}) != len(cleaned):
            raise ValueError("Role names must be unique")
        return cleaned


@router.get("/admin/application-settings")
def get_application_settings(db: Session = Depends(get_db), user=Depends(application_admin)):
    return application_settings(db, tenant(user))


@router.put("/admin/application-settings")
def save_application_settings(data: ApplicationSettingsInput, db: Session = Depends(get_db), user=Depends(application_admin)):
    from app.shared.models import ServicePolicy
    organization = tenant(user)
    key = f"intern-recruitment:{organization}"
    policy = db.query(ServicePolicy).filter_by(scope_key=key, organization_id=organization).with_for_update().first()
    if data.version != (policy.version if policy else 0):
        raise HTTPException(409, "Application roles changed; reload before saving")
    if policy:
        policy.values_json = {"roles": data.roles}
        policy.version += 1
        policy.updated_by = user.id
    else:
        db.add(ServicePolicy(scope_key=key, organization_id=organization, module_key="interns_hub", kind="recruitment", values_json={"roles": data.roles}, version=1, updated_by=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Application roles changed; reload before saving") from None
    return application_settings(db, organization)


@router.post("/applications", status_code=201)
def apply(data: ApplicationInput, request: Request, db: Session = Depends(get_db)):
    if data.role not in options(db)['roles']:raise HTTPException(422,detail=[{'loc':['body','role'],'msg':'Select an active supported role','type':'value_error'}])
    _check_ip_policy(db, request)
    _validate_password_policy(db, data.password)
    email = str(data.email).lower()
    if db.query(InternApplication.id).filter_by(email=email).first() or db.query(User.id).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "An application or account already exists for this email. Check your application status or sign in.")
    digest = hashlib.sha256(("intern-application:" + settings.SECRET_KEY).encode()).digest()
    cipher = Fernet(base64.urlsafe_b64encode(digest))
    item = InternApplication(organization_id=settings.INTERN_HUB_ORGANIZATION_ID, reference="APP-" + uuid4().hex[:16].upper(), email=email, full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        details=jsonable_encoder(data.model_dump(exclude={"email", "full_name", "password", "identity_number", "document_tokens"})),
        identity_number_encrypted=cipher.encrypt(data.identity_number.encode()).decode(), identity_last4=data.identity_number[-4:], status="Pending")
    try:
        db.add(item);db.flush()
        from .application_documents import claim
        claim(db,item,data.document_tokens)
        db.add_all([ApplicationEvent(application_id=item.id,state='Registered',note='Applicant consent recorded'),ApplicationEvent(application_id=item.id,state='Pending Verification')])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An application already exists for this email")
    return receipt(item, db)


class StatusInput(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=72)


@router.post("/applications/status")
def status(data: StatusInput, request: Request, db: Session = Depends(get_db)):
    _check_ip_policy(db, request)
    email = str(data.email).lower()
    recent = db.query(LoginAttempt).filter(LoginAttempt.email == email, LoginAttempt.failure_reason == "Application status verification failed", LoginAttempt.created_at >= datetime.now(timezone.utc) - timedelta(minutes=15)).count()
    if recent >= 10:
        raise HTTPException(423, "Too many attempts. Please try again later.")
    item = db.query(InternApplication).filter_by(email=email).first()
    account = db.query(User).filter(func.lower(User.email) == email).first() if item and item.status == "Approved" else None
    hashed = account.hashed_password if account else item.password_hash if item else get_password_hash("unknown-application")
    verified = verify_password(data.password, hashed)
    if not item or not verified:
        _log_attempt(db, None, email, False, "Application status verification failed", request)
        db.commit()
        raise HTTPException(401, "Application details could not be verified")
    return receipt(item, db)


@router.get("/admin/applications")
def applications(page:int=Query(1,ge=1),per_page:int=Query(100,ge=1,le=200),user=Depends(application_admin), db: Session = Depends(get_db)):
    items = db.query(InternApplication).filter(InternApplication.organization_id==tenant(user)).order_by(InternApplication.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    return [{"id": i.id, "reference": i.reference, "email": i.email, "full_name": i.full_name, "details": i.details,
             "documents":[{"id":d.id,"name":d.name,"category":d.category,"size":d.size} for d in db.query(ApplicationDocument).filter_by(application_id=i.id)],"identity_last4": i.identity_last4, "created_at": i.created_at, **receipt(i, db)} for i in items]


class DecisionInput(BaseModel):
    status: Literal["Approved", "Rejected", "Correction Requested"]
    branch_id: int | None = None
    department_id: int | None = None
    designation_id: int | None = None
    reporting_manager_id: int | None = None
    date_of_joining: date | None = None
    review_note: str = Field("", max_length=2000)


@router.post("/admin/applications/{application_id}/decision")
def decide(application_id: int, data: DecisionInput, user=Depends(application_admin), db: Session = Depends(get_db)):
    item = db.query(InternApplication).filter_by(id=application_id,organization_id=tenant(user)).with_for_update().first()
    if not item:
        raise HTTPException(404, "Application not found")
    if item.status not in {"Pending","Correction Requested"}:
        raise HTTPException(409, "This application has already been reviewed")
    if data.status != "Approved" and not data.review_note.strip():raise HTTPException(422,"A rejection/correction reason is required")
    if data.status == "Approved":
        if not all([data.branch_id, data.department_id, data.designation_id, data.reporting_manager_id, data.date_of_joining]):
            raise HTTPException(422, "Assign a branch, department, designation, manager and joining date")
        branch = db.get(Branch, data.branch_id)
        department = db.get(Department, data.department_id)
        designation = db.get(Designation, data.designation_id)
        manager = db.get(Employee, data.reporting_manager_id)
        if not branch or branch.company_id!=tenant(user) or not department or department.branch_id != branch.id or not designation or designation.department_id != department.id:
            raise HTTPException(422, "Choose a department and designation belonging to the selected branch")
        if manager and manager.branch and manager.branch.company_id!=tenant(user):raise HTTPException(403,"Manager is outside this organization")
        if not manager or manager.deleted_at or manager.status not in {"Active", "Probation"} or (manager.employment_type or "").lower() == "intern":
            raise HTTPException(422, "Choose an active employee as reporting manager")
        if db.query(User.id).filter(func.lower(User.email) == item.email).first():
            raise HTTPException(409, "An account with this email already exists. Resolve it before approval.")
        is_intern=item.details.get("employment_type","Intern")=="Intern"
        role_name="intern" if is_intern else "employee"
        role = db.query(Role).filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description="HRMS approved account", is_system=True)
            db.add(role)
            db.flush()
        account = User(email=item.email, hashed_password=item.password_hash, role_id=role.id, is_active=True, is_superuser=False)
        db.add(account)
        db.flush()
        parts = item.full_name.split(maxsplit=1)
        details = item.details
        employee = Employee(employee_id="IH-" + uuid4().hex[:12].upper(), user_id=account.id,
            first_name=parts[0], last_name=parts[1] if len(parts) > 1 else "", employment_type=item.details.get("employment_type","Intern"), status="Active",
            date_of_joining=data.date_of_joining, branch_id=branch.id, department_id=department.id, designation_id=designation.id,
            reporting_manager_id=manager.id, personal_email=item.email, phone_number=details["mobile"],phone_number_country_code=details.get('mobile_country_code'),
            date_of_birth=date.fromisoformat(details["date_of_birth"]), gender=details["gender"],
            present_city=details["city"], present_state=details["state"], present_address=details["address"],
            emergency_contact_number=details["emergency_contact"],emergency_contact_number_country_code=details.get('emergency_contact_country_code'), family_information="Parent / Guardian: " + details["parent_name"], interests=details["area_of_interest"],
            work_location="Office" if details["mode"] == "On-site" else details["mode"])
        db.add(employee)
        db.flush()
        for degree, marks in [("10th Standard", details["tenth_marks"]), ("12th Standard", details.get("twelfth_marks"))]:
            if marks is not None:
                db.add(EmployeeEducation(employee_id=employee.id, degree=degree, percentage_cgpa=marks))
        db.add(EmployeeEducation(employee_id=employee.id, degree=details["degree"], specialization=details["specialization"], institution=details["college"], pass_year=details["passout_year"]))
        for skill in dict.fromkeys(s.strip()[:100] for s in details["skills"].split(",") if s.strip()):
            db.add(EmployeeSkill(employee_id=employee.id, skill_name=skill))
        from app.apps.hrms.services.identity import HrmsIdentityService
        HrmsIdentityService.sync_employee_identity(db, employee)
        item.employee_id = employee.id
    item.lifecycle='Active' if data.status=='Approved' else data.status
    states=['Approved','Onboarded','Active'] if data.status=='Approved' else [data.status]
    for state in states:db.add(ApplicationEvent(application_id=item.id,actor_user_id=user.id,state=state,note=data.review_note))
    item.status = data.status
    if data.status == "Approved":
        from app.common.services.profiles import seed_application_profile
        seed_application_profile(db, employee, item)
    item.review_note = data.review_note
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "The application was updated concurrently. Refresh and try again.")
    return receipt(item, db)


@router.post('/application-uploads',status_code=201)
def upload_application_document(request:Request,file:UploadFile=File(...),category:str=Form(...),db:Session=Depends(get_db)):
    from .application_documents import upload_document
    from app.core.middleware.audit import client_addresses
    source,_,_=client_addresses(request)
    return upload_document(db,file,category,source or 'unknown')

@router.get('/admin/applications/documents/{document_id}')
def application_document(document_id:int,user=Depends(application_admin),db:Session=Depends(get_db)):
    from app.core.storage import FileResponse
    row=db.query(ApplicationDocument).join(InternApplication,InternApplication.id==ApplicationDocument.application_id).filter(ApplicationDocument.id==document_id,InternApplication.organization_id==tenant(user)).first()
    if not row:raise HTTPException(404,'Document not found')
    return FileResponse(row.storage_path,filename=row.name,media_type='application/octet-stream')

class CorrectionInput(BaseModel):
    credentials:StatusInput
    application:ApplicationInput

@router.post('/applications/corrections')
def correct_application(data:CorrectionInput,request:Request,db:Session=Depends(get_db)):
    status(data.credentials,request,db)
    item=db.query(InternApplication).filter_by(email=str(data.credentials.email).lower()).with_for_update().one()
    if item.status!='Correction Requested':raise HTTPException(409,'Corrections have not been requested')
    if str(data.application.email).lower()!=item.email:raise HTTPException(422,'Keep the registered email')
    if data.application.role not in options(db)['roles']:raise HTTPException(422,detail=[{'loc':['body','role'],'msg':'Select an active supported role','type':'value_error'}])
    details=data.application.model_dump(exclude={'email','full_name','password','identity_number','document_tokens'})
    item.details=jsonable_encoder(details);item.full_name=data.application.full_name
    digest=hashlib.sha256(('intern-application:'+settings.SECRET_KEY).encode()).digest()
    item.identity_number_encrypted=Fernet(base64.urlsafe_b64encode(digest)).encrypt(data.application.identity_number.encode()).decode();item.identity_last4=data.application.identity_number[-4:]
    from .application_documents import claim
    claim(db,item,data.application.document_tokens)
    item.status='Pending';item.lifecycle='Pending Verification'
    db.add(ApplicationEvent(application_id=item.id,state='Pending Verification',note='Applicant submitted corrections'))
    db.commit();return receipt(item,db)

class LifecycleInput(BaseModel):
    state:Literal['Suspended','Inactive','Completed','Exited','Active']
    note:str=Field(min_length=1,max_length=2000)

@router.post('/admin/applications/{application_id}/lifecycle')
def lifecycle(application_id:int,data:LifecycleInput,user=Depends(application_admin),db:Session=Depends(get_db)):
    item=db.query(InternApplication).filter_by(id=application_id,organization_id=tenant(user)).with_for_update().first()
    if not item or not item.employee_id:raise HTTPException(404,'Onboarded application not found')
    employee=db.get(Employee,item.employee_id);account=employee.user
    item.lifecycle=data.state;employee.status='Active' if data.state=='Active' else 'Inactive'
    if account:
        account.is_active=data.state=='Active'
        if not account.is_active:
            from app.models.user import UserSession
            db.query(UserSession).filter_by(user_id=account.id).update({'status':'Revoked'},synchronize_session=False)
    db.add(ApplicationEvent(application_id=item.id,actor_user_id=user.id,state=data.state,note=data.note));db.commit();return receipt(item,db)
