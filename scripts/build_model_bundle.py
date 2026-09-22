"""Assemble a versioned local model bundle and generate its SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, target: Path, *, hardlink: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if hardlink:
        try:
            os.link(source, target)
            return
        except OSError:
            pass
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path, *, hardlink: bool) -> None:
    for item in source.rglob("*"):
        if item.is_file():
            copy_file(item, target / item.relative_to(source), hardlink=hardlink)


def artifact(path: Path, root: Path) -> dict:
    if path.is_file():
        return {
            "path": path.relative_to(root).as_posix(),
            "kind": "file",
            "required": True,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "files": [],
        }
    files = []
    total = 0
    for item in sorted(path.rglob("*")):
        if item.is_file():
            size = item.stat().st_size
            total += size
            files.append(
                {
                    "path": item.relative_to(path).as_posix(),
                    "size_bytes": size,
                    "sha256": sha256(item),
                }
            )
    return {
        "path": path.relative_to(root).as_posix(),
        "kind": "directory",
        "required": True,
        "size_bytes": total,
        "sha256": None,
        "files": files,
    }


def parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--output", type=Path, default=root / "models" / "models-v1")
    value.add_argument(
        "--detector",
        type=Path,
        default=root / "artifacts" / "experiments" / "yolo26n_smoke_640" / "weights" / "best.pt",
    )
    cache = root / "artifacts" / "paddlex_cache" / "official_models"
    value.add_argument("--ocr-detection", type=Path, default=cache / "PP-OCRv6_medium_det")
    value.add_argument("--ocr-recognition", type=Path, default=cache / "PP-OCRv6_medium_rec")
    value.add_argument("--ocr-orientation", type=Path, default=cache / "PP-LCNet_x1_0_textline_ori")
    value.add_argument(
        "--baseline",
        type=Path,
        default=root / "artifacts" / "baseline" / "char_2_4_gbdt_sample_v1",
    )
    value.add_argument(
        "--vlm",
        type=Path,
        default=root / "artifacts" / "modelscope" / "Qwen3-VL-2B-Instruct",
    )
    value.add_argument("--bundle-version", default="models-v1")
    value.add_argument("--hardlink", action="store_true", help="Use hardlinks when possible")
    value.add_argument("--force", action="store_true")
    return value


def main() -> None:
    args = parser().parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        if not args.force:
            raise FileExistsError(f"model bundle already exists: {output}")
        expected_parent = (Path(__file__).resolve().parents[1] / "models").resolve()
        if output.parent != expected_parent:
            raise ValueError(
                "--force only removes a direct child of the repository models directory"
            )
        shutil.rmtree(output)
    sources = {
        "detector": args.detector.resolve(),
        "ocr_detection": args.ocr_detection.resolve(),
        "ocr_recognition": args.ocr_recognition.resolve(),
        "ocr_orientation": args.ocr_orientation.resolve(),
        "baseline": args.baseline.resolve(),
        "vlm": args.vlm.resolve(),
    }
    missing = [f"{name}: {path}" for name, path in sources.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing model sources:\n" + "\n".join(missing))
    destinations = {
        "detector": output / "detector" / "model.pt",
        "ocr_detection": output / "ocr" / "text_detection",
        "ocr_recognition": output / "ocr" / "text_recognition",
        "ocr_orientation": output / "ocr" / "textline_orientation",
        "baseline": output / "baseline" / sources["baseline"].name,
        "vlm": output / "vlm",
    }
    output.mkdir(parents=True)
    for name, source in sources.items():
        target = destinations[name]
        if source.is_file():
            copy_file(source, target, hardlink=args.hardlink)
        else:
            copy_tree(source, target, hardlink=args.hardlink)
    manifest = {
        "schema_version": 1,
        "bundle_version": args.bundle_version,
        "compatible_runtime": {"min_inclusive": "0.1.0", "max_exclusive": "0.2.0"},
        "models": {name: artifact(path, output) for name, path in destinations.items()},
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    size = sum(item.stat().st_size for item in output.rglob("*") if item.is_file())
    print(json.dumps({"output": str(output), "size_bytes": size, "manifest": str(manifest_path)}))


if __name__ == "__main__":
    main()
