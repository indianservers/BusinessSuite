"""Standalone application catalog; no cross-module subscriptions are installed."""
from dataclasses import asdict, dataclass
from typing import Literal

Environment = Literal["development", "testing", "production"]
ENVIRONMENTS = ("development", "testing", "production")
PERMISSIONS = tuple("power_apps_" + action for action in (
    "view", "create", "edit", "delete", "publish", "execute",
    "manage_credentials", "manage_environment", "activity_view",
    "approval_submit", "approval_decide", "approval_manage", "approval_delegate", "approval_audit", "approval_export",
))

@dataclass(frozen=True)
class Application:
    id: str
    name: str
    icon: str
    description: str
    status: str = "planned"
    required_permissions: tuple[str, ...] = ("power_apps_view",)
    feature_flags: tuple[str, ...] = ()
    environments: tuple[str, ...] = ENVIRONMENTS

    def payload(self):
        return {**asdict(self), "route": "/power-apps/" + self.id}

APPLICATIONS = (
    Application("automations", "Automations", "Workflow", "Build reliable workflows, one thoughtful step at a time.", "drafts"),
    Application("approvals", "Approvals", "BadgeCheck", "Give every decision a clear path forward.", "available"),
    Application("forms", "Forms", "ClipboardList", "Turn questions into structured business information."),
    Application("tables", "Tables & Databases", "Database", "A structured home for your business data."),
    Application("app-builder", "App Builder", "PanelsTopLeft", "Shape focused applications around your team."),
    Application("notifications", "Notifications", "BellRing", "Deliver the right update at the right moment."),
    Application("search", "Universal Search", "Search", "Find the resources that move your work forward."),
    Application("dashboards", "Dashboards & Reports", "ChartNoAxesCombined", "Bring your business into clearer view."),
    Application("connectors", "Connectors", "Plug", "Connect tools through governed adapters."),
    Application("documents", "Documents & Templates", "Files", "Create consistent documents from reusable templates."),
    Application("ai-agents", "AI Agents", "Bot", "Prepare permission-aware assistants for your business."),
    Application("activity", "Activity & Audit Center", "History", "A traceable record of changes in your environment.", "available", ("power_apps_view", "power_apps_activity_view")),
)

# Registrations are deployment code, never executable payloads from clients.
COMPONENTS: dict[str, dict] = {}
TEMPLATES: dict[str, dict] = {}

def register_component(key: str, contract: dict):
    if key in COMPONENTS:
        raise ValueError("Component already registered")
    COMPONENTS[key] = contract

def register_template(key: str, application_id: str, definition: dict):
    if application_id not in {app.id for app in APPLICATIONS} or key in TEMPLATES:
        raise ValueError("Invalid template registration")
    TEMPLATES[key] = {"id": key, "application_id": application_id, "definition": definition}
