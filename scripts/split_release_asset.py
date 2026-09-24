"""Split a large local release asset into ordered, checksummed parts."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--part-size-mib", type=int, default=1900)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.asset.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    part_size = args.part_size_mib * 1024 * 1024
    parts = []
    with source.open("rb") as stream:
        index = 1
        while chunk := stream.read(part_size):
            target = output / f"{source.name}.part{index:02d}"
            target.write_bytes(chunk)
            parts.append(
                {
                    "name": target.name,
                    "index": index,
                    "size_bytes": len(chunk),
                    "sha256": sha256(target),
                }
            )
            index += 1
    manifest = {
        "schema_version": 1,
        "source_name": source.name,
        "source_size_bytes": source.stat().st_size,
        "source_sha256": sha256(source),
        "assembly": "concatenate parts in ascending index order; verify every hash first",
        "parts": parts,
    }
    (output / f"{source.name}.parts.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
