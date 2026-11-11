from datetime import datetime
import pytest
from app.ai_operator.agent_recurrence import Recurrence,next_custom_occurrence


@pytest.mark.parametrize('anchor,current,unit,interval,zone,expected',[
    ('2026-01-01T09:00:00+00:00','2026-01-04T09:00:00+00:00','days',3,'UTC','2026-01-07T09:00:00+00:00'),
    ('2026-01-01T09:00:00+00:00','2026-01-08T12:00:00+00:00','days',3,'UTC','2026-01-10T09:00:00+00:00'),
    ('2026-01-05T09:00:00+00:00','2026-02-20T12:00:00+00:00','weeks',3,'UTC','2026-03-09T09:00:00+00:00'),
    ('2026-01-31T09:00:00+00:00','2026-03-31T09:00:00+00:00','months',2,'UTC','2026-05-31T09:00:00+00:00'),
    ('2026-12-31T09:00:00+00:00','2027-01-10T09:00:00+00:00','months',2,'UTC','2027-02-28T09:00:00+00:00'),
    ('2026-01-01T09:00:00+05:30','2026-01-01T08:00:00+00:00','hours',2,'Asia/Kolkata','2026-01-01T09:30:00+00:00'),
    ('2026-03-07T02:30:00-05:00','2026-03-07T08:00:00+00:00','days',1,'America/New_York','2026-03-08T07:30:00+00:00'),
    ('2026-03-07T02:30:00-05:00','2026-03-08T08:00:00+00:00','days',1,'America/New_York','2026-03-09T06:30:00+00:00'),
    ('2026-10-31T01:30:00-04:00','2026-11-01T05:45:00+00:00','days',1,'America/New_York','2026-11-02T06:30:00+00:00'),
    ('2026-12-01T09:00:00+00:00','2026-01-01T09:00:00+00:00','months',2,'UTC','2026-12-01T09:00:00+00:00'),
])
def test_anchored_intervals_skip_missed_runs_and_preserve_calendar_semantics(anchor,current,unit,interval,zone,expected):
    spec={'frequency':'custom','scheduled_at':anchor,'timezone':zone,'interval':interval,'interval_unit':unit}
    assert next_custom_occurrence(spec,datetime.fromisoformat(current))==datetime.fromisoformat(expected)


@pytest.mark.parametrize('fields',[
    {'frequency':'custom'}, {'frequency':'custom','interval':2},
    {'frequency':'daily','interval':2,'interval_unit':'days'},
    *[{'frequency':'custom','interval':i,'interval_unit':'days'} for i in (0,366,True,2.0)],
    {'frequency':'custom','interval':2,'interval_unit':'minutes'},
])
def test_invalid_or_ambiguous_custom_rules_are_rejected(fields):
    with pytest.raises(ValueError):Recurrence(**fields)
