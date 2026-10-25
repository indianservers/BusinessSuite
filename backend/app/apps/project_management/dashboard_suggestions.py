"""Optional assistant provider integration. Suggestions are validated, never persisted."""

import json
from fastapi import HTTPException
from pydantic import ValidationError
from .dashboard_config import Configuration, WIDGETS, validate_layout


def ai_preview(db, user, request, data):
    from app.ai_agents.api import _require_ai_access, _require_ai_rate_limit
    from app.ai_agents.services.advanced_security import AiDataRedactionService
    from app.ai_operator.models import OperatorProvider
    from app.ai_operator.service import scope_key, require_enabled
    from app.ai_operator.providers import generate_json

    _require_ai_access(user)
    require_enabled(db, user)
    config = (
        db.query(OperatorProvider)
        .filter_by(
            scope_key=scope_key(db, user, data.workspace_id),
            provider=data.provider,
            enabled=True,
            data_sharing_allowed=True,
        )
        .first()
    )
    if not config:
        return None
    _require_ai_rate_limit(db, request, user, bucket="dashboard_layout")
    payload = {
        "request": AiDataRedactionService().redact_text(data.prompt),
        "instructions": "Propose a 12-column dashboard layout using only the supported widget IDs and sources. Return configuration JSON only. Do not invent records, IDs, counts, URLs, people, project data or accomplished actions. Leave ID filters empty. This is a preview; the user must confirm and save it. Use at most 12 widgets with unique IDs, x+w <=12 and no overlapping positions. Unavailable data sources must retain unavailable states.",
        "supported_widgets": [
            {k: s[k] for k in ("id", "title", "source", "requirement")}
            for s in WIDGETS.values()
        ],
    }
    db.commit()  # Never hold business locks while waiting for a provider.
    try:
        output = generate_json(
            db,
            user,
            config,
            prompt=json.dumps(payload),
            schema=Configuration.model_json_schema(),
            output_type=Configuration,
            purpose="dashboard_layout",
        )
        parsed = validate_layout(Configuration.model_validate(output))
        # A model cannot select records or populate links/notes with invented data.
        for filters in [parsed.filters] + [
            w.filters for w in parsed.widgets if w.filters
        ]:
            filters.project_ids = []
            filters.assignee_ids = []
            filters.team_ids = []
            filters.sprint_ids = []
            filters.tag_ids = []
            filters.custom_field_id = None
            filters.custom_field_value = ""
        for widget in parsed.widgets:
            widget.url = ""
            widget.notes = ""
            widget.drilldown = False
        db.commit()
        return {
            "mode": "ai",
            "configuration": parsed.model_dump(mode="json"),
            "message": "AI layout preview. No project records were sent or changed. Review before applying; Save dashboard persists your confirmed layout.",
        }
    except (HTTPException, ValidationError, ValueError):
        db.commit()  # Keep sanitized provider telemetry, not partial dashboard writes.
        raise HTTPException(
            422,
            "The provider could not produce a valid dashboard layout. Use guided mode or edit manually.",
        )
