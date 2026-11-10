"""Synthetic intent-language expansion. These are paraphrases, not new capabilities.

Each requested module has 50 utterances for each of its 20 existing intent labels.
Existing examples are retained. No customer query, personal data or secret is used.
"""
from app.ai_operator.local_corpus import FAMILIES
from app.ai_operator.local_features import features

VERSION='platform-synthetic-3000-v1'
READ=['show me','list','display','retrieve','fetch','pull up','bring up','look up','open a list of',
      'let me see','give me a view of','help me locate','tell me about','present','return','find','check','review','load','identify']
OBJECTS={
 'CRM':{
 'leads.list':['visible sales leads','the lead directory','our prospective customers','the CRM lead records','the current prospect list','leads I can access'],
 'leads.search':['leads matching "Acme"','prospects named "Acme"','lead records containing "Acme"','the lead named "Acme"','CRM leads for "Acme"','prospects that match "Acme"'],
 'contacts.list':['customer contact records','the contact directory','visible CRM contacts','people in our contact list','the customer contacts list','business contact entries'],
 'customers.list':['customer company records','the customer account directory','visible customer companies','companies in our CRM','the business customer list','customer organization entries'],
 'deals.list':['sales opportunity records','the deal pipeline','visible CRM deals','our sales opportunities','the CRM opportunity list','deals in my pipeline'],
 'tasks.list':['CRM follow up tasks','the customer task list','visible customer follow ups','our CRM task records','the customer work list','CRM tasks I can access'],
 'tasks.today':['CRM tasks due today','customer follow ups due today','today CRM task deadlines','CRM work with a deadline today','customer tasks scheduled for today','CRM tasks that need completion today'],
 'tasks.overdue':['overdue CRM tasks','late customer follow ups','CRM tasks past their due dates','customer tasks with missed deadlines','CRM work that is overdue','customer follow ups still late'],
 'tasks.blocked':['blocked CRM tasks','stuck customer follow ups','customer tasks marked blocked','CRM work with blockers','CRM tasks that cannot proceed','blocked follow up work'],
 'tasks.mine':['CRM tasks assigned to me','customer follow ups I own','my assigned CRM work','CRM tasks under my responsibility','the customer tasks allocated to me','CRM follow ups assigned to my account'],
 'reminders.today':['my CRM reminders for today','customer reminders due today','today CRM reminder schedule','customer follow up reminders for today','CRM alerts due today','my reminders about CRM work today'],
 'jobs.today':['my CRM priorities for today','the customer jobs I should do today','today customer work priorities','my daily CRM work plan','my CRM jobs for today','the CRM work I need to focus on today'],
 'summary':['a CRM activity summary','the customer relationship overview','a recap of CRM work','an overview of customer activity','a CRM work briefing','a summary of customer follow ups'],
 'risk':['customer delivery risks','CRM deadlines at risk','customer follow up delivery blockers','the CRM delivery risk assessment','customer tasks threatening delivery','CRM work that puts delivery at risk'],
 },
 'PMS':{
 'projects.list':['the project portfolio','visible project records','projects I can access','our project directory','the PMS project list','my accessible projects'],
 'tasks.list':['the project task list','visible PMS tasks','work items in this project','project task records','the tasks for this project','PMS work items'],
 'tasks.today':['project tasks due today','PMS deadlines for today','project work due today','tasks with project deadlines today','today project task schedule','PMS work that needs completion today'],
 'tasks.overdue':['overdue project tasks','late PMS work items','project tasks past their due dates','project work with missed deadlines','PMS tasks that are overdue','late project task records'],
 'tasks.blocked':['blocked project tasks','stuck PMS work items','project work marked blocked','PMS tasks with blockers','project tasks that cannot proceed','the blocked project work list'],
 'tasks.mine':['project tasks assigned to me','my PMS assignments','project work I own','PMS tasks under my responsibility','the project tasks allocated to me','my assigned project work items'],
 'tasks.high':['high priority project tasks','urgent PMS work','critical project tasks','project work marked high priority','the urgent project work list','PMS tasks requiring high priority attention'],
 'tasks.unassigned':['unassigned project tasks','PMS tasks without assignees','project work with no owner','project tasks awaiting assignment','ownerless PMS work items','the unallocated project task list'],
 'reminders.today':['my project reminders for today','PMS reminders due today','today project reminder schedule','project task reminders for today','PMS alerts due today','my reminders about project work today'],
 'jobs.today':['my project priorities for today','the project jobs I should do today','today PMS work priorities','my daily project work plan','my PMS jobs for today','the project work I need to focus on today'],
 'dependencies':['project task dependency links','the task prerequisites','dependencies between project tasks','PMS dependency relationships','project tasks that depend on other tasks','the project dependency list'],
 'capacity':['the project team capacity','PMS resource availability','the team workload capacity','available project team capacity','the project resource capacity scenario','project staffing availability'],
 'playbooks':['saved project playbooks','reusable PMS plans','project automation playbooks','stored project work plans','the saved project memory and playbooks','the project playbook library'],
 'summary':['a project progress summary','the PMS status overview','a recap of project work','an overview of project activity','a project status briefing','a summary of this project'],
 'risk':['project delivery risks','PMS deadlines at risk','project delivery blockers','the project delivery risk assessment','project tasks threatening delivery','PMS work that puts delivery at risk'],
 },
 'HRMS':{
 'directory':['the employee directory','visible staff records','our team member list','the HR employee directory','employees I can access','the colleague directory'],
 'directory.search':['employees matching "Acme"','staff named "Acme"','employee records containing "Acme"','the colleague named "Acme"','HR staff records for "Acme"','employees that match "Acme"'],
 'leave.balance':['my remaining leave balance','my available time off entitlement','my unused leave days','the leave days available to me','my personal leave allowance','my remaining leave entitlement'],
 'leave.mine':['my submitted leave requests','the time off applications I filed','my personal leave applications','leave requests raised by me','the leave I have requested','my own time off request status'],
 'leave.pending':['leave requests awaiting approval','the pending leave approval queue','staff leave awaiting manager review','employee leave approvals still pending','leave applications needing approval','the unapproved leave request list'],
 'leave.team':['the team leave calendar this month','staff time off this month','employees away this month','the monthly team absence calendar','team availability for this month','the staff leave schedule this month'],
 'policies':['published HR policies','the employee policy documents','company leave policy records','staff policy documents','the available HR policy library','published employee guidelines'],
 'tickets.mine':['my HR helpdesk tickets','support requests I raised','my employee helpdesk issues','the HR tickets submitted by me','my personal HR support requests','the support ticket status for my HR requests'],
 'leave.types':['available leave types','configured time off categories','the leave categories I can request','the HR leave type list','allowed leave request categories','available employee leave categories'],
 'ticket.categories':['HR helpdesk categories','available support issue types','the HR ticket category list','configured employee support categories','the HR issue types I can raise','helpdesk request categories'],
 'reminders.today':['my HR reminders for today','HRMS reminders due today','today employee reminder schedule','leave reminders for today','HR alerts due today','my reminders about HR work today'],
 'jobs.today':['my HR priorities for today','the HR jobs I should do today','today HRMS work priorities','my daily HR work plan','my HRMS jobs for today','the HR work I need to focus on today'],
 'payroll':['employee payroll details','staff salary records','employee compensation information','staff bank account details','the confidential payroll information','employee salary payment details'],
 'attendance':['employee attendance today','today staff check in records','the daily employee attendance log','staff attendance for today','today employee check ins','the HR attendance records for today'],
 'leave.rejected':['my rejected leave requests','my declined time off applications','leave applications of mine marked rejected','my leave requests that were declined','my rejected personal leave applications','the declined leave requests I submitted'],
 'summary':['a summary of my HR work','the personal HR activity overview','a recap of my employee requests','an overview of my HR requests','my HRMS work briefing','a summary of my HR support activity'],
 'risk':['HR request delivery risks','overdue employee support issues','HR request deadlines at risk','pending HR blockers','HR support work that needs attention','the HR request risk assessment'],
 }}

