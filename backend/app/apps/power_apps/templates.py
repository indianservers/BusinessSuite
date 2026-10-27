"""Versioned, deployment-owned template definitions; no module adapters are installed."""
import json
from copy import deepcopy
from pathlib import Path
from app.apps.power_apps.graph import VisualWorkflowDefinition

TEMPLATES = json.loads(Path(__file__).with_name("automation_templates.json").read_text(encoding="utf-8"))["templates"]
for item in TEMPLATES:
    VisualWorkflowDefinition.model_validate(item["definition"])

def template_by_id(key):
    return next((deepcopy(row) for row in TEMPLATES if row["id"] == key), None)
