import io
from uuid import uuid4
import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_bot_artifacts import command,execute,A
from tests.test_agent_library import member
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context
from app.ai_operator.assistant_models import AssistantConversation
from app.shared.models import ServicePolicy
from app.ai_operator.artifact_shares import KIND

S=ROOT+'/artifact-shares'


@pytest.mark.parametrize('changes',[{'source_id':True},{'source_revision':True},{'share_id':True,'revision':1},
    {'audience':{'kind':'members','member_ids':[True]}},{'audience':{'kind':'workspace_teams','team_ids':['1']}},
    {'audience':{'kind':'members','member_ids':[]}}])
def test_share_identities_and_audiences_are_strict(changes):
    from app.ai_operator.artifact_shares import Preview
    with pytest.raises(ValueError):Preview.model_validate({'request_key':str(uuid4()),'source_id':1,'source_revision':1,'audience':{'kind':'organization'},**changes})


def source(client,db,h,kind='document'):
    text={'document':'Create document called Team notes: Approved public wording.',
        'checklist':'Create checklist called Team checklist: - [ ] Review scope',
        'presentation':'Create presentation called Review: Overview | Approved scope || Next | Confirm owner'}
    if kind!='table':return execute(client,db,h,command(client,h,'CRM',text[kind]))['receipts'][0]['artifact_id']
    table={'title':'Regional amounts','kind':'table','content':'Illustrative supplied rows.','columns':['Region','Amount','Currency'],
        'rows':[['North','100','USD'],['South','200','USD'],['North','50','INR'],['West','=1+1','USD']],
        'chart':{'kind':'bar','category_column':0,'value_column':1,'aggregation':'sum'}}
    return execute(client,db,h,command(client,h,'CRM','Prepare chart',local_plan={'summary':'Review chart','steps':[{'tool':'crm.create_artifact','payload':table}]}))['receipts'][0]['artifact_id']


def review(client,h,ident,audience,**extra):
    response=client.post(S+'/preview',headers=h,json={'request_key':str(uuid4()),'source_id':ident,'source_revision':1,'audience':audience,**extra})
    assert response.status_code==200,response.text
    return response.json()


def publish(client,h,draft):
    response=client.post(S+f'/{draft["id"]}/publish',headers=h,json={'preview_hash':draft['pending']['preview_hash']})
    assert response.status_code==200,response.text
    return response.json()


@pytest.mark.parametrize('kind',['document','checklist','table','presentation'])
def test_reviewed_shares_reuse_exports_without_exposing_private_artifacts_or_chats(client,db,kind):
    owner,_,_,_=setup_suite(client,db);recipient,user=member(client,db);outsider,_=member(client,db)
    ident=source(client,db,owner,kind)
    draft=review(client,owner,ident,{'kind':'members','member_ids':[user.id]})
    assert client.get(S+f'/{draft["id"]}/content',headers=recipient).status_code==404
    restored=client.get(S+'/source/'+str(ident),headers=owner).json()['items'][0]
    assert restored['pending']['preview_hash']==draft['pending']['preview_hash']
    share=publish(client,owner,draft)
    assert publish(client,owner,draft)['id']==share['id']
    content=client.get(S+f'/{share["id"]}/content',headers=recipient,params={'revision':share['revision']})
    assert content.status_code==200,content.text
    item=content.json()['item'];assert item['kind']==kind and item['provenance']['citations']==[]
    assert not {'conversation_id','project_id','security_context','suite_run_id'}&set(item)
    assert item['id']==f'share-{share["id"]}'
    assert client.get(A+f'/{ident}',headers=recipient).status_code==404
    assert db.query(AssistantConversation).filter_by(user_id=user.id).count()==0
    assert client.get(S+f'/{share["id"]}/content',headers=outsider).status_code==404
    assert 'pending' not in content.json() and client.get(S,headers=outsider).json()['items']==[]
    formats=['md','docx','pdf',*(['xlsx','csv'] if kind=='table' else ['pptx'] if kind=='presentation' else [])]
    for fmt in formats:
        exported=client.get(S+f'/{share["id"]}/download',headers=recipient,params={'format':fmt,'revision':share['revision']})
        assert exported.status_code==200,exported.text[:200]
    if kind=='table':
        analysis=client.get(S+f'/{share["id"]}/analysis',headers=recipient,params={'category_query':'North'}).json()
        assert {p['unit']:p['statistics']['sum'] for p in analysis['panels']}=={'USD':'100','INR':'50'}


