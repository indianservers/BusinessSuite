"""Personal calendar preferences, timed events and availability."""
import math
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSPlannerPreference, PMSCalendarEvent, PMSWorkspaceMember, PMSTask
from .access import get_project_for_action
from .workspaces import workspace_member

router = APIRouter()
UTC = timezone.utc

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Section(Strict):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,40}$")
    title: str = Field(min_length=1, max_length=60)
    enabled: bool = True
    filter: Literal["priorities", "people", "assigned", "overdue", "backlog", "high_priority"]
    @field_validator("title")
    @classmethod
    def title_required(cls,value):
        if not value.strip(): raise ValueError("Section name is required")
        return value.strip()

class WorkDay(Strict):
    day: int = Field(ge=0, le=6)  # Python Monday = 0
    enabled: bool = True
    start: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(default="17:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    @model_validator(mode="after")
    def valid(self):
        if self.enabled and self.end <= self.start:
            raise ValueError("Workday end must be later than start")
        return self

class Preferences(Strict):
    grid_size: Literal["default", "large", "xl"] = "default"
    event_style: Literal["subtle", "solid"] = "subtle"
    duration: Literal[15, 30, 45, 60, 90, 120] = 60
    color_by: Literal["project", "status", "priority"] = "project"
    week_start: int = Field(default=0, ge=0, le=6)  # JavaScript Sunday = 0
    timezone: str = "UTC"
    weekends: bool = True
    week_numbers: bool = False
    show_event_details: bool = True
    show_time_left: bool = True
    browser_reminders: bool = False
    quick_join: Literal[1, 2, 5, 10, 15] = 2
    show_task_dates: bool = True
    task_scope: Literal["all", "mine"] = "all"
    closed_tasks: bool = True
    recurring: bool = False
    default_project: int | None = Field(default=None, gt=0)
    prefix: str = Field(default="Work on", max_length=60)
    focus_visibility: Literal["private", "workspace"] = "private"
    workdays: list[WorkDay] = Field(default_factory=lambda: [WorkDay(day=i, enabled=i<5) for i in range(7)], min_length=7, max_length=7)
    sections: list[Section] = Field(default_factory=lambda: [Section(id=v, title=n, filter=v) for v,n in [("priorities","Priorities"),("people","People"),("assigned","Assigned to me"),("overdue","Today & overdue"),("backlog","Backlog")]], max_length=12)
    notes_name: str = Field(default="Meeting notes", max_length=100)
    notes_template: str = Field(default="Agenda\n\nDecisions\n\nAction items", max_length=4000)
    @field_validator("timezone")
    @classmethod
    def zone(cls, value):
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError): raise ValueError("Choose a valid IANA timezone")
        return value
    @model_validator(mode="after")
    def valid(self):
        if {w.day for w in self.workdays} != set(range(7)):
            raise ValueError("Supply each weekday once")
        if len({s.id for s in self.sections}) != len(self.sections):
            raise ValueError("Sidebar section IDs must be unique")
        return self

class PreferenceSave(Strict):
    revision: int = Field(ge=0)
    preferences: Preferences


def prefs_output(row):
    return {"revision": row.revision if row else 0, "preferences": Preferences.model_validate(row.payload).model_dump() if row else Preferences().model_dump()}