CREATE=['create','add','make','prepare','draft']
TASK_OBJECTS=['a task','a work task','a follow up task','a new task','a task entry','a new work task',
              'a follow up work item task','a task record','a work item task','a new follow up task','a scheduled task','a task item']
ACTION_OBJECTS=['task #1','the task #1','work task #1','the work task #1','task record #1','the task record #1',
                'task item #1','the task item #1','work item task #1','the work item task #1','assigned task #1','the assigned task #1',
                'selected task #1','specified task #1','existing task #1','tracked task #1','numbered task #1','identified task #1']


def candidates(module,intent):
    if intent in OBJECTS[module]:
        return [f'{verb} {noun}' for noun in OBJECTS[module][intent] for verb in READ]
    if intent=='tasks.create':
        return [f'{v} {module} {noun} "Review customer response" due tomorrow' for noun in TASK_OBJECTS for v in CREATE]
    if intent=='tasks.priority':
        return [f'{v} {module} {noun} priority to high' for noun in ACTION_OBJECTS for v in ['set','change','update','raise','mark','make']]
    if intent=='tasks.status':
        return [f'{v} {module} {noun} status to done' for noun in ACTION_OBJECTS for v in ['set','change','update','mark','switch','make']]
    if intent=='note.create':
        return [f'{v} {noun} for lead #1: Customer requested a callback' for noun in ['a note','an internal note','a CRM note','a customer note','a lead note','a new note','an internal CRM note','a follow up note','a note entry','a lead record note','a CRM lead note','a customer follow up note'] for v in ['add','record','write','save','prepare','attach']]
    if intent=='leads.message':
        return [f'{v} {noun}' for noun in ['a message to all leads','an email to every lead','outreach to all leads','a message for every lead','an email for all leads','a CRM message to all leads','a customer outreach message to every lead','an outreach email to all leads','a message to every CRM lead','an email message to all leads','a lead outreach message to all leads','a message for all CRM leads','an outbound email to every lead','a personalized email to all leads','a bulk message to every lead','a personalized message to all CRM leads'] for v in ['send','prepare','draft','compose','write','create']]
    if intent=='reminders.create':
        return [f'{v} {noun} for lead #1 tomorrow' for noun in ['a reminder','a CRM reminder','a customer reminder','a follow up reminder','a lead reminder','a task reminder','a customer follow up reminder','a CRM lead reminder','a reminder alert','a reminder notification','a follow up reminder alert','a CRM task reminder'] for v in ['create','set','schedule','add','prepare','arrange']]
    if intent=='milestone.create':
        return [f'{v} {noun} "Client acceptance" due tomorrow' for noun in ['a milestone','a project milestone','a new milestone','a PMS milestone','a delivery milestone','a milestone entry','a milestone record','a project delivery milestone','a new project milestone','a project checkpoint milestone','a release milestone','a milestone item'] for v in CREATE]
    if intent=='tasks.schedule':
        return [f'{v} {noun} starting tomorrow' for noun in ACTION_OBJECTS for v in ['schedule','plan dates for','suggest a schedule for','prepare dates for','draft the schedule for','set a start date for']]
    if intent=='leave.create':
        return [f'{v} {noun} for tomorrow' for noun in ['a leave request','a time off request','a personal leave application','an annual leave request','a new leave application','an employee leave request','a leave application','a personal time off request','a day off leave request','a leave request application','an HR leave request','a new time off application'] for v in ['prepare','create','draft','submit','make','raise']]
    if intent=='ticket.create':
        return [f'{v} {noun} "Laptop access"' for noun in ['an HR ticket','a helpdesk ticket','an HR support ticket','a new HR ticket','an employee helpdesk ticket','an HR helpdesk issue ticket','a support request ticket','a new helpdesk ticket','an employee support ticket','an HR issue ticket','a helpdesk request ticket','an HR assistance ticket'] for v in ['create','raise','open','prepare','submit','log']]
    if intent=='leave.approve':
        return [f'{v} {noun} #1' for noun in ['leave request','employee leave request','staff leave application','time off request','personal leave application','annual leave request','employee time off request','HR leave request','staff time off application','employee leave application','leave approval request','staff leave request'] for v in ['approve','accept','grant','authorize','confirm','permit']]
    raise ValueError((module,intent))


def examples(per_intent=50):
    result=[];seen={}
    for module in ['PMS','CRM','HRMS']:
        for intent,base in FAMILIES[module].items():
            rows=[{'module':module,'intent':intent,'text':f'{module}: {text}'} for text in base]
            for row in rows:
                signature=(module,tuple(sorted(features(row['text']).items())))
                if signature in seen and seen[signature]!=intent:raise ValueError('Conflicting base labels')
                seen[signature]=intent
            for text in candidates(module,intent):
                row={'module':module,'intent':intent,'text':f'{module}: {text}'}
                signature=(module,tuple(sorted(features(row['text']).items())))
                if signature in seen:continue
                rows.append(row);seen[signature]=intent
                if len(rows)==per_intent:break
            if len(rows)!=per_intent:raise ValueError(f'Need more distinct paraphrases: {module}/{intent}: {len(rows)}')
            result.extend(rows)
    return result


def with_platform_baseline(reviewed,scope):
    """Platform retraining retains the released 1,200-command module baseline."""
    return examples(60)+list(reviewed) if scope=={'platform':True} else list(reviewed)
