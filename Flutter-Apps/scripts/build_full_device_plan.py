"""Create auditable device cases without sending backend requests."""
import json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cat=json.loads((root/'assets/pms_catalog.json').read_text())['operations']
rows=[]; section=''; number=0
for line in (root/'qa/full-pms/source-checklist.txt').read_text(encoding='utf-8-sig').splitlines():
    head=re.match(r'(\d+)\. \*\*(.+?)\*\*',line)
    if head: section=head[2]; number=int(head[1]); continue
    item=re.match(r'\s+- (.+)',line)
    if item: rows.append({'id':f'{number}.{sum(r["category"]==section for r in rows)+1}', 'category':section,'operation':item[1],'status':'not_run'})
(root/'qa/full-pms/checklist.json').write_text(json.dumps(rows,indent=2))
cases=[]
def case(label,method,path,body=None,save=None,scope=None,verify=None):
    o=next((x for x in cat if x['method']==method and x['path']=='/project-management/'+path),None)
    assert o and o['available'],(method,path)
    c={'label':label,'method':method,'path':o['path'],'body':body or {}}
    if save:c['save']=save
    if scope:c['scope']=scope
    if verify:c['verify']=verify
    cases.append(c)
R=lambda name:'@'+name
case('Create isolated QA workspace','POST','workspaces',{'name':'Full PMS QA $run'},'workspace')
case('Create QA project','POST','projects',{'name':'Full PMS project $run','project_key':'Q$run'},'project')
for n in ('task','other','child'):
    case('Create '+n,'POST','projects/{project_id}/tasks',{'title':f'QA {n} $run','task_key':f'Q$run-{n}'},n)
