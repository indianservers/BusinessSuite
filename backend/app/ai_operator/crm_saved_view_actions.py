"""CRM binding for shared reviewed private views."""
from app.apps.crm import task_views as native
from app.ai_operator.private_view_actions import ReviewedPrivateView
service=ReviewedPrivateView('CRM',native,'/crm/tasks','task','Use name=...; queue=overdue; status=In Progress; priority=High; mine=true; sort=due_date:asc; search=....')
preflight,confirmed,prepare=service.preflight,service.confirmed,service.prepare
Update,Remove=service.Update,service.Remove
preview=service.preview
router=service.router()
