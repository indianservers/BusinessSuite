"""Prepare lazy router metadata before accepting HTTP traffic.

Only BaseRoute.matches is called: no handler, dependency, authorization check or
business-data read is executed. FastAPI invalidates its own route metadata when
registrations change, so this is warm-up rather than an authorization cache.
"""


def prime_routes(app):
    for route in app.router.routes:
        scope = {
            "type": "http", "asgi": {"version": "3.0"},
            "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": "/__suite_route_metadata_warmup__",
            "raw_path": b"/__suite_route_metadata_warmup__", "root_path": "",
            "query_string": b"", "headers": [], "server": ("startup", 80),
            "client": ("127.0.0.1", 0), "app": app,
        }
        route.matches(scope)
