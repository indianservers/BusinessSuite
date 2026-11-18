"""Unmasked pixel comparisons of the real UI captures with the supplied references.

Run frontend/scripts/test-appointments-complete.cjs first. This reports actual error;
it never substitutes the reference screenshot into the UI or masks differences.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = {
    'resources': '10d0ba94-bdbb-41d1-924d-8b6506591a26',
    'schedule': '735944e8-846a-477a-8346-3c6288c7e6a3',
    'booking': '1a30f083-8c11-4c07-9584-bab922c8ee6c',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dir', type=Path, default=Path('C:/Users/SAISAT~1/AppData/Local/Temp'))
    parser.add_argument('--label', default='after')
    parser.add_argument('--capture-prefix', default='appointments-complete', help='Use appointments-reference for the screenshot-state fixture capture.')
    parser.add_argument('--require-exact', action='store_true', help='Fail unless every unmasked pixel matches.')
    args = parser.parse_args()
    report = {}
    for name, identity in REFERENCES.items():
        reference = Image.open(args.reference_dir / f'codex-clipboard-{identity}.png').convert('RGB')
        capture = Image.open(ROOT / 'output' / f'{args.capture_prefix}-{name}-1586.png').convert('RGB')
        if reference.size != capture.size:
            raise ValueError(f'{name}: sizes differ: {reference.size} versus {capture.size}')
        delta = np.abs(np.asarray(reference).astype(np.int16) - np.asarray(capture).astype(np.int16))
        different = np.any(delta != 0, axis=2)
        report[name] = {
            'size': list(reference.size),
            'total_pixels': int(different.size),
            'different_pixels': int(different.sum()),
            'identical_pixels_percent': round(float((~different).mean() * 100), 4),
            'mean_absolute_channel_error': round(float(delta.mean()), 4),
            'pixels_with_channel_error_over_20_percent': round(float(np.any(delta > 20, axis=2).mean() * 100), 4),
            'exact_match': not bool(different.any()),
        }
        Image.blend(reference, capture, .5).save(ROOT / 'output' / f'appointments-pixel-{name}-overlay.png')
        Image.fromarray(np.clip(delta * 3, 0, 255).astype(np.uint8)).save(ROOT / 'output' / f'appointments-pixel-{name}-diff.png')
    target = ROOT / 'output' / f'appointments-pixel-{args.label}.json'
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if args.require_exact and not all(row['exact_match'] for row in report.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
