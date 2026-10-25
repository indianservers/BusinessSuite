from __future__ import annotations
from app.access.catalog import permission_objects

from sqlalchemy.orm import Session

from app.ai_agents.models import AiAgent, AiAgentTool
from app.ai_agents.tools.definitions import ALL_TOOL_DEFINITIONS, AiToolDefinition
from app.models.user import User


class AiToolDefinitionBuilder:
    def __init__(self, db: Session):
        self.db = db

    def allowed_tool_definitions(self, *, agent: AiAgent, user: User) -> list[AiToolDefinition]:
        active_names = {
            row.tool_name
            for row in self.db.query(AiAgentTool)
            .filter(AiAgentTool.agent_id == agent.id, AiAgentTool.is_active == True)
            .all()
        }
        tools: list[AiToolDefinition] = []
        for tool in ALL_TOOL_DEFINITIONS:
            if tool.tool_name not in active_names:
                continue
            if agent.code not in tool.allowed_agent_codes:
                continue
            if not self._has_permission(user, tool.required_permission):
                continue
            tools.append(tool)
        return tools

    def openai_tools(self, *, agent: AiAgent, user: User) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.tool_name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self.allowed_tool_definitions(agent=agent, user=user)
        ]

    def _has_permission(self, user: User, permission: str) -> bool:
        if not permission or user.is_superuser:
            return True
        permissions = {item.name for item in (permission_objects(user))}
        return permission in permissions or "*" in permissions
