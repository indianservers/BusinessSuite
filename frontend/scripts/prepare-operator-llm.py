"""Export pinned SmolLM2 safetensors to TF.js named tensors; requires numpy."""
import argparse
import hashlib
import json
import struct
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
SOURCE_SHA256 = "5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c"


def download_weights(url, target):
    """Resume the contiguous prefix, then download checked HTTP ranges."""
    partial = target.with_suffix('.safetensors.part')
    probe = urllib.request.urlopen(urllib.request.Request(url, headers={'Range': 'bytes=0-7'}), timeout=60)
    if probe.status != 206:
        raise ValueError('Weight host must support range requests')
    total = int(probe.headers['Content-Range'].split('/')[-1])
    probe.close()
    start = partial.stat().st_size if partial.exists() else 0
    # Range writes can leave holes after a failure. Keep a marker so retries
    # never mistake a preallocated, incomplete file for a contiguous prefix.
    marker = target.with_suffix('.resume.json')
    if marker.exists():
        start = json.loads(marker.read_text())['prefix']
    marker.write_text(json.dumps({'prefix': start}))

    def chunk(offset):
        end = min(offset + 4 * 1024 * 1024, total) - 1
        request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-{end}'})
        with urllib.request.urlopen(request, timeout=120) as response:
            if response.status != 206 or response.headers.get('Content-Range') != f'bytes {offset}-{end}/{total}':
                raise ValueError('Unexpected weight range')
            data = response.read()
        if len(data) != end - offset + 1:
            raise ValueError('Incomplete weight download')
        with partial.open('r+b') as file:
            file.seek(offset); file.write(data)

    partial.touch(exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(chunk, range(start, total, 4 * 1024 * 1024)))
    partial.replace(target)
    marker.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "public/models/operator-llm")
    parser.add_argument("--precision", choices=["float32", "uint8"], default="float32")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/"
    cache = Path(__file__).resolve().parents[2] / '.local/operator-llm-source'
    cache.mkdir(parents=True, exist_ok=True)
    for name in ["config.json", "tokenizer.json", "tokenizer_config.json", "README.md", "model.safetensors"]:
        target = (cache if name == 'model.safetensors' else out) / name
        if not target.exists():
            print(f"Downloading {name}", flush=True)
            temporary = out / (name + ".part")
            if name == 'model.safetensors':
                download_weights(base + name, target)
            else:
                urllib.request.urlretrieve(base + name, temporary)
                temporary.replace(target)
    license_path = out / 'LICENSE.txt'
    if not license_path.exists():
        urllib.request.urlretrieve('https://www.apache.org/licenses/LICENSE-2.0.txt', license_path)
    source = cache / "model.safetensors"
    with source.open('rb') as file:
        if hashlib.file_digest(file, 'sha256').hexdigest() != SOURCE_SHA256:
            raise ValueError('Source weights checksum does not match the pinned model')
    with source.open("rb") as file:
        header_size = struct.unpack("<Q", file.read(8))[0]
        header = json.loads(file.read(header_size))
    specs, paths, checksums = [], [], {}
    shard = bytearray()

    def flush():
        if shard:
            name = f"weights-{len(paths) + 1:04d}.bin"
            (out / name).write_bytes(shard)
            paths.append(name)
            checksums[name] = hashlib.sha256(shard).hexdigest()
            shard.clear()

    with source.open("rb") as file:
        for name, spec in header.items():
            if name == "__metadata__":
                continue
            start, end = spec["data_offsets"]
            file.seek(8 + header_size + start)
            raw = file.read(end - start)
            if spec["dtype"] == "BF16":
                values = (np.frombuffer(raw, dtype="<u2").astype(np.uint32) << 16).view(np.float32)
            elif spec["dtype"] in ("F16", "F32"):
                values = np.frombuffer(raw, dtype="<f2" if spec["dtype"] == "F16" else "<f4").astype(np.float32)
            else:
                raise ValueError(f"Unsupported weight dtype: {spec['dtype']}")
            entry = {"name": name, "shape": spec["shape"], "dtype": "float32"}
            if args.precision == "uint8":
                minimum, maximum = float(values.min()), float(values.max())
                scale = (maximum - minimum) / 255 or 1.0
                data = np.clip(np.rint((values - minimum) / scale), 0, 255).astype(np.uint8).tobytes()
                entry["quantization"] = {"dtype": "uint8", "min": minimum, "scale": scale}
            else:
                data = values.astype("<f4").tobytes()
            specs.append(entry)
            for offset in range(0, len(data), 4 * 1024 * 1024):
                shard.extend(data[offset:offset + 4 * 1024 * 1024]); flush()
    config = json.loads((out / "config.json").read_text())
    manifest = {"format": "pms-tfjs-llama-v1", "generatedBy": "prepare-operator-llm.py",
                "modelTopology": config, "weightsManifest": [{"paths": paths, "weights": specs}],
                "userDefinedMetadata": {"source": MODEL, "revision": REVISION, "license": "Apache-2.0",
                                        "precision": args.precision, "sha256": checksums}}
    (out / "model.json").write_text(json.dumps(manifest, indent=2))
    print(f"Exported {len(specs)} tensors, {len(paths)} shards to {out}")


if __name__ == "__main__":
    main()
