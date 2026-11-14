from sqlalchemy import event
from app.models.user import User
from app.models.audit import AuditLog
from app.common.models import CommonProfile
from app.apps.project_management.models import PMSWorkspaceMember
from app.apps.project_management.workspaces import members
from tests.test_pms_workspaces import account, middleware_database, BASE
from test_identity_utils import attach_test_identity


def test_member_directory_queries_are_bounded_and_preserve_status_privacy(client,db):
    owner,headers=account(db,"member-query-owner@example.test",True)
    wid=client.post(BASE+"/workspaces",headers=headers,json={"name":"Query scaling"}).json()["id"]
    def measured():
        db.expire_all();statements=[]
        def record(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith("SELECT"):statements.append(statement)
        engine=db.get_bind();event.listen(engine,"before_cursor_execute",record)
        try:rows=members(wid,db,owner)
        finally:event.remove(engine,"before_cursor_execute",record)
        return rows,len(statements)
    _,small=measured()
    seeded=[]
    for i in range(24):
        user=User(email=f"query-member-{i}@example.test",hashed_password="unused",is_active=i%3==0)
        db.add(user);db.flush();person=attach_test_identity(db,user)
        person.display_name=f"Member {i}"
        profile=db.query(CommonProfile).filter_by(person_id=person.id).one()
        profile.directory_visibility="private" if i%2 else "public"
        profile.profile_photo_url=f"/uploads/{i}.png"
        db.add(PMSWorkspaceMember(workspace_id=wid,user_id=user.id,role="Member"))
        if i%3==1:
            db.add(AuditLog(method="POST",entity_type="user",entity_id=user.id,action="ACCOUNT_TERMINATE"))
        seeded.append((user.id,i))
    db.commit()
    rows,large=measured();by_id={r["user_id"]:r for r in rows}
    for uid,i in seeded:
        row=by_id[uid];assert row["name"]==f"Member {i}"
        assert row["status"]==("active" if i%3==0 else "terminated" if i%3==1 else "suspended")
        assert row["photo_url"]==(None if i%2 else f"/uploads/{i}.png")
        assert row["role"]=="Member"
    assert large<=small+3,(small,large)
