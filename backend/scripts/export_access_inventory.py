"""Export registered modules/routes and existing seeded roles without DB writes."""

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("ENVIRONMENT", "test")
from app.main import app
from app.access.catalog import MODULES, ROUTES, ENDPOINT_MODULES
from app.db.init_common_db import COMMON_ROLES, COMMON_PERMISSIONS
from app.db.init_db import SYSTEM_ROLES, SYSTEM_PERMISSIONS


def walk(routes, prefix=""):
    for route in routes:
        if hasattr(route, "original_router"):
            yield from walk(
                route.original_router.routes, prefix + route.include_context.prefix
            )
        else:
            yield prefix, route


def dependencies(item):
    result = []
    for child in getattr(item, "dependencies", []):
        call = child.call
        result.append(
            {
                "name": getattr(call, "__name__", type(call).__name__),
                "permissions": sorted(getattr(call, "permissions", [])),
            }
        )
        result.extend(dependencies(child))
    return result


routes = [
    {
        "path": prefix + route.path,
        "methods": sorted(route.methods),
        "handler": route.endpoint.__module__ + "." + route.endpoint.__name__,
        "module": ENDPOINT_MODULES.get(id(route.endpoint)),
        "dependencies": dependencies(route.dependant),
    }
    for prefix, route in walk(app.routes)
    if hasattr(route, "methods") and hasattr(route, "dependant")
]
modules = [
    {**meta, "registeredOperations": sum(value == key for value in ROUTES.values())}
    for key, meta in MODULES.items()
]
permissions = {
    entry[0]: {"name": entry[0], "description": entry[1], "group": entry[2]}
    for entry in [*SYSTEM_PERMISSIONS, *COMMON_PERMISSIONS]
}
target = ROOT / "docs/qa/suite-access/discovery.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(
        {
            "modules": modules,
            "routes": routes,
            "seededRoles": [*SYSTEM_ROLES, *COMMON_ROLES],
            "seededPermissions": list(permissions.values()),
            "note": "Route dependencies and seeded definitions are an inventory, not proof of exhaustive behavioral authorization. Runtime custom roles/permissions come from the existing database catalog.",
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "modules": len(modules),
            "httpRoutes": len(routes),
            "seededPermissions": len(permissions),
            "seededRoleDefinitions": len(SYSTEM_ROLES) + len(COMMON_ROLES),
        }
    )
)