def test_shared_editions_do_not_change_until_review_and_revoke_removes_future_access(client,db):
    owner,_,_,_=setup_suite(client,db);recipient,user=member(client,db);next_recipient,next_user=member(client,db)
    ident=source(client,db,owner)
    first=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    execute(client,db,owner,command(client,owner,'CRM',f'Edit artifact #{ident}: Append: New source version.'))
    assert 'New source version' not in client.get(S+f'/{first["id"]}/content',headers=recipient).text
    pending=review(client,owner,ident,{'kind':'members','member_ids':[next_user.id]},source_revision=2,share_id=first['id'],revision=first['revision'])
    assert client.get(S+f'/{first["id"]}/content',headers=recipient).status_code==200
    assert client.get(S+f'/{first["id"]}/content',headers=next_recipient).status_code==404
    second=publish(client,owner,pending);assert second['revision']==2
    assert client.get(S+f'/{first["id"]}/content',headers=recipient).status_code==404
    assert 'New source version' in client.get(S+f'/{first["id"]}/content',headers=next_recipient).text
    assert client.get(S+f'/{first["id"]}/content',headers=next_recipient,params={'revision':1}).status_code==409
    assert client.post(S+f'/{first["id"]}/revoke',headers=recipient,json={'revision':2}).status_code==403
    revoked=client.post(S+f'/{first["id"]}/revoke',headers=owner,json={'revision':2});assert revoked.status_code==200,revoked.text
    assert client.post(S+f'/{first["id"]}/revoke',headers=owner,json={'revision':2}).json()['revision']==revoked.json()['revision']
    for route in ('content','download','analysis'):
        assert client.get(S+f'/{first["id"]}/{route}',headers=next_recipient).status_code==404
    row=db.get(ServicePolicy,first['id']);assert row.values_json['definition'] is None and row.values_json['history']==[]


def test_shared_dashboard_bundles_only_reviewed_snapshots_and_source_archive_revokes_bundle(client,db):
    owner,_,_,_=setup_suite(client,db);recipient,user=member(client,db)
    table=source(client,db,owner,'table');notes=source(client,db,owner)
    dashboard=execute(client,db,owner,command(client,owner,'CRM',f'Create dashboard called Team dashboard: artifact #{table} v1 as chart; artifact #{notes} v1 as summary'))['receipts'][0]['artifact_id']
    share=publish(client,owner,review(client,owner,dashboard,{'kind':'members','member_ids':[user.id]}))
    root=client.get(S+f'/{share["id"]}/content',headers=recipient).json()['item']
    assert [p['artifact_id'] for p in root['panels']]==[1,2]
    panel=client.get(S+f'/{share["id"]}/panels/1',headers=recipient).json()['item']
    assert panel['id']==f'share-{share["id"]}-panel-1' and panel['rows'][3][1]=='=1+1'
    analysis=client.get(S+f'/{share["id"]}/analysis',headers=recipient,params={'position':1,'chart_kind':'line'}).json()
    assert analysis['panels'][0]['kind']=='line' and analysis['panels'][0]['statistics']['sum']=='300'
    excel=client.get(S+f'/{share["id"]}/download',headers=recipient,params={'format':'xlsx'})
    assert excel.status_code==200,excel.text[:200]
    book=load_workbook(io.BytesIO(excel.content));assert len(book['Chart analysis']._charts)==2
    assert book['Source 1']['B8'].value=='=1+1' and book['Source 1']['B8'].data_type=='s'
    pdf=client.get(S+f'/{share["id"]}/download',headers=recipient,params={'format':'pdf'})
    assert pdf.status_code==200 and 'sum 300' in ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert client.delete(A+f'/{notes}',headers=owner).status_code==200
    assert client.get(S+f'/{share["id"]}/panels/1',headers=recipient).status_code==404
    assert client.get(S+f'/{share["id"]}/download',headers=recipient,params={'format':'pdf'}).status_code==404


def test_share_preview_is_owner_admin_only_and_archive_cancels_pending_publication(client,db):
    owner,_,_,_=setup_suite(client,db);recipient,user=member(client,db);ident=source(client,db,owner)
    assert client.post(S+'/preview',headers=recipient,json={'request_key':str(uuid4()),'source_id':ident,'source_revision':1,'audience':{'kind':'organization'}}).status_code==403
    draft=review(client,owner,ident,{'kind':'members','member_ids':[user.id]})
    wrong=client.post(S+f'/{draft["id"]}/publish',headers=owner,json={'preview_hash':'0'*64});assert wrong.status_code==409
    assert client.delete(A+f'/{ident}',headers=owner).status_code==200
    assert client.post(S+f'/{draft["id"]}/publish',headers=owner,json={'preview_hash':draft['pending']['preview_hash']}).status_code==409
    assert client.get(S+f'/{draft["id"]}/content',headers=recipient).status_code==404


