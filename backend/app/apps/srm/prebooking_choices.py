"""Bounded advisory combinations. Final reservation always rechecks all choices."""
from datetime import datetime, timedelta, timezone
from itertools import islice, product
from zoneinfo import ZoneInfo
from fastapi import HTTPException


def find_choices(db, actor, service_id, day, minutes, *, eligibility_id=None, resource_ids=None,
                 starts_at=None, auto_resources=False, employee_offset=0, resource_offset=0,
                 search_days=1, selected=None, window_from=None, window_until=None, priority='earliest', preferred_employee_id=None):
    from app.apps.srm.service_checkout_options import service_options, scheduling_availability, _providers, _authority
    company, branch, scope = _authority(db,actor,selected)
    if starts_at and starts_at.utcoffset() is None:
        raise HTTPException(422,'Discovery time needs a timezone offset')
    if bool(window_from) != bool(window_until) or window_from and (window_from.utcoffset() is not None or window_until.utcoffset() is not None or window_until <= window_from):
        raise HTTPException(422,'Choose a local time window with an end after its start')
    options = service_options(db,actor,service_id,selected=selected,offset=employee_offset)
    if not options['policy'] or not options['policy']['active']:
        raise HTTPException(409,'Choose a service with an active scheduling policy')
    people = options['specialists'][:4]
    if eligibility_id:
        people,_ = _providers(db,company,branch,scope,policy={**options['policy'],'service_product_id':service_id},eligibility_id=eligibility_id)
        if not people: raise HTTPException(404,'Eligible employee not found')
    resources = options['resources']
    ids = resource_ids or []
    if len(ids)>9 or len(set(ids))!=len(ids) or not set(ids)<={r['id'] for r in resources}:
        raise HTTPException(422,'Choose up to 9 current additional resources')
    required = set(options['policy'].get('required_resource_types') or [])
    fixed = [i for i in ids if not auto_resources or next(r['resource_type'] for r in resources if r['id']==i) not in required]
    missing = required - {r['resource_type'] for r in resources if r['id'] in fixed}
    groups = [[r['id'] for r in sorted(resources,key=lambda r:r['id'] not in ids) if r['resource_type']==kind][resource_offset:resource_offset+8] for kind in sorted(missing)]
    combinations = [fixed+list(extra) for extra in islice(product(*groups),32)] if groups else [fixed]
    if not (required - {r['resource_type'] for r in resources if r['id'] in ids}):
        combinations = [ids, *[c for c in combinations if c != ids]]
    choices, checked, errors = [], 0, 0
    for person in people:
        for offset in range(search_days):
            candidate_day = day + timedelta(days=offset)
            today = datetime.now(ZoneInfo(person['timezone'])).date()
            if not today <= candidate_day <= today+timedelta(days=90): continue
            for combination in combinations:
                if checked>=128: break
                checked+=1
                at = starts_at if offset==0 and starts_at and starts_at.astimezone(ZoneInfo(person['timezone'])).date()==candidate_day else None
                try:
                    state=scheduling_availability(db,actor,service_id,person['eligibility_id'],candidate_day,minutes,
                        resource_ids=combination,starts_at=at,selected=selected)
                except HTTPException as error:
                    if error.status_code not in (409,422): raise
                    errors+=1
                    continue
                possible = ([{'starts_at':at.isoformat()}, *[slot for slot in state['slots'] if datetime.fromisoformat(slot['starts_at']) != at]] if at and state['selection_available'] else state['slots'])
                possible = [slot for slot in possible if not starts_at or datetime.fromisoformat(slot['starts_at'])>=starts_at]
                if window_from:
                    possible = [slot for slot in possible if (lambda local: local.time().replace(tzinfo=None)>=window_from and (local+timedelta(minutes=minutes)).date()==local.date() and (local+timedelta(minutes=minutes)).time().replace(tzinfo=None)<=window_until)(datetime.fromisoformat(slot['starts_at']).astimezone(ZoneInfo(person['timezone'])))]
                for slot in possible[:2]:
                    choices.append({'eligibility_id':person['eligibility_id'],'employee_id':person['employee_id'],
                        'employee_name':person['employee_name'],'timezone':person['timezone'],
                        'provider_resource_id':person['provider_resource_id'],'eligibility_revision':person['eligibility_revision'],'work_categories':person.get('work_categories',[]),
                        'starts_at':slot['starts_at'],'resource_ids':combination,
                        'resources':[r['name'] for r in resources if r['id'] in combination],
                        'changed_resources':len(set(combination)^set(ids))})
                if possible: break
            if any(c['eligibility_id']==person['eligibility_id'] for c in choices) or checked>=128: break
        if checked>=128: break
    def rank(choice):
        at=datetime.fromisoformat(choice['starts_at'])
        other=choice['employee_id']!=preferred_employee_id if preferred_employee_id else choice['eligibility_id']!=eligibility_id
        return ((other,at,choice['changed_resources']) if priority=='same_employee' else (choice['changed_resources'],other,at) if priority=='fewest_changes' else (at,other,choice['changed_resources']))+(choice['employee_name'],)
    choices.sort(key=rank)
    return {'choices':choices[:8],'checked_combinations':checked,'partial':checked>=128 or bool(options.get('has_more_resources')) or (not eligibility_id and (options['has_more'] or len(options['specialists'])>len(people))) or any(len([r for r in resources if r['resource_type']==kind])>resource_offset+8 for kind in missing) or len(choices)>8,
        'failed_checks':errors,'next_employee_offset':employee_offset+len(people) if not eligibility_id and (options['has_more'] or len(options['specialists'])>len(people)) else None,
        'next_resource_offset':resource_offset+8 if any(len([r for r in resources if r['resource_type']==kind])>resource_offset+8 for kind in missing) else None,
        'searched_days':search_days,'checked_at':datetime.now(timezone.utc).isoformat()}
