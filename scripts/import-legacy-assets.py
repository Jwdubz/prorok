#!/usr/bin/env python3
"""Fetch Dylan's published Squarespace images into a controlled local WebP library.

Reads the frozen URL-level inventory. Appends ?format=1500w for the fetch only.
Does not treat public availability as a rights claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prorok_assets import (  # noqa: E402
    FROZEN_MANIFEST,
    LOCAL_MANIFEST,
    ROOT,
    fetch_url,
    labels_for,
    local_relpath,
)

USER_AGENT = (
    "ProrokLocalArchive/1.0 "
    "(private local worktree recovery for Dylan Prorok; "
    "+https://prorok.jarrettwroten.com/)"
)
MAX_LONG_EDGE = 1600
WEBP_QUALITY = 82
WEBP_METHOD = 6
CONNECT_TIMEOUT = 20
READ_TIMEOUT = 90
RETRIES = 4
WORKERS = 6
SUMI = (20, 16, 14)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv() -> list[dict]:
    with FROZEN_MANIFEST.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_previous() -> dict[str, dict]:
    if not LOCAL_MANIFEST.exists():
        return {}
    try:
        payload = json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {row["asset_id"]: row for row in payload.get("assets", [])}


def decode_and_convert(raw: bytes) -> tuple[bytes, int, int]:
    with Image.open(BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode in {"RGBA", "LA", "P"}:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, SUMI)
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        width, height = image.size
        long_edge = max(width, height)
        if long_edge > MAX_LONG_EDGE:
            scale = MAX_LONG_EDGE / long_edge
            image = image.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.LANCZOS,
            )
            width, height = image.size
        clean = Image.new("RGB", image.size)
        clean.paste(image)
        buffer = BytesIO()
        clean.save(
            buffer,
            format="WEBP",
            quality=WEBP_QUALITY,
            method=WEBP_METHOD,
            exact=False,
        )
        return buffer.getvalue(), width, height


def existing_output_ok(path: Path) -> tuple[bool, int, int]:
    if not path.exists() or path.stat().st_size == 0:
        return False, 0, 0
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            return width > 0 and height > 0, width, height
    except OSError:
        return False, 0, 0


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/*,*/*;q=0.8",
        },
        method="GET",
    )
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=READ_TIMEOUT) as response:
                data = response.read()
            if not data:
                raise OSError("empty response body")
            return data
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < RETRIES:
                time.sleep(min(8, 1.5 * attempt))
    raise RuntimeError(f"fetch failed after {RETRIES} attempts: {last_error}")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    ) as handle:
        handle.write(data)
        handle.flush()
        temp_name = handle.name
    Path(temp_name).replace(path)


def record_for(
    row: dict,
    rows: list[dict],
    local_path: Path,
    downloaded_sha: str,
    output_sha: str,
    width: int,
    height: int,
    status: str,
    error: str = "",
) -> dict:
    alt, caption = labels_for(row, rows)
    return {
        "asset_id": row["asset_id"],
        "source_url": row["source_url"],
        "fetch_url": fetch_url(row["source_url"]),
        "local_path": local_path.as_posix(),
        "downloaded_sha256": downloaded_sha,
        "output_sha256": output_sha,
        "width": width,
        "height": height,
        "source_category": row["source_category"],
        "source_subcategory": row["source_subcategory"],
        "source_routes": row["source_routes"],
        "page_order": row["page_order"],
        "alt": alt,
        "caption": caption,
        "legacy_alt_or_description": row["legacy_alt_or_description"],
        "duplicate_group": row["duplicate_group"],
        "duplicate_relationship": row["duplicate_relationship"],
        "current_repo_match": row["current_repo_match"],
        "current_match_basis": row["current_match_basis"],
        "rights_status": "confirmation-required",
        "technical_reuse_status": row["technical_reuse_status"],
        "status": status,
        "error": error,
    }


def write_manifest(rows: list[dict], assets: list[dict], failures: list[dict]) -> None:
    by_id = {item["asset_id"]: item for item in assets}
    ordered = [by_id[row["asset_id"]] for row in rows if row["asset_id"] in by_id]
    created = [item for item in ordered if item["status"] in {"ok", "reused"}]
    counts: dict[str, dict[str, int]] = {}
    for item in created:
        bucket = counts.setdefault(
            item["source_category"],
            {"expected": 0, "created": 0, "decoded": 0},
        )
        bucket["created"] += 1
        if item["width"] > 0 and item["height"] > 0:
            bucket["decoded"] += 1
    expected_by_cat: dict[str, int] = {}
    for row in rows:
        expected_by_cat[row["source_category"]] = expected_by_cat.get(row["source_category"], 0) + 1
    for cat, expected in expected_by_cat.items():
        counts.setdefault(cat, {"expected": 0, "created": 0, "decoded": 0})
        counts[cat]["expected"] = expected
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": FROZEN_MANIFEST.relative_to(ROOT).as_posix(),
        "rights_note": (
            "Public availability is not a rights claim. "
            "Every row keeps rights_status=confirmation-required."
        ),
        "conversion": {
            "format": "webp",
            "quality": WEBP_QUALITY,
            "method": WEBP_METHOD,
            "max_long_edge": MAX_LONG_EDGE,
            "exif_transpose": True,
            "strip_metadata": True,
        },
        "counts": counts,
        "expected": len(rows),
        "created": len(created),
        "decoded": sum(1 for item in created if item["width"] > 0 and item["height"] > 0),
        "failures": failures,
        "assets": ordered,
    }
    LOCAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(LOCAL_MANIFEST, json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))


def process_row(
    row: dict,
    rows: list[dict],
    previous: dict[str, dict],
    force: bool,
) -> dict:
    dest = ROOT / local_relpath(row)
    ok, width, height = existing_output_ok(dest)
    if ok and not force:
        prior = previous.get(row["asset_id"], {})
        return record_for(
            row,
            rows,
            local_relpath(row),
            prior.get("downloaded_sha256", ""),
            sha256_file(dest),
            width,
            height,
            "reused",
        )
    try:
        raw = fetch_bytes(fetch_url(row["source_url"]))
        converted, width, height = decode_and_convert(raw)
        if width <= 0 or height <= 0:
            raise RuntimeError("converted image has zero dimensions")
        atomic_write(dest, converted)
        return record_for(
            row,
            rows,
            local_relpath(row),
            sha256_bytes(raw),
            sha256_bytes(converted),
            width,
            height,
            "ok",
        )
    except Exception as exc:  # noqa: BLE001 - bounded fetch/convert must continue
        return record_for(
            row,
            rows,
            local_relpath(row),
            "",
            "",
            0,
            0,
            "failed",
            str(exc),
        )


def print_report(rows: list[dict], assets: list[dict]) -> int:
    expected = len(rows)
    created = [item for item in assets if item["status"] in {"ok", "reused"}]
    decoded = [item for item in created if item["width"] > 0 and item["height"] > 0]
    failures = [item for item in assets if item["status"] == "failed"]
    print("IMPORTER VALIDATION")
    print(f"expected {expected}")
    print(f"created {len(created)}")
    print(f"decoded {len(decoded)}")
    by_cat: dict[str, dict[str, int]] = {}
    for row in rows:
        by_cat.setdefault(row["source_category"], {"expected": 0, "created": 0, "decoded": 0})
        by_cat[row["source_category"]]["expected"] += 1
    created_ids = {item["asset_id"] for item in created}
    decoded_ids = {item["asset_id"] for item in decoded}
    for row in rows:
        cat = row["source_category"]
        if row["asset_id"] in created_ids:
            by_cat[cat]["created"] += 1
        if row["asset_id"] in decoded_ids:
            by_cat[cat]["decoded"] += 1
    for cat in ("tattoo", "flash", "art", "merch"):
        bucket = by_cat.get(cat, {"expected": 0, "created": 0, "decoded": 0})
        print(
            f"  {cat}: expected {bucket['expected']} "
            f"created {bucket['created']} decoded {bucket['decoded']}"
        )
    paths = [item["local_path"] for item in created]
    unique_paths = set(paths)
    if len(paths) != len(unique_paths):
        print("FAIL duplicate local paths")
        return 1
    if failures:
        print("FAILURES")
        for item in failures:
            print(f"  {item['asset_id']} {item['source_url']} :: {item['error']}")
    else:
        print("FAILURES none")
    return 0 if len(decoded) == expected and not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-fetch even when a valid WebP exists")
    parser.add_argument("--limit", type=int, default=0, help="process only the first N rows")
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    rows = load_csv()
    if args.limit:
        rows = rows[: args.limit]
    if args.validate_only:
        previous = load_previous()
        assets = []
        for row in rows:
            dest = ROOT / local_relpath(row)
            ok, width, height = existing_output_ok(dest)
            prior = previous.get(row["asset_id"], {})
            assets.append(
                record_for(
                    row,
                    rows,
                    local_relpath(row),
                    prior.get("downloaded_sha256", ""),
                    sha256_file(dest) if dest.exists() else "",
                    width,
                    height,
                    "ok" if ok else "failed",
                    "" if ok else "missing or undecodable local output",
                )
            )
        write_manifest(rows, assets, [a for a in assets if a["status"] == "failed"])
        return print_report(rows, assets)

    previous = load_previous()
    assets: list[dict] = []
    lock = threading.Lock()
    print(f"importing {len(rows)} assets with {args.workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(process_row, row, rows, previous, args.force): row["asset_id"]
            for row in rows
        }
        done = 0
        for future in as_completed(futures):
            result = future.result()
            with lock:
                assets.append(result)
                done += 1
                write_manifest(rows, assets, [a for a in assets if a["status"] == "failed"])
            mark = result["status"]
            print(
                f"[{done}/{len(rows)}] {result['asset_id']} {mark} "
                f"{result['width']}x{result['height']}",
                flush=True,
            )
    return print_report(rows, assets)


if __name__ == "__main__":
    sys.exit(main())
