#!/usr/bin/env python
"""Resolve, license-check, and download pinned Wikimedia Commons regression images."""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import URLError

from visionguard.evaluation.historical import (
    HistoricalImageRecord,
    HistoricalImageSource,
    coverage,
    load_jsonl,
    sha256,
    validate_resolved,
    validate_sources,
)

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "VisionGuard-Acceptance/1.0 (https://github.com/qdjia/VisionGuard)"
RETRY_DELAYS_SECONDS = (0, 2, 5)


def clean_html(value: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def open_url(request: urllib.request.Request, timeout: int):
    last_error: Exception | None = None
    for delay in RETRY_DELAYS_SECONDS:
        if delay:
            time.sleep(delay)
        try:
            return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
        except (TimeoutError, ConnectionError, URLError) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def query_commons(title: str) -> dict:
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "titles": title,
            "prop": "imageinfo|revisions",
            "iiprop": "url|extmetadata|size|mime|sha1",
            "iiurlwidth": "1600",
            "rvprop": "ids",
            "format": "json",
            "formatversion": "2",
        }
    )
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    with open_url(request, timeout=60) as response:
        payload = json.load(response)
    pages = payload.get("query", {}).get("pages", [])
    if len(pages) != 1 or pages[0].get("missing"):
        raise RuntimeError(f"Commons file not found: {title}")
    return pages[0]


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with open_url(request, timeout=180) as response:
        content = response.read()
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(target)


def resolve(source: HistoricalImageSource, asset_dir: Path) -> HistoricalImageRecord:
    page = query_commons(source.commons_title)
    info = page["imageinfo"][0]
    metadata = info.get("extmetadata", {})
    mime_type = "image/jpeg" if info["mime"] == "image/tiff" else info["mime"]
    if mime_type not in {"image/jpeg", "image/png"}:
        raise RuntimeError(f"unsupported image MIME for {source.case_id}: {mime_type}")
    download_url = info.get("thumburl") or info["url"]
    extension = mimetypes.guess_extension(mime_type) or ".bin"
    if extension == ".jpe":
        extension = ".jpg"
    filename = f"{source.case_id}{extension}"
    target = asset_dir / filename
    if not target.exists():
        download(download_url, target)
    revision = page.get("revisions", [{}])[0].get("revid") or page.get("lastrevid")
    record = HistoricalImageRecord(
        **source.model_dump(mode="json"),
        filename=filename,
        source_page_url=info["descriptionurl"],
        download_url=download_url,
        license_name=metadata.get("LicenseShortName", {}).get("value", ""),
        license_url=metadata.get("LicenseUrl", {}).get("value"),
        artist=clean_html(metadata.get("Artist", {}).get("value")) or "Unknown",
        attribution_required=(
            metadata.get("AttributionRequired", {}).get("value", "true").casefold() != "false"
        ),
        commons_page_id=page["pageid"],
        commons_revision_id=revision,
        commons_sha1=info["sha1"],
        sha256=sha256(target),
        size_bytes=target.stat().st_size,
        width=info.get("thumbwidth") or info["width"],
        height=info.get("thumbheight") or info["height"],
        mime_type=mime_type,
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources", type=Path, default=Path("data/regression/real_image_sources.jsonl")
    )
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    sources = load_jsonl(args.sources, HistoricalImageSource)
    errors = validate_sources(sources)
    if errors:
        raise SystemExit("\n".join(errors))
    asset_dir = args.asset_dir.resolve()
    asset_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for source in sources:
        print(f"Resolving {source.case_id}: {source.commons_title}", flush=True)
        records.append(resolve(source, asset_dir))
    errors = validate_resolved(records, asset_dir)
    if errors:
        raise SystemExit("\n".join(errors))
    target = args.manifest_output.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(item.model_dump_json() + "\n" for item in records), encoding="utf-8"
    )
    report = coverage(records)
    report["asset_dir"] = str(asset_dir)
    report["manifest"] = str(target)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
