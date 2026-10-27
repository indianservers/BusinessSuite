"""The complete set of non-user-authenticated API surfaces.

Each exception has another server-validated capability (HMAC, invitation, applicant,
portal session, or signed file token), or is an intentionally public auth entry.
New routes require ordinary authentication unless explicitly added here.
"""

import re
from fastapi import Depends
from fastapi.routing import APIRoute, request_response
from fastapi.dependencies.utils import get_parameterless_sub_dependant

PUBLIC_CAPABILITIES = (
    r"/power-apps/hooks/[^/]+",
    r"/auth/(login|refresh|forgot-password|reset-password|mfa/verify|firebase/(config|login))",
    r"/auth/sso/(providers/active|initiate/[^/]+|callback/oidc/[^/]+|complete/[^/]+)",
    r"/forms/public/[^/]+(?:/(?:challenge|submit))?",
    r"/public/webforms/[^/]+(?:/submit)?",
    r"/access/services/webhooks/[^/]+/receive",
    r"/internal/cron",
    r"/(?:customer|partner)-portal(?:/.*)?",
    r"/interns-hub/(?:application-options|application-uploads|applications(?:/(?:status|corrections))?|signup/(?:session|providers|firebase))",
    r"/background-verification/webhooks/[^/]+",
    r"/crm/lead-management/(?:capture/[^/]+/[^/]+|booking/[^/]+/[^/]+/[^/]+)",
    r"/project-management/workspace-invitations/(?:preview|activate)",
    r"/project-management/dev-integrations/webhook/(?:github|gitlab)",
)


def is_public(path):
    path = path.removeprefix("/api/v1")
    return any(re.fullmatch(pattern, path) for pattern in PUBLIC_CAPABILITIES)


def dependency_names(dependant):
    yield getattr(dependant.call, "__name__", type(dependant.call).__name__)
    for child in dependant.dependencies:
        yield from dependency_names(child)


def enforce_private_defaults(router, prefix=""):
    from app.core.deps import get_current_user

    for route in router.routes:
        if hasattr(route, "original_router"):
            enforce_private_defaults(
                route.original_router, prefix + route.include_context.prefix
            )
        elif isinstance(route, APIRoute) and not is_public(prefix + route.path):
            if "get_current_user" not in set(dependency_names(route.dependant)):
                dependency = Depends(get_current_user)
                route.dependencies.insert(0, dependency)
                route.dependant.dependencies.insert(
                    0,
                    get_parameterless_sub_dependant(
                        depends=dependency, path=route.path_format
                    ),
                )
                route.app = request_response(route.get_route_handler())
