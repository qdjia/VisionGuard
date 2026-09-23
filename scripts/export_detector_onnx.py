"""Export a detector to a reproducible embedded-NMS ONNX deployment artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--opset", type=int, default=18)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--export-conf-threshold", type=float, default=0.001)
    parser.add_argument("--iou-threshold", type=float, default=0.45)
    parser.add_argument("--max-det", type=int, default=300)
    parser.add_argument("--static", action="store_true", help="Disable dynamic batch axes")
    parser.add_argument("--no-simplify", action="store_true")
    args = parser.parse_args()

    checkpoint = args.checkpoint.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_AUTOINSTALL"] = "false"

    from ultralytics import YOLO

    model = YOLO(str(checkpoint))
    exported = Path(
        model.export(
            format="onnx",
            imgsz=args.imgsz,
            opset=args.opset,
            dynamic=not args.static,
            simplify=not args.no_simplify,
            nms=True,
            batch=args.batch,
            conf=args.export_conf_threshold,
            iou=args.iou_threshold,
            max_det=args.max_det,
            device=args.device,
        )
    ).resolve(strict=True)
    if exported != output:
        shutil.copy2(exported, output)
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "source": {
            "name": checkpoint.name,
            "size_bytes": checkpoint.stat().st_size,
            "sha256": sha256(checkpoint),
        },
        "artifact": {
            "name": output.name,
            "size_bytes": output.stat().st_size,
            "sha256": sha256(output),
        },
        "export": {
            "format": "onnx",
            "image_size": args.imgsz,
            "opset": args.opset,
            "dynamic_axes": not args.static,
            "simplify": not args.no_simplify,
            "embedded_nms": True,
            "maximum_batch": args.batch,
            "export_conf_threshold": args.export_conf_threshold,
            "iou_threshold": args.iou_threshold,
            "max_detections": args.max_det,
            "output_layout": "batch,max_detections,[x1,y1,x2,y2,confidence,class_id]",
        },
        "class_names": model.names,
        "versions": {name: version(name) for name in ("ultralytics", "torch", "onnx", "onnxslim")},
    }
    output.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
