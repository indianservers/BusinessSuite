"""Validate changed API-owned contact values, including imports and generic resources."""
from sqlalchemy import event,inspect,Float,Numeric
import math
from urllib.parse import urlsplit
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.audit_context import context
from app.core.input_validation import PHONE_FIELDS,national_phone,calling_code,email_address,clean_text


def contact_issues(record):
    result={}
    try:columns=inspect(type(record)).columns
    except Exception:return result
    for field in columns.keys():
        if field not in PHONE_FIELDS or not getattr(record,field,None):continue
        try:
            national_phone(getattr(record,field));calling_code(getattr(record,field+'_country_code',None))
        except ValueError:result[field]='Legacy phone needs correction: select its country code and enter exactly 10 ASCII digits.'
    return result


def validate_api_contacts(session,flush_context,instances):
    request=context.get()
    # Include signed public ingestion as well as authenticated CRUD.
    # Fixture loading and historical migrations have no HTTP request context.
    if not request:return
    errors=[]
    for record in session.new.union(session.dirty):
        # Audit evidence must preserve attempted values and historical actor identity.
        if getattr(record,'__tablename__','') in {'audit_logs','audit_log_tasks','field_audit_events','login_attempts'}:continue
        state=inspect(record);columns=state.mapper.columns
        for field in columns.keys():
            changed=record in session.new or state.attrs[field].history.has_changes()
            if field in PHONE_FIELDS:
                code_field=field+'_country_code'
                if code_field not in columns:continue
                changed=changed or state.attrs[code_field].history.has_changes()
                value=getattr(record,field,None)
                if changed and getattr(record,code_field,None) not in (None,''):
                    try:calling_code(getattr(record,code_field))
                    except ValueError as exc:errors.append({'loc':['body',code_field],'msg':str(exc),'type':'value_error'})
                if changed and value not in (None,''):
                    try:national_phone(value);calling_code(getattr(record,code_field,None))
                    except ValueError as exc:errors.append({'loc':['body',field],'msg':str(exc),'type':'value_error'})
            elif changed and (field=='email' or field.endswith('_email')):
                value=getattr(record,field,None)
                if value not in (None,''):
                    try:
                        if field in {'to_email','cc_email','bcc_email'} and isinstance(value,str) and ',' in value:
                            value=', '.join(email_address(item.strip()) for item in value.split(','))
                        else:value=email_address(value)
                        maximum=getattr(columns[field].type,'length',None)
                        if maximum and len(value)>maximum:raise ValueError(f'Use {maximum} characters or fewer')
                        setattr(record,field,value)
                    except ValueError as exc:errors.append({'loc':['body',field],'msg':str(exc),'type':'value_error'})
            elif changed and (field in {'name','title','first_name','last_name','full_name','parent_name'} or field.endswith('_name')):
                value=getattr(record,field,None)
                if isinstance(value,str):
                    try:setattr(record,field,clean_text(value,getattr(columns[field].type,'length',None) or 500,required=not columns[field].nullable and field!='last_name'))
                    except ValueError as exc:errors.append({'loc':['body',field],'msg':str(exc),'type':'value_error'})
            elif changed and field in {'website','website_url','linkedin_url','portfolio_url','github_url','webhook_url'}:
                value=getattr(record,field,None)
                if value not in (None,''):
                    try:
                        if not isinstance(value,str) or len(value)>2048 or any(c.isspace() for c in value):raise ValueError()
                        parsed=urlsplit(value)
                        if parsed.scheme not in {'http','https'} or not parsed.hostname:raise ValueError()
                    except (TypeError,ValueError):errors.append({'loc':['body',field],'msg':'Enter a complete HTTP or HTTPS URL','type':'value_error'})
            elif changed and isinstance(columns[field].type,(Float,Numeric)) and getattr(record,field,None) is not None:
                try:
                    if not math.isfinite(getattr(record,field)):raise ValueError('Enter a finite number')
                except (TypeError,ValueError,OverflowError):errors.append({'loc':['body',field],'msg':'Enter a finite number','type':'value_error'})
    if errors:raise HTTPException(422,detail=errors)


def install():
    if not event.contains(Session,'before_flush',validate_api_contacts):event.listen(Session,'before_flush',validate_api_contacts)
