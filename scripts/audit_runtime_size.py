"""Generate reproducible file, directory, extension, and component size reports."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


def component(path: str) -> str:
    value = path.lower().replace("\\", "/")
    filename = value.rsplit("/", 1)[-1]
    cuda_markers = (
        "cublas",
        "cudnn",
        "cufft",
        "curand",
        "cusolver",
        "cusparse",
        "cupti",
        "nvjitlink",
        "nvrtc",
        "nvperf",
    )
    if any(marker in filename for marker in cuda_markers):
        return "CUDA/cuDNN libraries"
    rules = (
        ("PyTorch", ("_internal/torch/", "_internal/torchvision/")),
        ("Paddle", ("_internal/paddle/",)),
        ("PaddleX", ("_internal/paddlex/",)),
        ("PaddleOCR", ("_internal/paddleocr/",)),
        ("Ultralytics", ("_internal/ultralytics/",)),
        (
            "Transformers/Hugging Face",
            ("_internal/transformers/", "_internal/tokenizers/", "_internal/hf_"),
        ),
        ("OpenCV", ("_internal/cv2/",)),
        ("NumPy", ("_internal/numpy",)),
        ("SciPy", ("_internal/scipy",)),
        ("scikit-learn", ("_internal/sklearn/",)),
        ("Polars", ("_internal/_polars", "_internal/polars/")),
        ("Matplotlib", ("_internal/matplotlib/",)),
        ("FastAPI/Uvicorn", ("_internal/fastapi/", "_internal/uvicorn/", "_internal/starlette/")),
    )
    for name, prefixes in rules:
        if any(value.startswith(prefix) for prefix in prefixes):
            return name
    return "Others"


def row(path: str, size: int) -> dict:
    return {"path": path, "size_bytes": size, "size_mib": round(size / 1024**2, 3)}


def build_report(root: Path) -> dict:
    files = []
    component_sizes: dict[str, int] = defaultdict(int)
    directory_sizes: dict[str, int] = defaultdict(int)
    extension_sizes: dict[str, int] = defaultdict(int)
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        relative = item.relative_to(root).as_posix()
        size = item.stat().st_size
        files.append((relative, size))
        component_sizes[component(relative)] += size
        extension_sizes[item.suffix.lower() or "<none>"] += size
        parent = Path(relative).parent
        while str(parent) not in {".", ""}:
            directory_sizes[parent.as_posix()] += size
            parent = parent.parent
    total = sum(size for _, size in files)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime_root_name": root.name,
        "total_size_bytes": total,
        "file_count": len(files),
        "top_files": [row(path, size) for path, size in sorted(files, key=lambda x: -x[1])[:50]],
        "top_directories": [
            row(path, size)
            for path, size in sorted(directory_sizes.items(), key=lambda x: -x[1])[:30]
        ],
        "components": [
            {
                "name": name,
                "size_bytes": size,
                "size_mib": round(size / 1024**2, 3),
                "percent": round(size * 100 / total, 3) if total else 0,
            }
            for name, size in sorted(component_sizes.items(), key=lambda x: -x[1])
        ],
        "extensions": [
            {
                "extension": extension,
                "size_bytes": size,
                "size_mib": round(size / 1024**2, 3),
            }
            for extension, size in sorted(extension_sizes.items(), key=lambda x: -x[1])
        ],
    }


def markdown(report: dict) -> str:
    lines = [
        "# Runtime Size Audit",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"Reference Runtime: `{report['total_size_bytes']:,}` bytes "
        f"(`{report['total_size_bytes'] / 1024**3:.3f} GiB`), "
        f"`{report['file_count']:,}` files.",
        "",
        "## Component breakdown",
        "",
        "| Component | Bytes | MiB | Share |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {item['name']} | {item['size_bytes']:,} | {item['size_mib']:,.3f} | "
        f"{item['percent']:.3f}% |"
        for item in report["components"]
    )
    lines.extend(["", "## Top 50 largest files", "", "| File | Bytes | MiB |", "|---|---:|---:|"])
    lines.extend(
        f"| `{item['path']}` | {item['size_bytes']:,} | {item['size_mib']:,.3f} |"
        for item in report["top_files"]
    )
    lines.extend(
        ["", "## Top 30 largest directories", "", "| Directory | Bytes | MiB |", "|---|---:|---:|"]
    )
    lines.extend(
        f"| `{item['path']}` | {item['size_bytes']:,} | {item['size_mib']:,.3f} |"
        for item in report["top_directories"]
    )
    lines.extend(
        ["", "## Largest extension groups", "", "| Extension | Bytes | MiB |", "|---|---:|---:|"]
    )
    lines.extend(
        f"| `{item['extension']}` | {item['size_bytes']:,} | {item['size_mib']:,.3f} |"
        for item in report["extensions"][:20]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.runtime.expanduser().resolve(strict=True))
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"bytes": report["total_size_bytes"], "files": report["file_count"]}))


if __name__ == "__main__":
    main()
