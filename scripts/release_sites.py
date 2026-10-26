"""Release one committed revision to registered sites, retaining per-site public config."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sites():
    items = json.loads((ROOT / "deployment/sites.json").read_text(encoding="utf-8"))["sites"]
    seen = set()
    projects = set()
    for item in items:
        if not re.fullmatch(r"[a-z0-9-]+", item["id"]) or item["id"] in seen:
            raise ValueError("Site IDs must be unique lowercase names")
        seen.add(item["id"])
        if item["projectId"] in projects or not item["projectId"].startswith("prj_") or not item["orgId"].startswith("team_"):
            raise ValueError("Each site must identify its own existing project and team")
        projects.add(item["projectId"])
        if item["kind"] not in {"suite", "interns-hub"}:
            raise ValueError("Unsupported site kind")
        from urllib.parse import urlparse
        url = urlparse(item["url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment or url.path:
            raise ValueError("Site URL must be a public HTTPS origin")
        if item["kind"] == "interns-hub":
            config = item["publicConfig"]
            if set(config) != {"apiBaseUrl", "hrmsLoginUrl", "firebaseConfig"}:
                raise ValueError("Only public portal configuration belongs in the registry")
            if set(config["firebaseConfig"]) - {"apiKey", "authDomain", "projectId", "appId", "storageBucket", "messagingSenderId", "measurementId"}:
                raise ValueError("Firebase configuration contains unsupported fields")
            if any(not config["firebaseConfig"].get(key) for key in ["apiKey", "authDomain", "projectId", "appId"]):
                raise ValueError("Firebase public web configuration is incomplete")
            for key in ["apiBaseUrl", "hrmsLoginUrl"]:
                value = urlparse(config[key])
                if value.scheme != "https" or not value.hostname or value.username or value.password or value.query or value.fragment:
                    raise ValueError("Portal URLs must be public HTTPS URLs")
    return items


def run(args, cwd=ROOT, capture=False, env=None):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, text=True, capture_output=capture)
    if result.returncode:
        if capture:
            print(result.stdout[-6000:], flush=True)
            print(result.stderr[-6000:], flush=True)
        raise RuntimeError(f"{args[0]} failed with exit code {result.returncode}")
    return result.stdout.strip() if capture else None


def release(item, commit, portal_dist=None):
    if run(["git", "status", "--porcelain"], capture=True):
        raise RuntimeError("Commit all source changes before deploying")
    vercel = shutil.which("vercel")
    if not vercel:
        raise RuntimeError("Install Vercel CLI 65.1.0 before deploying")
    with tempfile.TemporaryDirectory(prefix="businesssuite-release-") as directory:
        work = Path(directory).resolve()
        if not work.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("Release workspace must stay inside the system temporary directory")
        archive = work / "source.tar"
        run(["git", "archive", "--format=tar", "--output", archive, commit])
        source = work / "source"
        source.mkdir()
        with tarfile.open(archive) as tar:
            tar.extractall(source, filter="data")
        target = source
        if item["kind"] == "interns-hub":
            if portal_dist is None:
                raise RuntimeError("Build the portal first and supply --portal-dist")
            version = json.loads((portal_dist / "release.json").read_text())["commit"]
            if version != commit:
                raise RuntimeError("Portal artifact does not match the source commit; rebuild before deploying")
            portal = source / "frontend/interns-hub"
            shutil.copytree(portal_dist, portal / "dist")
            config = work / "firebase-public.json"
            config.write_text(json.dumps(item["publicConfig"]["firebaseConfig"]))
            target = work / "portal"
            run(["node", portal / "scripts/package-release.mjs", "--output", target,
                 "--api-base-url", item["publicConfig"]["apiBaseUrl"],
                 "--hrms-login-url", item["publicConfig"]["hrmsLoginUrl"], "--firebase-config-file", config])
        (target / ".vercel").mkdir(exist_ok=True)
        (target / ".vercel/project.json").write_text(json.dumps({"projectId": item["projectId"], "orgId": item["orgId"]}))
        args = [vercel, "deploy", "--prod", "--yes", "--scope", item["orgId"], "--cwd", target,
                "--meta", f"fleetCommit={commit}", "--meta", f"fleetSite={item['id']}"]
        if item["kind"] == "interns-hub":
            args.append("--prebuilt")
        else:
            args += ["--archive=tgz", "--build-env", f"SUITE_RELEASE_SHA={commit}"]
        if os.environ.get("VERCEL_TOKEN"):
            args += ["--token", os.environ["VERCEL_TOKEN"]]
        print(f"Deploying {item['id']} from {commit} to {item['url']}", flush=True)
        output = run(args, capture=True)
        print(output[-2000:], flush=True)
        # Exact version check prevents a successful upload being mistaken for a live update.
        request = urllib.request.Request(item["url"] + "/release.json", headers={"Cache-Control": "no-cache"})
        observed = json.load(urllib.request.urlopen(request, timeout=60))
        if observed.get("commit") != commit:
            raise RuntimeError(f"Live version mismatch on {item['url']}: {observed.get('commit')}")
        print(f"Verified {item['id']}: {commit}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site")
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--portal-dist", type=Path)
    args = parser.parse_args()
    items = sites()
    if args.site:
        items = [item for item in items if item["id"] == args.site]
        if not items:
            parser.error("Unknown site ID")
    if args.matrix:
        print(json.dumps({"include": [{"id": item["id"], "kind": item["kind"]} for item in items]}))
        return
    commit = run(["git", "rev-parse", "HEAD"], capture=True)
    for item in items:
        if args.deploy:
            release(item, commit, args.portal_dist.resolve() if args.portal_dist else None)
        else:
            print(f"PLAN {item['id']}: {commit} -> {item['url']} ({item['projectId']})")


if __name__ == "__main__":
    main()
