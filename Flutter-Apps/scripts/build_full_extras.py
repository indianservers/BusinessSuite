"""Targeted retries plus native board/calendar, forms, attachments and recovery."""
import copy,json
from pathlib import Path
r=Path(__file__).resolve().parents[1]
base=json.loads((r/'integration_test/full_pms_cases.dart').read_text().split("r'''")[1].split("'''")[0])
by={c['label']:c for c in base}
cases=copy.deepcopy(base[:5])
def take(label,body=None):
    c=copy.deepcopy(by[label])
    if body is not None:c['body']=body
    cases.append(c)
def add(label,method,path,body=None,**kw):
    cases.append({'label':label,'method':method,'path':'/project-management/'+path,'body':body or {},**kw})
for label in ['Clone QA project','Archive QA clone','Unarchive QA clone','Create epic','Create component','Create release','Create milestone','Create sprint','Set task parent','Clear task parent','Bulk task status priority and assignee','Bulk task planning assignments','Remove task from sprint']:take(label)
take('Reorder backlog',{'task_ids':['@task']})
take('Reorder sprint tasks')
take('Create custom field')
take('Set custom-field value')
add('Clear nullable custom-field value','PUT','tasks/{task_id}/custom-fields/{field_id}',{'value':None})
add('Create numeric custom field','POST','projects/{project_id}/custom-fields',{'name':'QA numeric $run','field_type':'number'},save='field')
add('Set numeric custom-field value','PUT','tasks/{task_id}/custom-fields/{field_id}',{'value':12.5})
add('Create boolean custom field','POST','projects/{project_id}/custom-fields',{'name':'QA checkbox $run','field_type':'checkbox'},save='field')
add('Set boolean custom-field value','PUT','tasks/{task_id}/custom-fields/{field_id}',{'value':True})
take('Create custom task type')
take('Update custom task type',{'description':'Android QA updated','default_priority':'High','color':'#2255cc','archived':True})
for rule,interval in [('daily',1),('weekly',2),('monthly',1)]:
    add('Configure '+rule+' recurrence','PATCH','tasks/{task_id}',{'due_date':'$today','recurrence_rule':rule,'recurrence_interval':interval,'recurrence_until':'$future'})
    take('Mark task complete')
    add('Verify next '+rule+' occurrence','GET','projects/{project_id}/tasks',assert_recurring_generated=rule)
    take('Reopen task')
take('Clear recurrence')
take('Read Get Backlog')
take('Read Report Velocity')
add('Create deletable QA time log','POST','time-logs',{'project_id':'@project','task_id':'@task','log_date':'$future','duration_minutes':5,'description':'QA deletable $run'},save='time_log')
add('Delete unsubmitted QA time log','DELETE','time-logs/{time_log_id}')
for action,label in [('layouts','Switch native board/list layouts'),('drag','Drag native task into In Progress'),('copy','Copy task ID from native menu'),('bulk','Bulk-edit selected native board task'),('duplicate','Duplicate task through native menu')]:
    add(label,'GET','projects/{project_id}/board',native='board',action=action)
for action,label in [('navigate','Navigate native calendar month/week/day/agenda'),('create','Create event from native calendar')]:
    add(label,'GET','planner',native='planner',action=action)
add('Upload attachment through Android document picker','POST','tasks/{task_id}/attachments',{'file':'PMS-QA-upload.txt'},save='file')
add('Read uploaded attachments','GET','tasks/{task_id}/attachments')
add('Download uploaded bytes and save through Android picker','GET','attachments/{file_id}/download',assert_file=True,save_download=True)
add('Edit uploaded project file metadata','PATCH','files/{file_id}',{'original_name':'PMS-QA-upload-renamed.txt','visibility':'Internal'})
add('Delete uploaded QA attachment','DELETE','attachments/{file_id}')
question={'id':'request_title','type':'text','label':'Request title','required':True,'help':'QA request title','placeholder':'Enter a QA request'}
questions=[question,{'id':'size','type':'select','label':'Size','options':['Small','Large'],'condition':{'field':'request_title','operator':'not_empty','value':''}}, {'id':'score','type':'number','label':'Score','min':0,'max':10}, {'id':'confirmed','type':'checkbox','label':'Confirmed'}]
definition={'name':'QA intake form $run','fields':questions,'description':'Physical Android QA','submit_label':'Send QA response','success_message':'QA saved','accent':'#2255cc','workflow':{'enabled':True,'project_id':'@project','title_field':'request_title','priority':'High','assignee_id':'@user','due_days':2}}
add('Create form with questions options limits conditions and task workflow','POST','workspaces/{wid}/forms',definition,save='form')
add('Publish QA form','PUT','workspaces/{wid}/forms/{fid}',{'definition':definition,'publish':True},save='form')
add('Submit authenticated form and create mapped task','POST','workspaces/{wid}/forms/{fid}/submit',{'version':1,'answers':{'request_title':'QA submitted intake $run','size':'Large','score':3,'confirmed':True}})
add('Read form responses','GET','workspaces/{wid}/forms/{fid}/responses')
add('Export form responses','GET','workspaces/{wid}/forms/{fid}/export')
add('Close form','PUT','workspaces/{wid}/forms/{fid}',{'definition':definition,'close':True},save='form')
take('Create document')
add('Edit document with version protection','PUT','docs/{document_id}',{'title':'QA document updated $run','content':'Updated on physical Android'},save='document')
add('Read previous document revision','GET','docs/{document_id}/revisions/{version}',scope={'version':1})
take('Create dashboard')
add('Edit dashboard identity filters and refresh configuration','PUT','dashboards/{did}',{'name':'QA dashboard updated $run','description':'Android QA layout','icon':'projects','accent':'#2255cc','category':'QA','configuration':{'refresh_seconds':60,'density':'compact'}},save='dashboard')
add('Archive dashboard','PUT','dashboards/{did}',{'archived':True},save='dashboard')
add('Unarchive dashboard','PUT','dashboards/{did}',{'archived':False},save='dashboard')
add('Trash dashboard','POST','dashboards/{did}/trash',save='dashboard')
add('Restore dashboard','POST','dashboards/{did}/restore',save='dashboard')
add('Create manual QA savepoint','POST','workspaces/{workspace_id}/recovery/savepoints',{'name':'QA savepoint $run'},save='point')
add('Modify QA task after savepoint','PATCH','tasks/{task_id}',{'description':'Temporary content to verify QA restore'})
add('Read restore preview without applying','GET','workspaces/{workspace_id}/recovery/savepoints/{point_id}/preview')
add('Enable automatic QA savepoints','PUT','workspaces/{workspace_id}/recovery/policy',{'enabled':True,'interval_hours':24,'retain_automatic':2})
add('Disable automatic QA savepoints','PUT','workspaces/{workspace_id}/recovery/policy',{'enabled':False,'interval_hours':24,'retain_automatic':2})
add('Download QA backup','GET','workspaces/{workspace_id}/recovery/savepoints/{point_id}/download')
add('Restore only the QA workspace savepoint','POST','workspaces/{workspace_id}/recovery/savepoints/{point_id}/restore',{'confirm_name':'$workspace_name'})
add('Verify restored task content','GET','tasks/{task_id}',verify={'description':None})
(r/'integration_test/full_pms_extra_cases.dart').write_text("// Generated device cases; no credentials.\nconst fullPmsExtraCasesJson=r'''"+json.dumps(cases,separators=(',',':'))+"''';\n")
print({'extra_cases':len(cases)})
