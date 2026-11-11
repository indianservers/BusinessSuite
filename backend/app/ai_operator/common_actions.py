"""600 curated everyday requests, not a claim of 600 distinct API capabilities.

Synthetic names/records only. Each module retains its 20 existing intent labels.
Ten concrete requests per label include explicit clarification/native handoffs.
These are authored examples, not a usage-frequency ranking or unseen evaluation.
"""
VERSION = 'common-actions-200-v1'

# One line is one independently listed request. Keep titles quoted so business
# words inside them cannot change the operation or module.
GROUPS = {
 'PMS': {
  'projects.list': '''Show projects I can access
List active project records
Show the project portfolio
Which projects are visible to me
Get the accessible project list
Display my project directory
Find our project records
Show projects available in this workspace
List the projects for my team
Give me the visible project names''',
  'tasks.list': '''Show tasks in this project
List project work items
Get the current project task list
Display this project's tasks
Find visible project tasks
Show the project backlog tasks
List the tasks available in this project
Which project tasks can I access
Show work recorded for this project
Give me the visible PMS task list''',
  'tasks.today': '''Show project tasks due today
List today's project deadlines
Which project tasks must be finished today
Show PMS work with a due date of today
Get today's due project tasks
Find project tasks scheduled to be due today
Display the due-today project queue
Show tasks reaching their project deadline today
List project work due before today ends
What project task deadlines fall today''',
  'tasks.overdue': '''Show overdue project tasks
List late project work
Find project tasks past their deadline
Which project tasks have missed their due date
Display overdue PMS assignments
Show project work with expired deadlines
Get the late project task queue
List project tasks that are past due
Show missed project task deadlines
What project tasks should already be finished''',
  'tasks.blocked': '''Show blocked project tasks
List stuck project work
Which project tasks have blockers
Find blocked work in this project
Display project tasks with blocked status
Get the project blocker list
Show PMS work that is stuck
List tasks blocked in this project
Show project work waiting on blockers
What project tasks cannot move forward because they are blocked''',
  'tasks.mine': '''Show project tasks assigned to me
List my project assignments
What project tasks do I own
Get my PMS work list
Display project work allocated to me
Find tasks assigned to me in this project
Show my current project workload
List the project tasks I am responsible for
Which tasks in this project are mine
Give me my project task assignments''',
  'tasks.high': '''Show high priority project tasks
List urgent project tasks
Find critical project work
Which PMS tasks have high priority
Display the urgent project task queue
Get project tasks marked high priority
Show critical tasks in this project
List high priority PMS assignments
Show project work requiring urgent attention
Which project work items have an urgent priority''',
  'tasks.unassigned': '''Show unassigned project tasks
List project tasks without an owner
Which project tasks have no assignee
Find unallocated project work
Display ownerless project tasks
Get PMS tasks awaiting assignment
Show project work without an assignee
List tasks with no owner in this project
Which project tasks are waiting for assignment
Show unassigned work in the project backlog''',
  'reminders.today': '''Check today's project reminders
Show my PMS reminders for today
List project reminders due today
What project reminders are scheduled today
Get today's project reminder schedule
Display project reminders falling today
Show today's reminder alerts for PMS
Find project reminders due before today ends
Which project reminder notifications are due today
Show the project reminder list for today''',
  'jobs.today': '''What are today's project jobs
Show my project priorities for today
What project work should I do today
List today's PMS jobs
Give me today's project work priorities
What project jobs need my attention today
Show my daily project work plan
What should I work on in this project today
List project jobs to focus on today
Show the project jobs on my plate today''',
  'tasks.create': '''Create a project task called "Prepare the project kickoff agenda"
Add a project task called "Confirm the release acceptance criteria" due tomorrow
Make a project task called "Review the API contract" with high priority
Prepare a fresh project task called "Test the password reset flow"
Draft a project task called "Document the deployment checklist"
Create a project task called "Verify the production backup" due next monday
Add a project task called "Review accessibility findings"
Create a project task called "Run the regression test suite" with low priority
Prepare a project task called "Confirm the client handover checklist"
Create a project task called "Review the sprint demo" and assign it to any eligible user''',
  'tasks.priority': '''Set project task #101 priority to high
Make project task #102 urgent priority
Change project task #103 priority to low
Raise project task #104 priority to high
Update project task #105 priority to medium
Set PMS task #106 priority to critical
Make project task #107 low priority
Change PMS task #108 priority to high
Update project task #109 priority to urgent
Mark project task #110 as high priority''',
  'tasks.status': '''Mark project task #101 as done
Set project task #102 status to in progress
Change PMS task #103 to blocked
Complete project task #104
Finish PMS task #105
Set project task #106 status to to do
Update project task #107 status to done
Mark PMS task #108 as in progress
Change project task #109 to done
Set PMS task #110 status to blocked''',
  'milestone.create': '''Create a project milestone called "Requirements approved"
Add a milestone called "Design sign-off" due tomorrow
Prepare a project milestone called "Development complete"
Draft a milestone called "User acceptance testing complete"
Create a milestone called "Security review complete" due next monday
Make a project milestone called "Production release"
Add a project milestone called "Client training complete"
Create a milestone called "Data migration verified"
Prepare a milestone called "Final customer acceptance"
Create a project milestone called "Project closure approved"''',
  'tasks.schedule': '''Schedule project task #101 starting tomorrow
Plan dates for project task #102 from next monday
Suggest a schedule for task #103 starting today
Prepare task #104 dates starting in 3 days
Schedule task #105 from next friday
Draft task #106 schedule for tomorrow
Schedule project task #107 starting in 2 weeks
Plan dates for task #108 starting next tuesday
Suggest a schedule for project task #109 starting today
Prepare task #110 dates starting next wednesday''',
  'dependencies': '''Show project task dependencies
List task prerequisites in this project
Which project tasks depend on other tasks
Display project dependency links
Find dependency blockers in this project
Get the task dependency list
Show prerequisites for project work
List project task dependency relationships
Show the project dependency graph links
What project work has task dependencies''',
  'capacity': '''Show team capacity for this project
Preview project workload capacity this week
What is the project team's availability
Check project resource capacity
Show a project capacity scenario
Display available project team capacity
What bandwidth does this project team have
Get project workload capacity
Preview resource availability for this project
Show the team's project workload scenario''',
  'playbooks': '''Show saved project playbooks
List reusable project plans
Inspect project playbooks
Show project memory and playbooks
Display saved project automation rules
Get the reusable project playbook list
Show my saved PMS playbooks
List project working preferences in memory
Inspect the project's saved rules
Show available project plan playbooks''',
  'summary': '''Summarize this project's progress
Give me a PMS overview
Show the project status summary
Brief me on current project work
Review this project's activity
Provide a summary of project tasks
Give me a project progress recap
Summarize the current project task status
Show an overview of this project's work
Brief me on this project's delivery status''',
  'risk': '''Show project delivery risk
Which project tasks put delivery at risk
Review project deadline risks
Find project delivery blockers
Show PMS deadlines at risk
Summarize overdue project delivery risk
Which project tasks threaten the delivery date
Review the project's delivery risk signals
Show risks from missed project deadlines
What project delivery risks need attention''',
 },
 'CRM': {
  'leads.list': '''Show leads I can access
List visible lead records
Get our lead list
Display the CRM lead directory
Which leads are available to me
Find our current leads
Show the accessible leads
List my visible sales leads
Give me the CRM lead records
Show leads in my authorized scope''',
  'leads.search': '''Find leads named Cedar
Search leads for Harbor
Look up lead Juniper
Show leads matching Meridian
Locate Beacon leads
Filter leads by Willow
Find leads named Summit
Search leads for Northwind
Look up lead Pinecrest
Show leads matching Riverside''',
  'contacts.list': '''Show CRM contacts
List customer contact records
Get visible business contacts
Display the contact directory
Find contacts I can access
Which contacts are visible to me
Show our customer contact list
List the CRM contact directory
Get accessible contact records
Display contacts in my authorized scope''',
  'customers.list': '''Show customer companies
List visible customers
Get the customer account directory
Display accessible customer companies
Find our customer records
Which customers can I access
Show the CRM company list
List customer organization records
Get visible customer accounts
Display our customer directory''',
  'deals.list': '''Show CRM deals
List visible sales opportunities
Display the deal pipeline
Get accessible deal records
Find our sales opportunities
Which deals can I access
Show the current opportunity list
List CRM opportunity records
Get the visible sales pipeline
Display deals in my authorized scope''',
  'tasks.list': '''Show CRM follow-up tasks
List customer follow-up work
Get the visible CRM task list
Display sales follow-up tasks
Find our CRM work tasks
What CRM tasks can I access
Show tasks recorded in CRM
List accessible follow-up tasks
Display customer work items in CRM
Give me the CRM follow-up task queue''',
  'tasks.today': '''Show CRM tasks due today
List customer follow-ups due today
What sales follow-up tasks are due today
Display today's due CRM work
Get CRM tasks with today's deadline
Find follow-ups reaching their due date today
Show the due-today CRM task queue
List customer work with a deadline of today
What CRM task deadlines fall today
Show follow-up work due before today ends''',
  'tasks.overdue': '''Show overdue CRM tasks
List late customer follow-ups
Find CRM tasks past their due date
What follow-up deadlines have been missed
Display overdue customer work
Get late sales follow-up tasks
Show CRM work with expired deadlines
List follow-ups that are past due
Which CRM tasks should already be completed
Show the overdue CRM follow-up queue''',
  'tasks.blocked': '''Show blocked CRM tasks
List stuck customer follow-ups
Which CRM tasks have blocked status
Find blocked sales follow-up work
Display CRM work waiting on blockers
Get the blocked customer task queue
Show follow-up tasks that are stuck
List customer work with blockers
Which follow-up tasks cannot move forward because they are blocked
Show blocked work recorded in CRM''',
  'tasks.mine': '''Show CRM tasks assigned to me
List my customer follow-ups
What CRM work do I own
Get my sales follow-up assignments
Display the CRM tasks I am responsible for
Find follow-ups assigned to me
Show my current CRM workload
List my CRM task assignments
Which customer follow-up tasks are mine
Give me my CRM work list''',
  'reminders.today': '''Check today's CRM reminders
Show customer reminders due today
List my CRM reminder schedule for today
What follow-up reminders are due today
Get today's customer reminder alerts
Display reminders for CRM work today
Find lead reminders due today
Show today's CRM reminder notifications
Which customer reminders fall today
List reminders for sales follow-ups today''',
  'jobs.today': '''What are today's CRM jobs
Show my customer work priorities for today
What CRM work should I do today
List today's sales follow-up jobs
Give me my CRM priorities today
What customer jobs need my attention today
Show my daily CRM work plan
What CRM work is on my plate today
List customer jobs to focus on today
Show the CRM jobs I should handle today''',
  'tasks.create': '''Create a CRM task called "Call the new inbound lead" due tomorrow
Add a customer follow-up called "Confirm the discovery call"
Prepare a fresh customer follow-up called "Review the renewal quotation"
Create a CRM task called "Send the requested product specification"
Draft a customer follow-up called "Check the proposal decision"
Make a CRM task called "Confirm the purchase order" with high priority
Add a CRM task called "Review the stalled opportunity"
Create a customer follow-up called "Collect the contract signature"
Prepare a CRM task called "Schedule the customer onboarding call"
Create a CRM task called "Request post-delivery feedback" with low priority''',
  'tasks.priority': '''Set CRM task #201 priority to high
Make CRM task #202 urgent priority
Change CRM task #203 priority to low
Raise CRM task #204 priority to high
Update CRM task #205 priority to medium
Set task #206 priority to critical
Make CRM task #207 low priority
Change task #208 priority to high
Update CRM task #209 priority to urgent
Mark CRM task #210 as high priority''',
  'tasks.status': '''Mark CRM task #201 as done
Set CRM task #202 status to in progress
Change CRM task #203 to blocked
Complete CRM task #204
Finish CRM task #205
Set CRM task #206 status to to do
Update CRM task #207 status to done
Mark CRM task #208 as in progress
Change CRM task #209 to done
Set CRM task #210 status to blocked''',
  'note.create': '''Add note to lead #201: Customer requested a callback tomorrow.
Record an internal note for lead #202: Procurement review is pending.
Write a note on lead #203: Product demonstration completed.
Save lead #204 note: Customer asked for the technical specification.
Prepare a note for lead #205: Decision maker will review the quotation.
Attach a note to lead #206: Renewal discussion is planned for Friday.
Add internal note to lead #207: Customer confirmed the preferred meeting time.
Record a note for lead #208: Contract questions need legal review.
Write internal note on lead #209: Proposal feedback received.
Save lead #210 note: Follow-up requested after the product trial.''',
  'leads.message': '''Prepare an email to all leads
Draft a message for all leads
Send an email to every lead
Prepare outreach to all leads
Email all visible leads
Message every CRM lead
Draft a customer outreach email to all leads
Prepare a message to every lead
Send a CRM email message to all leads
Draft an email for every lead''',
  'reminders.create': '''Remind me about lead #201 tomorrow
Set a reminder for CRM task #202
Schedule a CRM reminder for lead #203
Create a customer reminder for task #204 tomorrow
Add a follow-up reminder for lead #205
Prepare a reminder for deal #206
Remind me about CRM task #207 in 3 days
Set a CRM reminder for lead #208 next monday
Create a follow-up reminder for task #209
Schedule a customer reminder for deal #210 tomorrow''',
  'summary': '''Summarize CRM activity
Give me a customer work overview
Show the CRM task summary
Brief me on sales follow-up work
Review customer relationship activity
Provide a summary of CRM work
Give me a CRM activity recap
Summarize the visible customer follow-ups
Show an overview of current CRM work
Brief me on the CRM follow-up queue''',
  'risk': '''Show CRM delivery risk
Which CRM tasks put delivery at risk
Review customer follow-up risks
Find CRM delivery blockers
Show CRM deadlines at risk
Summarize overdue customer work risk
Which follow-ups threaten customer delivery
Review the CRM delivery risk signals
Show risks from missed customer deadlines
What CRM delivery risks need attention''',
 },
 'HRMS': {
  'directory': '''Show the employee directory
List coworkers I can access
Get visible employee directory records
Display the staff directory
Find our employee list
Which employees can I see
Show the company employee directory
List accessible coworker profiles
Get the staff contact directory
Display employees in my authorized scope''',
  'directory.search': '''Find employee named Maya
Search employees for Arjun
Look up colleague Leena
Display staff matching Kiran
Locate employee Nisha
Filter employee directory by Dev
Find employee named Isha
Search employees for Omar
Look up colleague Riya
Display staff matching Asha''',
  'leave.balance': '''Show my leave balance
How much annual leave do I have
Check my remaining leave days
Get my available leave entitlement
Display my unused leave balance
What is my current leave balance
Show my remaining time off balance
Check the leave days available to me
Get my personal leave balance
How many leave days remain for me''',
  'leave.mine': '''Show my leave requests
List the leave applications I submitted
Get my time off request status
Display my personal leave applications
Check the status of my leave requests
What leave requests have I made
Show leave applications submitted by me
List my requested time off
Get my personal leave request history
Display my submitted leave requests''',
  'leave.pending': '''Show pending leave approvals
List leave requests awaiting manager approval
Get the leave approval queue
Which leave requests need review
Display pending staff leave applications
Find leave approvals waiting for a decision
Show employee leave requests pending approval
List leave requests awaiting approval decisions
Get the pending employee leave review queue
Which staff leave applications need approval''',
  'leave.team': '''Show team leave this month
Who is away this month
Display the team leave calendar
Get this month's staff time off calendar
Show approved team leave for this month
Who is absent on leave this month
List this month's employee leave calendar
Display team availability this month
Show staff leave scheduled for this month
Get the monthly team time off view''',
  'policies': '''Show published HR policies
List employee policy documents
Find published staff policies
Display the company leave policies
Get the employee handbook policies
What HR policy documents are available
Show the published employee policy list
List available company HR policies
Find the published staff handbook policies
Display HR policies I can access''',
  'tickets.mine': '''Show my HR tickets
List my employee helpdesk requests
Get my HR support ticket status
Display HR issues I raised
Check my helpdesk tickets
What HR tickets have I created
Show the support requests I submitted
List my HR helpdesk issues
Get my personal HR ticket list
Display my employee support requests''',
  'leave.types': '''Show available leave types
List the time off categories I can request
Get configured leave categories
Which leave types are available to me
Display the leave type list
Find available employee leave types
Show personal time off request categories
List the configured employee leave types
What leave categories can I apply for
Get the available leave request types''',
  'ticket.categories': '''Show HR helpdesk categories
List employee support request categories
Get the available HR issue types
Which helpdesk ticket categories are configured
Display HR support issue categories
Find available helpdesk request types
Show the employee helpdesk category list
List configured HR ticket types
What support categories can I use for an HR ticket
Get the HR helpdesk request category list''',
  'reminders.today': '''Check today's HR reminders
Show my HRMS reminders due today
List employee request reminders for today
What HR reminders are scheduled today
Get today's leave reminder alerts
Display the HR reminder schedule for today
Find HR reminders due before today ends
Show today's employee support reminders
Which HR reminder notifications fall today
List my HR work reminders for today''',
  'jobs.today': '''What are today's HR jobs
Show my HR priorities for today
What employee requests need attention today
List today's HRMS work
Give me today's personal HR work priorities
What HR jobs should I handle today
Show my daily HR work plan
What HR work is on my plate today
List employee support jobs to focus on today
Show the HR requests I should review today''',
  'leave.create': '''Apply for annual leave tomorrow
Request personal leave next monday
Submit a leave request for tomorrow
Create my leave application for next friday
Prepare a time off request for tomorrow
Apply for leave in 3 days
Request a day off tomorrow
Submit my annual leave application
Prepare my personal leave request
Create a leave request for next tuesday''',
  'ticket.create': '''Create an HR ticket called "Correct my attendance entry"
Raise an HR ticket called "Request an employment verification letter"
Open an HR support ticket called "Report a payroll discrepancy"
Prepare an HR ticket called "Update my emergency contact"
Submit an HR ticket called "Request laptop access"
Log an HR ticket called "Check reimbursement request status"
Create a helpdesk ticket called "Clarify leave policy eligibility"
Raise a helpdesk ticket called "Request onboarding documents"
Open an HR ticket called "Report an access card problem"
Create an HR ticket called "Request an experience certificate"''',
  'leave.approve': '''Approve leave request #301
Accept employee leave request #302
Grant leave application #303
Approve staff time off #304
Authorize leave request #305
Confirm leave approval #306
Approve employee leave #307
Accept staff leave application #308
Grant employee time off request #309
Approve leave application #310''',
  'payroll': '''Show employee salaries
Display payroll details
List staff bank account details
Get employee compensation information
Show confidential salary records
Calculate payroll payments
Show employee payroll payment details
Display staff salary records
Get the confidential payroll information
List employee salary payment records''',
  'attendance': '''Show today's employee attendance
Who checked in today
Display staff attendance records
Get employee check-in records
List today's staff check-ins
Show the employee attendance log
Display daily employee attendance
Get today's attendance entries
List staff attendance for today
Show the daily staff check-in log''',
  'leave.rejected': '''Show my rejected leave requests
List my declined leave applications
Find rejected time off requests
Display my leave requests marked rejected
Get my rejected leave applications
Which of my leave requests were declined
Show my declined time off requests
List my personal leave applications marked rejected
Find my rejected annual leave applications
Display the leave requests of mine that were declined''',
  'summary': '''Summarize my HR work
Give me an HRMS overview
Show my HR request summary
Brief me on my employee requests
Review my HR activity
Provide a personal HR work overview
Give me a recap of my HR requests
Summarize my employee support activity
Show an overview of my HR work
Brief me on the status of my HR requests''',
  'risk': '''Show HR request delivery risk
Review pending HR support risks
Find overdue employee support work
Which HR requests need risk review
Summarize HR support blockers
Show employee request risks
Review HR request deadlines at risk
Find HR support issues needing attention
Show risks from overdue HR requests
What HR support delivery risks need attention''',
 },
}

HANDOFF = {'HRMS': {'payroll', 'attendance', 'leave.approve'}}
CLARIFY = {'CRM': {'leads.message', 'reminders.create'}, 'HRMS': {'leave.create'}}

def catalog():
    result=[]
    for module,groups in GROUPS.items():
        number=0
        for intent,block in groups.items():
            for text in block.splitlines():
                number+=1
                behavior=('native_handoff' if intent in HANDOFF.get(module,set()) else
                    'needs_details' if intent in CLARIFY.get(module,set()) else
                    'reviewed_draft' if intent.endswith('.create') or intent in {'tasks.priority','tasks.status','tasks.schedule'} else 'authorized_read')
                result.append({'id':f'{module}-{number:03d}','module':module,'intent':intent,
                    'text':f'{module}: {text}','behavior':behavior})
    return result

def examples():
    return [{k:r[k] for k in ('module','intent','text')} for r in catalog()]
