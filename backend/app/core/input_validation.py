"""Central business input rules. Phone format does not establish ownership/existence."""
import json
import re
import unicodedata
import math
from pathlib import Path
from typing import Annotated
from pydantic import AfterValidator, StrictStr
from email_validator import validate_email, EmailNotValidError

CONTRACT=json.loads(Path(__file__).with_name('validation_contract.json').read_text(encoding='utf-8'))
CALLING_CODES={country['code'] for country in CONTRACT['countries']}
PHONE_ERROR=CONTRACT['phone_error']
PHONE_FIELDS={'mobile','mobile_number','phone','phone_number','alternate_phone','whatsapp_number','emergency_contact','emergency_contact_number','contact_phone','contact_number','business_phone_number','primary_phone','secondary_phone'}


def national_phone(value):
    if not isinstance(value,str) or len(value)!=CONTRACT['national_phone_length'] or not re.fullmatch(r'[0-9]+',value):raise ValueError(PHONE_ERROR)
    return value


def calling_code(value):
    if not isinstance(value,str) or value not in CALLING_CODES:raise ValueError('Select a supported country calling code')
    return value


NationalPhone=Annotated[StrictStr,AfterValidator(national_phone)]
CallingCode=Annotated[StrictStr,AfterValidator(calling_code)]


def email_address(value):
    if not isinstance(value,str) or len(value)>254 or any(char.isspace() for char in value):raise ValueError('Enter a valid email address without spaces')
    try:return validate_email(value,check_deliverability=False,allow_quoted_local=True).normalized
    except EmailNotValidError:raise ValueError('Enter a valid email address without spaces') from None


EmailAddress=Annotated[StrictStr,AfterValidator(email_address)]


def clean_text(value,maximum,required=True,multiline=False):
    if not isinstance(value,str):raise ValueError('Enter text')
    if any(unicodedata.category(char) in {'Cc','Cs'} and not (multiline and char in '\n\r\t') for char in value):raise ValueError('Remove control characters from this field')
    value=value.strip()
    if required and (not value or not any(unicodedata.category(char)[0] not in {'C','Z'} for char in value)):raise ValueError('This field is required')
    if len(value)>maximum:raise ValueError(f'Use {maximum} characters or fewer')
    return value


def identity_number(kind,value):
    if not isinstance(value,str) or value!=value.strip():raise ValueError('Enter the ID number without surrounding spaces')
    patterns={'Aadhaar':r'[0-9]{12}','PAN':r'[A-Z]{5}[0-9]{4}[A-Z]'}
    if kind in patterns and not re.fullmatch(patterns[kind],value):
        messages={'Aadhaar':'Enter the 12-digit Aadhaar number; format checking does not verify identity','PAN':'Enter five uppercase letters, four digits and one uppercase letter'}
        raise ValueError(messages[kind])
    # International passports and legacy voter documents vary; preserve as printed.
    return clean_text(value,40)


def full_phone(record,field):
    """Messaging/export consumers must not guess a code for an ambiguous legacy value."""
    value=getattr(record,field,None);code=getattr(record,field+'_country_code',None)
    if not value:return None
    try:return calling_code(code)+national_phone(value)
    except ValueError:return None


def contact_change_errors(changes,current=None):
    errors=[]
    for field in PHONE_FIELDS:
        code=field+'_country_code'
        if field not in changes and code not in changes:continue
        value=changes.get(field,getattr(current,field,None))
        if value in (None,''):continue
        try:national_phone(value);calling_code(changes.get(code,getattr(current,code,None)))
        except ValueError as exc:errors.append({'loc':['body',field],'msg':str(exc),'type':'value_error'})
    for field,value in changes.items():
        if (field=='email' or field.endswith('_email')) and value not in (None,''):
            try:email_address(value)
            except ValueError as exc:errors.append({'loc':['body',field],'msg':str(exc),'type':'value_error'})
    return errors
