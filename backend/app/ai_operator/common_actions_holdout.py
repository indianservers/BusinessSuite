"""Frozen synthetic wording, authored separately and never fitted by this release.

One probe for each of the existing 20 intent families in each requested module.
This is a small development evaluation, not production accuracy evidence.
"""
TEXT = {
 'PMS': '''Bring up the accessible project roster
Show the task records belonging to the selected project
Which tasks in the selected project are due today
Show project tasks whose deadlines are already past due
List the selected project's blocked task records
Find the selected project's tasks assigned to me personally
Show the selected project's high priority task records
Which project tasks are still awaiting assignment
Are there project reminders due today
What project jobs ought I to focus on today
Prepare a new project task titled "Verify the export retry behavior"
Change project task #411 priority to medium
Update the status on project task #412 to in progress
Prepare a new milestone titled "Pilot rollout accepted"
Plan dates for task #413 starting next thursday
Show dependency links between the selected project's tasks
Check the selected project team's workload capacity
Inspect the saved playbooks for the selected project
Give an overview of progress in the selected project
Which deadlines create delivery risk for the selected project''',
 'CRM': '''Bring up the lead records visible to my account
Look up leads matching Sequoia
Bring up the customer contact directory
Show the customer company records visible to my account
List sales opportunity records visible to my account
Show the customer follow-up task records
Which CRM follow-up tasks are due today
Find CRM follow-ups whose deadlines are already overdue
List customer follow-ups with blocked status
Show customer tasks that are assigned to me personally
Are there CRM reminders due today
What CRM jobs ought I to focus on today
Prepare a fresh customer follow-up titled "Confirm the distributor trial feedback"
Change CRM task #511 priority to medium
Update the status on CRM task #512 to in progress
Record a private internal note on lead #513: Customer will confirm the revised proposal.
Prepare an outbound email message to every CRM lead
Remind me about lead #514 next thursday
Give an overview of our customer follow-up activity
Which CRM deadlines create customer delivery risk''',
 'HRMS': '''Bring up the directory of visible employees
Look up employee matching Meera
How many days remain in my leave balance
Show the time off applications submitted by me
List leave requests still awaiting manager approval
Show the monthly calendar of team leave
Bring up the published employee policy documents
Show the HR support tickets submitted by me
Which configured leave types may I request
Which issue categories are configured for HR helpdesk tickets
Are there HR reminders due today
What HR jobs ought I to focus on today
Prepare an annual leave request for next thursday
Prepare a fresh HR ticket titled "Request a joining confirmation letter"
Authorize the staff time off application request #611
Show the employee payroll compensation records
Bring up today's staff attendance entries
Which leave applications of mine were rejected
Give an overview of my employee support requests
Which employee support requests have delivery risk''',
}

def examples():
    from app.ai_operator.local_corpus import FAMILIES
    return [{'module':module,'intent':intent,'text':f'{module}: {text}','split':'test'}
        for module,block in TEXT.items() for intent,text in zip(FAMILIES[module],block.splitlines(),strict=True)]
