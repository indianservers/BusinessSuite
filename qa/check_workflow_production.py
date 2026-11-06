"""Read-only deployment probes. Never logs in or changes production records."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ["app.dsbchartered.com", "app.indianservers.com"]


def probe(host):
    result = {"host": host, "checks": {}}
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for path in ["/health", "/release.json", "/api/v1/openapi.json", "/api/v1/project-management/transition-approvals/inbox"]:
            try:
                response = client.get(f"https://{host}{path}")
                item = {"status": response.status_code, "final_url": str(response.url)}
                try: data = response.json()
                except ValueError: data = None
                if path == "/health" and isinstance(data, dict):
                    item["health"] = {key: data[key] for key in ["status", "db"] if key in data}
                if path == "/release.json" and isinstance(data, dict):
                    item["release"] = {key: data[key] for key in ["commit", "version", "builtAt"] if key in data}
                if path.endswith("openapi.json"):
                    item["workflow_paths"] = [key for key in (data or {}).get("paths", {})
                                              if "workflow-scheme" in key or "transition-approval" in key] if isinstance(data, dict) else []
                result["checks"][path] = item
            except httpx.HTTPError as exc:
                result["checks"][path] = {"error": type(exc).__name__}
    return result


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=2) as pool:
        report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
                  "scope": "Unauthenticated, read-only health, release and route availability; not live end-to-end acceptance",
                  "sites": list(pool.map(probe, HOSTS))}
    destination = ROOT / "outputs" / "workflow-production-probes.json"
    destination.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
