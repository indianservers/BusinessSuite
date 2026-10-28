#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential libpq-dev \
    postgresql postgresql-client redis-server nginx git curl ca-certificates \
    certbot python3-certbot-nginx
id businesssuite >/dev/null 2>&1 || useradd --create-home --shell /bin/bash businesssuite
install -d -o businesssuite -g businesssuite -m 0755 /srv/business-suite
install -d -o businesssuite -g businesssuite -m 0750 \
    /srv/business-suite/releases /srv/business-suite/shared /srv/business-suite/shared/uploads
usermod -a -G businesssuite www-data
for name in backend frontend interns backup; do
    target="/srv/business-suite/shared/$name.env"
    if [[ ! -e $target ]]; then
        install -o businesssuite -g businesssuite -m 0600 \
            "$ROOT/deployment/digitalocean/$name.env.example" "$target"
    fi
done
if [[ ! -e /srv/business-suite/shared/interns-config.js ]]; then
    install -o businesssuite -g businesssuite -m 0600 \
        "$ROOT/deployment/digitalocean/interns-config.js.example" /srv/business-suite/shared/interns-config.js
fi
install -m 0644 "$ROOT"/deployment/digitalocean/business-suite*.service /etc/systemd/system/
install -m 0644 "$ROOT"/deployment/digitalocean/business-suite*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable postgresql redis-server nginx business-suite.service \
    business-suite-jobs.timer business-suite-backup.timer
systemctl start postgresql redis-server
cat > /etc/sudoers.d/business-suite <<'EOF'
businesssuite ALL=(root) NOPASSWD: /usr/bin/systemctl stop business-suite-jobs.timer business-suite-backup.timer
businesssuite ALL=(root) NOPASSWD: /usr/bin/systemctl stop business-suite-jobs.service business-suite-backup.service business-suite.service
businesssuite ALL=(root) NOPASSWD: /usr/bin/systemctl start business-suite.service
businesssuite ALL=(root) NOPASSWD: /usr/bin/systemctl stop business-suite.service
businesssuite ALL=(root) NOPASSWD: /usr/bin/systemctl start business-suite-jobs.timer business-suite-backup.timer
EOF
chmod 0440 /etc/sudoers.d/business-suite
visudo -cf /etc/sudoers.d/business-suite
echo 'Host prepared. Configure credentials, Node 22+, Nginx and HTTPS as described in deployment/README.md.'
