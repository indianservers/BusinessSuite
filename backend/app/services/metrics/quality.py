"""Read-only ambiguity checks. No records are merged or repaired automatically."""
import json
from sqlalchemy import func,or_
from app.models.user import User
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.common.models import CommonPerson
from .queries import registered_users,employee_records


def inspect_identities(db,user):
    accounts=registered_users(db,user,include_invited=True)
    employees=employee_records(db,user)
    emails=accounts.with_entities(func.lower(User.email).label("email"),func.count(User.id).label("records")).group_by(func.lower(User.email)).having(func.count(User.id)>1).count()
    linked=employees.filter(Employee.user_id.isnot(None)).with_entities(Employee.user_id,func.count(Employee.id)).group_by(Employee.user_id).having(func.count(Employee.id)>1).count()
    missing=accounts.filter(~User.person.has()).count()
    duplicate_days=db.query(Attendance.employee_id,Attendance.attendance_date,func.count(Attendance.id)).filter(Attendance.employee_id.in_(employees.with_entities(Employee.id))).group_by(Attendance.employee_id,Attendance.attendance_date).having(func.count(Attendance.id)>1).count()
    from app.apps.project_management.people_workspace import teams_query
    from app.apps.project_management.models import PMSWorkspaceTeamMember
    teams=teams_query(db,user).all();ids=[t.id for t in teams]
    pairs=db.query(PMSWorkspaceTeamMember.team_id,PMSWorkspaceTeamMember.user_id).filter(PMSWorkspaceTeamMember.team_id.in_(ids)).all() if ids else []
    normalized={identity:set() for identity in ids}
    for team,identity in pairs:normalized[team].add(identity)
    mismatches=[]
    for team in teams:
        try:legacy=set(json.loads(team.member_ids_json or "[]"))
        except (ValueError,TypeError):mismatches.append({"team_id":team.id,"problem":"Invalid legacy membership JSON"});continue
        if legacy!=normalized[team.id]:mismatches.append({"team_id":team.id,"problem":"Legacy and normalized membership IDs differ"})
    return [
        {"check":"Case-insensitive duplicate account emails","count":emails,"unit":"ambiguous groups","classification":"data-quality issue","review_required":bool(emails),"action":"Administrator review only; never merge by name or similarity"},
        {"check":"Multiple nondeleted employee records linked to one account","count":linked,"unit":"linked user IDs","classification":"data-quality issue","review_required":bool(linked)},
        {"check":"Accounts using a legacy organization fallback without a canonical person","count":missing,"unit":"account records","classification":"Mapping review","review_required":bool(missing)},
        {"check":"Duplicate attendance employee/day records","count":duplicate_days,"unit":"employee/day groups","classification":"data-quality issue","review_required":bool(duplicate_days),"action":"Today's attendance metric uses the latest stored row per employee/day; review duplicates without deleting history"},
        {"check":"Team membership cache differs from normalized identities","count":len(mismatches),"unit":"teams","classification":"data-quality issue","review_required":bool(mismatches),"examples":mismatches[:20]},
    ]
