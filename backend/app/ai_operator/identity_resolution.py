"""Exact identity resolution over fresh, authorized native directory results."""
import re


def person_id(selector,people,*,complete):
    target=selector.strip().strip('"“”').casefold()
    any_user=target in {'any eligible user','any user','someone','some user'}
    ident=re.fullmatch(r'(?:user\s*#?\s*|#)([1-9]\d*)',target)
    matches=[]
    for person in people:
        if type(person.get('id')) is not int or person['id']<=0:continue
        names={str(person.get(key) or '').strip().casefold() for key in ('name','displayName','display_name','email')}
        if any_user or (person['id']==int(ident[1]) if ident else target and target in names):matches.append(person['id'])
    # Names must be unique across the complete authorized result, not just page 1.
    unique=set(matches)
    if not unique or not any_user and (len(unique)!=1 or not complete):return None
    return min(unique)
