"""Run the versioned acceptance manifest with this interpreter and emit JUnit evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='../.local/assistant-release-v1.xml')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root/'tests/fixtures/assistant-release-v1.json').read_text(encoding='utf-8'))
    output = Path(args.output)
    if not output.is_absolute(): output = root/output
    output.parent.mkdir(parents=True, exist_ok=True)
    print(manifest['version'] + ': deterministic integration/policy acceptance; live gates remain separate.', flush=True)
    return subprocess.run([sys.executable, '-m', 'pytest', *manifest['suites'], '-q', '--disable-warnings',
                           '--junitxml', str(output)], cwd=root).returncode


if __name__ == '__main__':
    raise SystemExit(main())
