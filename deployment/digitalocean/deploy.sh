#!/usr/bin/env bash
# Run as the checkout owner, with sudo access to systemctl.
set -Eeuo pipefail
umask 027
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
BASE=/srv/business-suite
exec 9>"$BASE/shared/deploy.lock"
flock -n 9 || { echo 'Another deployment is running.' >&2; exit 1; }
cd "$ROOT"
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) process.exit(1)' || { echo 'Node 22+ is required.' >&2; exit 1; }
sudo -n -l >/dev/null
[[ -z $(git status --porcelain) ]] || { echo 'Commit or stash local changes before deploying.' >&2; exit 1; }
[[ $(git branch --show-current) == main ]] || { echo 'Deployment checkout must be on main.' >&2; exit 1; }
git pull --ff-only origin main
REV=$(git rev-parse HEAD)
RELEASE="$BASE/releases/$(date -u +%Y%m%dT%H%M%S)-${REV:0:12}"
mkdir -p "$RELEASE"
git archive HEAD | tar -x -C "$RELEASE"
ln -s "$BASE/shared/backend.env" "$RELEASE/backend/.env"
python3 -m venv "$RELEASE/.venv"
PY="$RELEASE/.venv/bin/python"
"$PY" -m pip install --disable-pip-version-check -r "$RELEASE/backend/requirements.txt"
ln -s "$BASE/shared/frontend.env" "$RELEASE/frontend/.env.production.local"
export SUITE_RELEASE_SHA="$REV"
npm ci --prefix "$RELEASE/frontend"
npm run build --prefix "$RELEASE/frontend"
# Portal imports shared suite source and needs the suite node_modules above.
ln -s "$BASE/shared/interns.env" "$RELEASE/frontend/interns-hub/.env.production.local"
npm ci --prefix "$RELEASE/frontend/interns-hub"
npm run build --prefix "$RELEASE/frontend/interns-hub"
cp "$BASE/shared/interns-config.js" "$RELEASE/frontend/interns-hub/dist/config.js"
# Config files are private; only their public portal copy may be served by Nginx.
chmod 0640 "$RELEASE/frontend/interns-hub/dist/config.js"
cd "$RELEASE/backend"
"$PY" ../deployment/digitalocean/operations.py preflight
# Stop writers before taking the matching database + uploads recovery copy.
sudo systemctl stop business-suite-jobs.timer business-suite-backup.timer
sudo systemctl stop business-suite-jobs.service business-suite-backup.service business-suite.service
STOPPED=1
trap 'code=$?; if [[ ${STOPPED:-0} == 1 ]]; then echo "Deployment failed. Service remains stopped to protect schema consistency. Recovery: deployment/README.md. Release: $RELEASE" >&2; fi; exit "$code"' ERR
"$PY" ../deployment/digitalocean/operations.py backup
"$PY" scripts/migrate_deployment.py
"$PY" scripts/verify_postgresql_schema.py --suite-only
# Atomic activation; old releases are retained for investigation/recovery.
ln -s "$RELEASE" "$BASE/current.next"
mv -Tf "$BASE/current.next" "$BASE/current"
sudo systemctl start business-suite.service
for attempt in {1..60}; do
    if "$PY" -c 'import httpx; r=httpx.get("http://127.0.0.1:8000/health", timeout=5); r.raise_for_status(); assert r.json().get("db") == "ok" and r.json().get("status") == "healthy"' 2>/dev/null; then
        sudo systemctl start business-suite-jobs.timer business-suite-backup.timer
        STOPPED=0
        echo "Deployed $REV; health check passed."
        exit 0
    fi
    sleep 2
done
sudo systemctl stop business-suite.service
echo 'Health check failed; inspect journalctl -u business-suite. Timers remain stopped.' >&2
exit 1
