from __future__ import annotations

from typing import Any


def schema(properties: dict[str, dict[str, Any]], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


def s(description: str = "") -> dict[str, Any]:
    return {"type": "string", "description": description}


def i(description: str = "") -> dict[str, Any]:
    return {"type": "integer", "description": description}


def arr(description: str = "") -> dict[str, Any]:
    return {"type": "array", "description": description}


def obj(description: str = "") -> dict[str, Any]:
    return {"type": "object", "description": description}


def enum(values: list[str], description: str = "") -> dict[str, Any]:
    return {"type": "string", "enum": values, "description": description}