case('Create client','POST','clients',{'name':'QA client $run'},'client')
case('Edit client','PATCH','clients/{client_id}',{'name':'QA client $run updated','email':'qa@example.invalid'})
case('Edit project identity and client','PATCH','projects/{project_id}',{'name':'Full PMS project $run updated','description':'Physical device verification','client_id':R('client'),'owner_user_id':R('user'),'manager_user_id':R('user')})
case('Edit project classification','PATCH','projects/{project_id}',{'category':'Internal','status':'In Progress','priority':'High','health':'On Track'})
case('Edit project schedules','PATCH','projects/{project_id}',{k:'$today' for k in ['start_date','due_date','planned_start_date','planned_end_date','actual_start_date','actual_end_date']})
case('Edit project financial estimates and progress','PATCH','projects/{project_id}',{'budget_amount':'1000.25','estimated_hours':'8.5','estimated_cost':'500.25','actual_cost':'100.25','billing_status':'Unbilled','progress_percent':25,'is_client_visible':False,'is_template':True})
case('Clone QA project','POST','projects/{project_id}/clone',{'name':'QA clone $run','project_key':'C$run'},'clone')
case('Archive QA clone','POST','projects/{project_id}/archive',scope={'project_id':R('clone')})
case('Unarchive QA clone','PATCH','projects/{project_id}',{'is_archived':False},scope={'project_id':R('clone')})
case('Delete QA clone','DELETE','projects/{project_id}',scope={'project_id':R('clone')})
case('Create epic','POST','projects/{project_id}/epics',{'name':'QA epic $run','epic_key':'E$run'},'epic')
case('Create component','POST','projects/{project_id}/components',{'name':'QA component $run'},'component')
case('Create release','POST','projects/{project_id}/releases',{'name':'QA release $run'},'release')
case('Create milestone','POST','projects/{project_id}/milestones',{'name':'QA milestone $run'},'milestone')
case('Create sprint','POST','projects/{project_id}/sprints',{'name':'QA sprint $run','start_date':'$today','end_date':'$tomorrow'},'sprint')
case('Edit task identity and issue details','PATCH','tasks/{task_id}',{'title':'QA task $run updated','description':'Device test description','work_type':'Bug','severity':'High','environment':'Android','affected_version':'0.2.0','fix_version':'0.2.1'})
case('Edit task development references','PATCH','tasks/{task_id}',{'development_branch':'qa/$run','development_commits':2,'development_prs':1,'development_deployments':1,'development_build':'QA-$run'})
case('Edit task estimates and access','PATCH','tasks/{task_id}',{'estimated_hours':'8.25','actual_hours':'1.5','original_estimate_hours':'10','remaining_estimate_hours':'6.75','story_points':3,'rank':10,'is_blocking':True,'is_client_visible':False,'security_level':'Internal'})
case('Assign task and reporter','PATCH','tasks/{task_id}',{'assignee_user_ids':[R('user')],'reporter_user_id':R('user')})
case('Set task scheduling','PATCH','tasks/{task_id}',{'start_date':'$today','due_date':'$tomorrow'})
case('Clear task scheduling','PATCH','tasks/{task_id}',{'start_date':None,'due_date':None},verify={'start_date':None,'due_date':None})
case('Clear task assignees','PATCH','tasks/{task_id}',{'assignee_user_ids':[]})
case('Associate task planning records','PATCH','tasks/{task_id}',{k+'_id':R(k) for k in ['milestone','sprint','epic','component','release']})
case('Set task parent','PATCH','tasks/{task_id}',{'parent_task_id':R('task')},scope={'task_id':R('child')})
case('Clear task parent','PATCH','tasks/{task_id}',{'parent_task_id':None},scope={'task_id':R('child')})
case('Bulk task status priority and assignee','PATCH','tasks/bulk',{'task_ids':[R('task'),R('other')],'status':'In Progress','priority':'High','assignee_user_id':R('user')})
case('Bulk task planning assignments','PATCH','tasks/bulk',{'task_ids':[R('task'),R('other')],'sprint_id':R('sprint'),'release_id':R('release'),'component_id':R('component')})
case('Mark task complete','PATCH','tasks/{task_id}',{'status':'Done'})
case('Reopen task','PATCH','tasks/{task_id}',{'status':'To Do'})
case('Create checklist item','POST','tasks/{task_id}/checklist',{'title':'QA checklist $run'},'item')
case('Edit and complete checklist','PATCH','checklist/{item_id}',{'title':'QA checklist updated $run','is_completed':True})
case('Reopen checklist','PATCH','checklist/{item_id}',{'is_completed':False})
case('Reorder checklist','POST','tasks/{task_id}/checklist/reorder',{'item_ids':[R('item')]})
case('Create task comment','POST','tasks/{task_id}/comments',{'body':'QA comment $run'},'comment')
case('Edit task comment','PATCH','comments/{comment_id}',{'body':'QA comment updated $run'})
case('Create tag','POST','tags',{'name':'QA-tag-$run','color':'#2255cc'},'tag')
case('Attach tag','POST','tasks/{task_id}/tags',{'tag_id':R('tag')})
case('Rename and recolor tag','PUT','tag-manager/{tag_id}',{'name':'QA-tag-updated-$run','color':'#cc5522'})
case('Create custom field','POST','projects/{project_id}/custom-fields',{'name':'QA field $run','field_type':'text'},'field')
case('Rename custom field','PUT','projects/{project_id}/custom-fields/{field_id}',{'name':'QA field updated $run','options':[]})
case('Set custom-field value','PUT','tasks/{task_id}/custom-fields/{field_id}',{'value':'Verified on Android'})
case('Create custom task type','POST','task-types',{'name':'QA type $run'},'type')
case('Update custom task type','PUT','task-types/{type_id}',{'name':'QA type updated $run','description':'Android QA','default_priority':'High','color':'#2255cc'})
case('Create task dependency','POST','tasks/{task_id}/dependencies',{'depends_on_task_id':R('other')},'dependency')
case('Move task into sprint','POST','tasks/{task_id}/move-to-sprint',{'sprint_id':R('sprint')})
case('Remove task from sprint','POST','tasks/{task_id}/remove-from-sprint')
case('Reorder backlog','POST','backlog/reorder',{'task_ids':[R('task'),R('other')]})
case('Reorder sprint tasks','POST','sprints/{sprint_id}/reorder-tasks',{'task_ids':[R('other')]})
case('Start sprint','POST','sprints/{sprint_id}/start')
case('Record sprint review','PATCH','sprints/{sprint_id}/review',{'review_notes':'QA review','retrospective_notes':'QA retro','what_went_well':'Testing','what_did_not_go_well':'None','outcome':'Verified'})
case('Complete sprint and carry work to backlog','POST','sprints/{sprint_id}/complete',{'incomplete_action':'move_to_backlog','review_notes':'QA review','retrospective_notes':'QA retro'})
case('Edit epic','PATCH','epics/{epic_id}',{'name':'QA epic updated $run','description':'Android QA'})
case('Schedule epic','PATCH','epics/{epic_id}/schedule',{'start_date':'$today','end_date':'$tomorrow'})
case('Edit component','PATCH','components/{component_id}',{'name':'QA component updated $run'})
case('Edit release','PATCH','releases/{release_id}',{'name':'QA release updated $run'})
case('Submit milestone approval','POST','milestones/{milestone_id}/submit-approval')
case('Approve milestone','POST','milestones/{milestone_id}/approve')
case('Set weekly recurrence','PATCH','tasks/{task_id}',{'recurrence_rule':'weekly','recurrence_interval':1,'recurrence_until':'$tomorrow'})
case('Clear recurrence','PATCH','tasks/{task_id}',{'recurrence_rule':None,'recurrence_until':None})
case('Create manual time log','POST','time-logs',{'project_id':R('project'),'task_id':R('task'),'log_date':'$today','duration_minutes':15,'description':'QA time $run','is_billable':False},'time_log')
case('Edit and bill time log','PATCH','time-logs/{time_log_id}',{'duration_minutes':20,'description':'QA time updated $run','is_billable':True})
case('Create timesheet','POST','timesheets',{'week_start_date':'$monday'},'timesheet')
case('Submit timesheet','POST','timesheets/{timesheet_id}/submit')
case('Approve timesheet','POST','timesheets/{timesheet_id}/approve')
case('Create calendar meeting','POST','planner/events',{'title':'QA meeting $run','start_at':'$today','end_at':'$tomorrow','timezone':'Asia/Kolkata','kind':'meeting','visibility':'private','meeting_url':'https://example.invalid/qa'},'event')
case('Create saved view','POST','saved-views',{'name':'QA view $run','view_type':'list'},'view')
case('Rename saved view','PATCH','saved-views/{view_id}',{'name':'QA view updated $run'})
case('Create saved project filter','POST','projects/{project_id}/saved-filters',{'name':'QA filter $run'},'filter')
case('Rename saved filter','PATCH','saved-filters/{filter_id}',{'name':'QA filter updated $run'})
case('Create risk','POST','risks',{'project_id':R('project'),'title':'QA risk $run'},'risk')
case('Edit risk','PATCH','risks/{risk_id}',{'title':'QA risk updated $run','probability':2,'impact':3,'mitigation_plan':'Device QA','contingency_plan':'Rollback','owner_user_id':R('user')})
case('Create team','POST','workspaces/{workspace_id}/teams',{'name':'QA team $run','alias':'qa-$run'},'team')
case('Rename team','PUT','workspaces/{workspace_id}/teams/{team_id}',{'name':'QA team updated $run','alias':'qa-$run'})
case('Create document','POST','projects/{project_id}/docs',{'title':'QA document $run','content':'Android QA'},'document')
case('Create dashboard','POST','dashboards',{'name':'QA dashboard $run','workspace_id':R('workspace')},'dashboard')
case('Create workspace note','POST','workspaces/{workspace_id}/entries',{'kind':'note','body':'QA workspace note $run'})
case('Create workspace chat entry','POST','workspaces/{workspace_id}/entries',{'kind':'chat','body':'QA workspace chat $run'})
case('Create automation','POST','workspaces/{workspace_id}/automations',{'name':'QA automation $run','project_id':R('project'),'trigger':'task.status_changed','action':'set_priority','priority':'High','enabled':False},'rule')
case('Enable automation','PATCH','workspaces/{workspace_id}/automations/{rule_id}',{'enabled':True})
case('Pause automation','PATCH','workspaces/{workspace_id}/automations/{rule_id}',{'enabled':False})
case('Create goal tool','POST','workspaces/{workspace_id}/tools',{'kind':'goal','name':'QA goal $run','project_id':R('project'),'task_ids':[R('task')]},'tool')
case('Disable goal tool','PATCH','workspaces/{workspace_id}/tools/{tool_id}',{'enabled':False})
# Every safe readable PMS endpoint is exercised in the native Flutter data page.
excluded=('workspace-invitations/preview','timer','/business/','/savepoints/{point_id}/','/direct-conversations/{','/chat/conversations/{','/attachments/{','/docs/{document_id}/revisions/{version}')
for o in cat:
    if o['method']!='GET' or not o['available'] or o['internal'] or o['restricted']:continue
    if any(x in o['path'] for x in excluded):continue
    if o['download']:continue
    if '/workspace-invitations/' in o['path']:continue
    cases.append({'label':'Read '+o['title'],'method':'GET','path':o['path'],'body':{}})
# Delete only records created by this matrix, after their read-back tests.
for label,path in [('comment','comments/{comment_id}'),('dependency','task-dependencies/{dependency_id}'),('checklist','checklist/{item_id}'),('tag association','tasks/{task_id}/tags/{tag_id}'),('time log','time-logs/{time_log_id}'),('view','saved-views/{view_id}'),('filter','saved-filters/{filter_id}'),('risk','risks/{risk_id}')]:
    case('Delete QA '+label,'DELETE',path)
case('Delete QA child task','DELETE','tasks/{task_id}',scope={'task_id':R('child')})
case('Restore QA child task','POST','trash/tasks/{task_id}/restore',scope={'task_id':R('child')})
payload=json.dumps(cases,separators=(',',':'))
(root/'integration_test/full_pms_cases.dart').write_text("// Generated by scripts/build_full_device_plan.py. Contains no credentials.\nconst fullPmsCasesJson = r'''"+payload+"''';\n")
print({'checklist_items':len(rows),'device_cases':len(cases)})
