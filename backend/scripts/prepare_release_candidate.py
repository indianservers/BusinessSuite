"""Snapshot release inputs without credentials, dependencies or production data."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TOPS = {'backend', 'frontend', 'shared', 'integrations', 'deployment', 'scripts', 'qa', 'playwright', 'app', '.github'}
ROOT_FILES = {'vercel.json', '.vercelignore', '.gitignore', '.gitattributes', 'README.md'}
SKIP_DIRS = {'node_modules', 'venv', '.venv', '__pycache__', '.pytest_cache',
    'uploads', 'backups', 'dist', 'dist-module-validation', 'recovery_backups', '.vercel'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT / '.local' / 'release-candidates' / f'rc-{stamp}'
    source = output / 'source'
    source.mkdir(parents=True, exist_ok=False)
    names = subprocess.check_output(['git', 'ls-files', '-z', '-c', '-o', '--exclude-standard'], cwd=ROOT)
    files = []
    for name in sorted(set(item.decode('utf-8') for item in names.split(b'\0') if item)):
        p = Path(name)
        if not (p.parts[0] in TOPS or name in ROOT_FILES or name in {
            'docs/qa/release-scope-2026-11-12.json', 'docs/qa/release-readiness-2026-11-09.json'}):
            continue
        if any(part in SKIP_DIRS for part in p.parts) or p.name.startswith('.env'):
            continue
        if p.suffix.lower() in {'.pem', '.key', '.dump', '.log', '.pyc'}:
            continue
        if name.startswith('frontend/public/models/operator-llm/'):
            continue
        original = ROOT / p
        if not original.is_file():
            continue
        content = original.read_bytes()
        if (b'-----BEGIN ' + b'PRIVATE KEY-----') in content or (p.suffix.lower() == '.json' and b'"private_key"' in content):
            continue
        destination = source / p
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        files.append({'path': p.as_posix(), 'bytes': len(content), 'sha256': digest(content)})
    fingerprint = digest(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())
    drifted = [f['path'] for f in files if not (ROOT / f['path']).is_file()
        or digest((ROOT / f['path']).read_bytes()) != f['sha256']]
    manifest = {
        'candidate_sha256': fingerprint,
        'created_at_utc': stamp,
        'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source': 'source', 'file_count': len(files), 'files': files,
        'capture_valid': not drifted, 'source_changed_during_capture': drifted,
        'review_status': 'local candidate; production promotion not approved or performed',
        'exclusions': 'Environment files, private-key JSON/PEM, dependencies, build outputs, uploads, backups, local runtimes and operator model weights.',
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if drifted:
        raise RuntimeError('Source changed while capturing; candidate retained as invalid. Capture again.')
    archive = output / 'source.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for entry in files:
            bundle.write(source / entry['path'], entry['path'])
        bundle.write(output / 'manifest.json', 'candidate-manifest.json')
    print(json.dumps({'candidate': str(output), 'sha256': fingerprint,
        'files': len(files), 'source_archive_bytes': archive.stat().st_size}))


if __name__ == '__main__':
    main()