def test_shared_snapshot_does_not_grant_source_module_access_and_integrity_is_checked(client,db):
    owner,_,_,_=setup_suite(client,db);recipient,user=member(client,db,permissions=['ai_assistant','crm_view'])
    source_id=execute(client,db,owner,command(client,owner,'HRMS','Create document called Staffing: Reviewed HRMS snapshot.'))['receipts'][0]['artifact_id']
    dashboard=execute(client,db,owner,command(client,owner,'CRM',f'Create dashboard called Staffing overview: artifact #{source_id} v1 as summary'))['receipts'][0]['artifact_id']
    share=publish(client,owner,review(client,owner,dashboard,{'kind':'members','member_ids':[user.id]}))
    assert client.get(S+f'/{share["id"]}/content',headers=recipient).status_code==403
    row=db.get(ServicePolicy,share['id']);row.values_json={**row.values_json,'audience':{'kind':'organization','member_ids':[],'team_ids':[]}};db.commit()
    assert client.get(S+f'/{share["id"]}/content',headers=recipient).status_code==409


def test_shared_team_membership_is_checked_on_every_read(client,db):
    from app.apps.project_management.models import PMSWorkspaceMember,PMSWorkspaceTeam,PMSWorkspaceTeamMember
    from test_identity_utils import provision_workflow_workspace
    owner,publisher,_,_=setup_suite(client,db);recipient,user=member(client,db)
    workspace=provision_workflow_workspace(db,publisher)
    db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=user.id,role='Member'))
    team=PMSWorkspaceTeam(workspace_id=workspace.id,name='Report reviewers',alias='report-reviewers');db.add(team);db.commit()
    ident=execute(client,db,owner,command(client,owner,'CRM','Create document called Team brief: Reviewed team content.',workspace_id=workspace.id))['receipts'][0]['artifact_id']
    share=publish(client,owner,review(client,owner,ident,{'kind':'workspace_teams','team_ids':[team.id]}))
    assert client.get(S+f'/{share["id"]}/content',headers=recipient).status_code==404
    membership=PMSWorkspaceTeamMember(team_id=team.id,user_id=user.id);db.add(membership);db.commit()
    assert client.get(S+f'/{share["id"]}/content',headers=recipient).status_code==200
    db.delete(membership);db.commit()
    assert client.get(S+f'/{share["id"]}/content',headers=recipient).status_code==404


def test_shares_cannot_cross_organizations_or_survive_a_disabled_publisher(client,db):
    owner,publisher,_,_=setup_suite(client,db);recipient,user=member(client,db);foreign,foreign_user=member(client,db,company_id=2)
    ident=source(client,db,owner)
    response=client.post(S+'/preview',headers=owner,json={'request_key':str(uuid4()),'source_id':ident,'source_revision':1,
        'audience':{'kind':'members','member_ids':[foreign_user.id]}})
    assert response.status_code==422,response.text
    share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    assert client.get(S+f'/{share["id"]}/content',headers=foreign).status_code==404
    publisher.is_active=False;db.commit()
    assert client.get(S+f'/{share["id"]}/content',headers=recipient).status_code==404


def test_share_confirmation_is_bound_to_original_session_and_export_permission(client,db,monkeypatch):
    from fastapi import HTTPException
    from app.access import service
    owner,publisher,_,_=setup_suite(client,db);recipient,user=member(client,db);ident=source(client,db,owner)
    draft=review(client,owner,ident,{'kind':'members','member_ids':[user.id]})
    from app.ai_agents.security import signature
    row=db.get(ServicePolicy,draft['id']);pending=row.values_json['pending']
    # A differently sealed review is rejected even with its real, unchanged hash.
    invalid={**pending['grant'],'session_id':None};invalid['signature']=signature({k:v for k,v in invalid.items() if k!='signature'})
    from app.ai_operator.artifact_shares import sign
    row.values_json={**row.values_json,'pending':{**pending,'grant':invalid}};sign(row);db.commit()
    rejected=client.post(S+f'/{draft["id"]}/publish',headers=owner,json={'preview_hash':pending['preview_hash']});assert rejected.status_code in (401,403),rejected.text
    row.values_json={**row.values_json,'pending':pending};sign(row);db.commit()
    share=publish(client,owner,draft)
    original=service.check_background_access
    def guarded(db,user,module,action,*args,**kwargs):
        if user.id==user_id and action=='export':raise HTTPException(403,'Export is not permitted')
        return original(db,user,module,action,*args,**kwargs)
    user_id=user.id;monkeypatch.setattr(service,'check_background_access',guarded)
    assert client.get(S+f'/{share["id"]}/content',headers=recipient).status_code==200
    assert client.get(S+f'/{share["id"]}/download',headers=recipient,params={'format':'pdf'}).status_code==403


