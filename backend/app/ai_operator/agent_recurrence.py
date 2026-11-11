"""Typed, anchored recurrence shared by schedule forms and agent authoring."""
import calendar
from datetime import datetime,timedelta,timezone
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import Field,model_validator
from app.ai_operator.suite_tools import Strict


class Recurrence(Strict):
    frequency:Literal['once','daily','weekly','monthly','custom']='daily'
    interval:int|None=Field(default=None,ge=1,le=365,strict=True)
    interval_unit:Literal['hours','days','weeks','months']|None=None

    @model_validator(mode='after')
    def recurrence(self):
        if self.frequency=='custom':
            if self.interval is None or self.interval_unit is None:raise ValueError('Choose a custom interval and unit')
        elif self.interval is not None or self.interval_unit is not None:raise ValueError('Intervals apply only to custom recurrence')
        return self


def next_custom_occurrence(spec,current):
    """Skip missed occurrences while retaining the reviewed first-run anchor.

    Hours are elapsed UTC time. Calendar intervals retain local wall time.
    Nonexistent DST times round forward by the gap; repeated times use fold 0.
    Month-end clamping never shifts the original day for later months.
    """
    zone=ZoneInfo(spec['timezone']);anchor=datetime.fromisoformat(spec['scheduled_at']).astimezone(zone)
    current=current.astimezone(timezone.utc);step=spec['interval'];unit=spec['interval_unit']
    if unit=='hours':
        first=anchor.astimezone(timezone.utc);period=timedelta(hours=step)
        return first+max(0,(current-first)//period+1)*period
    local=current.astimezone(zone)
    if unit=='months':
        elapsed=(local.year-anchor.year)*12+local.month-anchor.month
        index=max(0,elapsed//step-1)
    else:
        days=step*(7 if unit=='weeks' else 1)
        index=max(0,(local.date()-anchor.date()).days//days-1)
    for n in range(index,index+5):
        if unit=='months':
            year,month=divmod(anchor.year*12+anchor.month-1+n*step,12);month+=1
            candidate=anchor.replace(year=year,month=month,day=min(anchor.day,calendar.monthrange(year,month)[1]),fold=0)
        else:candidate=(anchor+timedelta(days=n*days)).replace(fold=0)
        candidate=candidate.astimezone(timezone.utc)
        if candidate>current:return candidate
    raise ValueError('Could not determine next custom occurrence')
