"""HRMS binding for shared reviewed private views."""
from app.apps.hrms import ticket_views as native
from app.ai_operator.private_view_actions import ReviewedPrivateView
service=ReviewedPrivateView('HRMS',native,'/hrms/helpdesk','ticket|helpdesk','Use name=...; status=Open; priority=High; assigned_to_me=true; my_tickets=false. Supported statuses: Open, In Progress, Pending, Resolved, Closed; priorities: Low, Medium, High, Critical.')
preflight,confirmed,prepare=service.preflight,service.confirmed,service.prepare
Update,Remove=service.Update,service.Remove
preview=service.preview
router=service.router()