@router.get('/planner/preferences')
def preferences(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    return prefs_output(db.get(PMSPlannerPreference, user.id))

@router.put('/planner/preferences')
def save_preferences(data: PreferenceSave, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if data.preferences.default_project:
        get_project_for_action(db, data.preferences.default_project, user, 'manage_tasks')
    row = db.get(PMSPlannerPreference, user.id)
    if (row.revision if row else 0) != data.revision:
        raise HTTPException(409, "Calendar preferences changed. Reload before saving.")
    if row:
        changed = db.execute(update(PMSPlannerPreference).where(PMSPlannerPreference.user_id==user.id, PMSPlannerPreference.revision==data.revision).values(payload=data.preferences.model_dump(), revision=data.revision+1)).rowcount
        if not changed: raise HTTPException(409, "Calendar preferences changed. Reload before saving.")
    else:
        db.add(PMSPlannerPreference(user_id=user.id, revision=1, payload=data.preferences.model_dump()))
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Calendar preferences changed. Reload before saving.")
    db.expire_all()
    return prefs_output(db.get(PMSPlannerPreference,user.id))

class EventInput(Strict):
    title: str = Field(min_length=1, max_length=220)
    description: str = Field(default="", max_length=10000)
    start_at: datetime
    end_at: datetime
    timezone: str = "UTC"
    kind: Literal["meeting", "focus"] = "meeting"
    visibility: Literal["private", "workspace"] = "private"
    workspace_id: int | None = Field(default=None, gt=0)
    task_id: int | None = Field(default=None, gt=0)
    meeting_url: str = Field(default="", max_length=2000)
    @model_validator(mode="after")
    def valid(self):
        if not self.title.strip(): raise ValueError("Title is required")
        if not self.start_at.tzinfo or not self.end_at.tzinfo: raise ValueError("Event dates require timezone offsets")
        if self.end_at <= self.start_at or self.end_at-self.start_at > timedelta(days=7): raise ValueError("Event duration must be positive and at most 7 days")
        try: ZoneInfo(self.timezone)
        except (ValueError,ZoneInfoNotFoundError): raise ValueError("Invalid timezone")
        if self.visibility=='workspace' and not self.workspace_id: raise ValueError("Workspace visibility requires a workspace")
        if self.meeting_url:
            url=urlparse(self.meeting_url)
            if url.scheme!='https' or not url.hostname or url.username or url.password: raise ValueError("Meeting link must be a valid HTTPS URL without credentials")
        self.title=self.title.strip()
        return self

class EventSave(EventInput):
    revision: int = Field(ge=1)


def event_scope(db,user):
    workspace_ids=db.query(PMSWorkspaceMember.workspace_id).filter(PMSWorkspaceMember.user_id==user.id)
    return db.query(PMSCalendarEvent).filter(or_(PMSCalendarEvent.owner_id==user.id, (PMSCalendarEvent.visibility=='workspace') & PMSCalendarEvent.workspace_id.in_(workspace_ids)))


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def event_output(event,user):
    return {**{key:getattr(event,key) for key in ['id','title','description','timezone','kind','visibility','workspace_id','task_id','meeting_url','revision','owner_id']}, 'start_at':aware(event.start_at).isoformat(), 'end_at':aware(event.end_at).isoformat(), 'can_edit':event.owner_id==user.id}


def validate_scope(db,user,data):
    if data.workspace_id:
        _,member=workspace_member(db,data.workspace_id,user)
        if member.role=='Guest': raise HTTPException(403,"Guests cannot create workspace calendar events")
    if data.task_id:
        task=db.query(PMSTask).filter_by(id=data.task_id,deleted_at=None).first()
        if not task: raise HTTPException(404,"Task not found")
        project=get_project_for_action(db,task.project_id,user)
        if data.visibility=='workspace' and project.workspace_id!=data.workspace_id: raise HTTPException(422,"The linked task must belong to the event workspace")

@router.get('/planner/events')
def list_events(start: datetime, end: datetime, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if not start.tzinfo or not end.tzinfo or end<=start or end-start>timedelta(days=370): raise HTTPException(422,"Choose a timezone-aware range of at most 370 days")
    rows=event_scope(db,user).filter(PMSCalendarEvent.start_at<end.astimezone(UTC),PMSCalendarEvent.end_at>start.astimezone(UTC)).order_by(PMSCalendarEvent.start_at).limit(2001).all()
    if len(rows)>2000: raise HTTPException(422,"Narrow the date range to fewer than 2,000 events")
    return [event_output(e,user) for e in rows]

@router.post('/planner/events',status_code=201)
def create_event(data: EventInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    validate_scope(db,user,data)
    event=PMSCalendarEvent(owner_id=user.id,**{**data.model_dump(),'start_at':data.start_at.astimezone(UTC),'end_at':data.end_at.astimezone(UTC)})
    db.add(event);db.commit();db.refresh(event)
    return event_output(event,user)

@router.put('/planner/events/{event_id}')
def edit_event(event_id:int,data:EventSave,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    event=db.query(PMSCalendarEvent).filter_by(id=event_id,owner_id=user.id).first()
    if not event: raise HTTPException(404,"Event not found")
    validate_scope(db,user,data)
    values=data.model_dump(exclude={'revision'});values.update(start_at=data.start_at.astimezone(UTC),end_at=data.end_at.astimezone(UTC),revision=data.revision+1)
    if not db.execute(update(PMSCalendarEvent).where(PMSCalendarEvent.id==event_id,PMSCalendarEvent.owner_id==user.id,PMSCalendarEvent.revision==data.revision).values(**values)).rowcount:
        raise HTTPException(409,"Event changed. Reload before saving.")
    db.commit();db.refresh(event)
    return event_output(event,user)

@router.delete('/planner/events/{event_id}',status_code=204)
def delete_event(event_id:int,revision:int=Query(ge=1),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    event=db.query(PMSCalendarEvent).filter_by(id=event_id,owner_id=user.id).first()
    if not event: raise HTTPException(404,"Event not found")
    if not db.query(PMSCalendarEvent).filter_by(id=event_id,owner_id=user.id,revision=revision).delete(): raise HTTPException(409,"Event changed. Reload before deleting.")
    db.commit()

@router.get('/planner/free-slots')
def free_slots(day:date,minutes:int=Query(60,ge=15,le=240),timezone_name:str|None=Query(None,alias="timezone",max_length=80),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=db.get(PMSPlannerPreference,user.id);prefs=Preferences.model_validate(row.payload) if row else Preferences()
    try: zone=ZoneInfo(timezone_name or prefs.timezone)
    except (ValueError,ZoneInfoNotFoundError): raise HTTPException(422,"Invalid timezone")
    work=next(w for w in prefs.workdays if w.day==day.weekday())
    if not work.enabled:return []
    start=datetime.fromisoformat(f'{day}T{work.start}').replace(tzinfo=zone).astimezone(UTC)
    end=datetime.fromisoformat(f'{day}T{work.end}').replace(tzinfo=zone).astimezone(UTC)
    busy=event_scope(db,user).filter(PMSCalendarEvent.start_at<end,PMSCalendarEvent.end_at>start).all()
    result=[];cursor=max(start,datetime.now(UTC))
    cursor=datetime.fromtimestamp(math.ceil(cursor.timestamp()/900)*900,UTC)
    while cursor+timedelta(minutes=minutes)<=end and len(result)<8:
        last=cursor+timedelta(minutes=minutes)
        if not any(aware(e.start_at)<last and aware(e.end_at)>cursor for e in busy):result.append({'start_at':cursor.isoformat(),'end_at':last.isoformat()})
        cursor+=timedelta(minutes=15)
    return result

@router.get('/planner/connections')
def connections(user:User=Depends(get_current_user)):
    return {'calendar':'BusinessSuite','providers':[{'id':key,'name':name,'state':'not_configured','requirements':requirements} for key,name,requirements in [('google','Google Calendar',['OAuth client ID and secret','Verified redirect URL','Calendar scopes']),('outlook','Outlook Calendar',['Microsoft Entra app registration','Client secret','Calendar consent']),('zoom','Zoom',['Zoom OAuth app','Client credentials','Meeting scopes'])]]}