def test_shared_listing_does_not_reveal_titles_after_publisher_permission_changes(client,db):
    from app.access.models import AccessMembership
    owner,publisher,_,_=setup_suite(client,db)
    existing=db.query(AccessMembership).filter_by(user_id=publisher.id,company_id=1).first()
    if existing:existing.active=True;existing.is_admin=True
    else:db.add(AccessMembership(user_id=publisher.id,company_id=1,active=True,is_admin=True))
    db.commit();ident=source(client,db,owner)
    publish(client,owner,review(client,owner,ident,{'kind':'organization'}))
    publisher.is_superuser=False;db.commit()
    listing=client.get(S,headers=owner)
    assert listing.status_code==200,listing.text
    assert listing.json()['items']==[] and 'Team notes' not in listing.text


def test_read_only_project_viewer_can_read_a_share_without_task_management_or_export_rights(client,db):
    from app.apps.project_management.models import PMSWorkspaceMember,PMSProject
    from app.apps.project_management.access import get_project_for_action
    from fastapi import HTTPException
    from test_identity_utils import provision_workflow_workspace
    owner,publisher,project_id,_=setup_suite(client,db);recipient,user=member(client,db,permissions=['ai_assistant','pms_view'])
    outsider,_=member(client,db,permissions=['ai_assistant','pms_view'])
    project=db.get(PMSProject,project_id)
    workspace=provision_workflow_workspace(db,publisher);project.workspace_id=workspace.id
    db.add(PMSWorkspaceMember(workspace_id=project.workspace_id,user_id=user.id,role='Guest'));db.commit()
    ident=execute(client,db,owner,command(client,owner,'PMS','Create document called Project briefing: Reviewed project scope.',
        workspace_id=project.workspace_id,project_id=project.id))['receipts'][0]['artifact_id']
    share=publish(client,owner,review(client,owner,ident,{'kind':'organization'}))
    response=client.get(S+f'/{share["id"]}/content',headers=recipient)
    assert response.status_code==200,response.text
    assert 'Reviewed project scope' in response.text
    with pytest.raises(HTTPException):get_project_for_action(db,project.id,user,'manage_tasks')
    assert client.get(S+f'/{share["id"]}/download',headers=recipient,params={'format':'pdf'}).status_code==403
    assert client.get(S+f'/{share["id"]}/content',headers=outsider).status_code in (403,404)


def test_archiving_source_through_another_storage_path_still_blocks_shared_reads(client,db):
    from datetime import datetime,timezone
    from sqlalchemy import update
    owner,_,_,_=setup_suite(client,db);recipient,user=member(client,db);ident=source(client,db,owner)
    share=publish(client,owner,review(client,owner,ident,{'kind':'members','member_ids':[user.id]}))
    db.connection().execute(update(AssistantConversation.__table__).where(AssistantConversation.__table__.c.id==ident).values(deleted_at=datetime.now(timezone.utc)));db.commit()
    assert client.get(S+f'/{share["id"]}/content',headers=recipient).status_code==404
    assert client.get(S+f'/{share["id"]}/download',headers=recipient,params={'format':'pdf'}).status_code==404
    assert client.get(S,headers=recipient).json()['items']==[]


def test_idempotent_publish_still_rechecks_private_source_access(client,db,monkeypatch):
    from fastapi import HTTPException
    from app.ai_operator import artifact_shares
    owner,_,_,_=setup_suite(client,db);ident=source(client,db,owner)
    draft=review(client,owner,ident,{'kind':'organization'});publish(client,owner,draft)
    monkeypatch.setattr(artifact_shares,'bundle',lambda *args:(_ for _ in ()).throw(HTTPException(403,'Source access revoked')))
    response=client.post(S+f'/{draft["id"]}/publish',headers=owner,json={'preview_hash':draft['pending']['preview_hash']})
    assert response.status_code==403,response.text


def test_active_library_does_not_expose_a_pending_snapshot_after_its_private_access_is_lost(client,db,monkeypatch):
    from fastapi import HTTPException
    from app.ai_operator import artifact_shares
    owner,_,_,_=setup_suite(client,db);ident=source(client,db,owner)
    share=publish(client,owner,review(client,owner,ident,{'kind':'organization'}))
    execute(client,db,owner,command(client,owner,'CRM',f'Edit artifact #{ident}: Append: Pending private wording.'))
    review(client,owner,ident,{'kind':'organization'},source_revision=2,share_id=share['id'],revision=share['revision'])
    monkeypatch.setattr(artifact_shares,'bundle',lambda *args:(_ for _ in ()).throw(HTTPException(403,'Private source access revoked')))
    response=client.get(S,headers=owner);assert response.status_code==200,response.text
    assert response.json()['items'][0]['pending'] is None and 'Pending private wording' not in response.text
