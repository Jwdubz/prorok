#!/usr/bin/env python3
"""Switch canonical, OG, JSON-LD, sitemap, and robots origins.

Default / rehearsal mode is staging-safe:
  origin https://prorok.jarrettwroten.com
  noindex, nofollow
  robots.txt Disallow: /

Production cutover requires an explicit origin AND --indexable.
--dry-run prints the would-be state without writing files and never
edits DNS or CNAME.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prorok_assets import PRODUCT_URLS, restore_product_urls, shield_product_urls  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PREVIEW_ORIGIN = "https://prorok.jarrettwroten.com"
PRODUCTION_ORIGIN = "https://www.dylanprorok.com"
ALTERNATE_REHEARSAL_ORIGIN = "https://dylanproroktattoos.com"
KNOWN_ORIGINS = (PREVIEW_ORIGIN, PRODUCTION_ORIGIN, "https://dylanprorok.com", ALTERNATE_REHEARSAL_ORIGIN)
HTML_PAGES = [
    "index.html",
    "portfolio.html",
    "about.html",
    "booking.html",
    "flash.html",
    "art.html",
    "merch.html",
]
TEXT_FILES = HTML_PAGES + [
    "robots.txt",
    "sitemap.xml",
    "sitemap-pages.xml",
    "sitemap-images.xml",
    "assets/config.js",
    "assets/launch.json",
]
NOINDEX = "noindex, nofollow, noarchive, nosnippet, noimageindex"
INDEXABLE = "index, follow"
ROBOTS_META_RE = re.compile(
    r'(<meta name="robots" content=")([^"]*)(" />)'
)


def current_origin() -> str:
    launch_path = ROOT / "assets/launch.json"
    if launch_path.exists():
        data = json.loads(launch_path.read_text(encoding="utf-8"))
        if data.get("origin"):
            return data["origin"].rstrip("/")
    config = (ROOT / "assets/config.js").read_text(encoding="utf-8")
    match = re.search(r'origin:\s*"(https://[^"]+)"', config)
    if match:
        return match.group(1).rstrip("/")
    return PREVIEW_ORIGIN


def rewrite_text(text: str, old_origin: str, new_origin: str, indexable: bool) -> str:
    text, product_tokens = shield_product_urls(text)
    for origin in {old_origin, *KNOWN_ORIGINS}:
        if origin and origin != new_origin:
            text = text.replace(origin, new_origin)
    if ROBOTS_META_RE.search(text):
        text = ROBOTS_META_RE.sub(
            rf"\1{INDEXABLE if indexable else NOINDEX}\3",
            text,
        )
    elif "<meta name=\"viewport\"" in text:
        text = text.replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
            f'<meta name="robots" content="{INDEXABLE if indexable else NOINDEX}" />\n',
            1,
        )
    if text.startswith("User-agent:") or "Sitemap:" in text[:200]:
        sitemap = f"Sitemap: {new_origin}/sitemap.xml\n"
        if indexable:
            text = f"User-agent: *\nAllow: /\n\n{sitemap}"
        else:
            text = f"User-agent: *\nDisallow: /\n\n{sitemap}"
    if "window.PROROK" in text:
        text = re.sub(r'origin:\s*"(https://[^"]+)"', f'origin: "{new_origin}"', text, count=1)
    if text.lstrip().startswith("{") and '"preview_origin"' in text:
        data = json.loads(text)
        data["origin"] = new_origin
        data["indexable"] = indexable
        text = json.dumps(data, indent=2) + "\n"
    return restore_product_urls(text, product_tokens)


def product_urls_intact(files: dict[str, str]) -> list[str]:
    failures = []
    blob = "\n".join(files.values())
    for url in PRODUCT_URLS:
        if url not in blob:
            failures.append(f"product URL missing after rewrite: {url}")
        rewritten = url.replace("https://www.dylanprorok.com", "https://dylanproroktattoos.com")
        if rewritten in blob:
            failures.append(f"product URL was rewritten: {rewritten}")
    return failures


def rehearsal_product_url_check(origin: str = ALTERNATE_REHEARSAL_ORIGIN) -> list[str]:
    files = collect(origin, False)
    failures = product_urls_intact(files)
    if f'origin: "{origin}"' not in files["assets/config.js"]:
        failures.append("alternate-origin dry-run did not rewrite config origin")
    if f"{origin}/merch.html" not in files["merch.html"]:
        failures.append("alternate-origin dry-run did not rewrite merch metadata")
    if "https://www.dylanprorok.com/store/p/gwap-geisha-print" not in files["merch.html"]:
        failures.append("gwap-geisha product URL did not remain byte-exact")
    if "https://www.dylanprorok.com/store/p/ko-omote-t-shirt" not in files["merch.html"]:
        failures.append("ko-omote product URL did not remain byte-exact")
    return failures


def collect(origin: str, indexable: bool) -> dict[str, str]:
    old = current_origin()
    rewritten = {}
    for rel in TEXT_FILES:
        path = ROOT / rel
        rewritten[rel] = rewrite_text(path.read_text(encoding="utf-8"), old, origin, indexable)
    return rewritten


def validate_rewritten(files: dict[str, str], origin: str, indexable: bool) -> list[str]:
    failures = []
    for page in HTML_PAGES:
        text = files[page]
        expected = f"{origin}/" if page == "index.html" else f"{origin}/{page}"
        if f'href="{expected}"' not in text and f'"url":"{expected}"' not in text.replace(" ", ""):
            if f'href="{expected}"' not in text:
                failures.append(f"{page}: missing canonical {expected}")
        if indexable:
            if "noindex" in text.lower():
                failures.append(f"{page}: still noindex in indexable mode")
        else:
            if "noindex" not in text.lower() or "nofollow" not in text.lower():
                failures.append(f"{page}: missing noindex/nofollow in staging mode")
        if origin not in text:
            failures.append(f"{page}: origin {origin} not present")
        if page != "about.html" and "https://www.dylanprorok.com/" in text and origin != PRODUCTION_ORIGIN:
            # merch may still point at live product listings
            if page not in {"merch.html", "index.html"}:
                failures.append(f"{page}: leftover production origin")
    robots = files["robots.txt"]
    if indexable:
        if "Allow: /" not in robots or "Disallow: /" in robots:
            failures.append("robots.txt not crawlable in indexable mode")
    else:
        if "Disallow: /" not in robots:
            failures.append("robots.txt missing Disallow in staging mode")
    if f"Sitemap: {origin}/sitemap.xml" not in robots:
        failures.append("robots.txt sitemap origin mismatch")
    if f"{origin}/sitemap-pages.xml" not in files["sitemap.xml"]:
        failures.append("sitemap.xml origin mismatch")
    if f'origin: "{origin}"' not in files["assets/config.js"]:
        failures.append("config.js origin mismatch")
    cname = (ROOT / "CNAME").read_text(encoding="utf-8").strip()
    if cname != "prorok.jarrettwroten.com":
        failures.append(f"CNAME unexpectedly {cname!r}")
    failures.extend(product_urls_intact(files))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default=PREVIEW_ORIGIN, help="Absolute origin, no trailing slash")
    parser.add_argument("--indexable", action="store_true", help="Remove the index block. Required for a public launch.")
    parser.add_argument("--dry-run", action="store_true", help="Validate the would-be state without writing")
    args = parser.parse_args()
    origin = args.origin.rstrip("/")
    if not origin.startswith("https://"):
        print("origin must be an https URL", file=sys.stderr)
        return 2
    if args.indexable and origin == PREVIEW_ORIGIN:
        print("refusing to mark the GitHub preview indexable", file=sys.stderr)
        return 2
    if not args.indexable and origin == PRODUCTION_ORIGIN and not args.dry_run:
        print("production origin write requires --indexable, or use --dry-run", file=sys.stderr)
        return 2

    files = collect(origin, args.indexable)
    failures = validate_rewritten(files, origin, args.indexable)
    if args.dry_run:
        rehearsal_origin = origin if origin == ALTERNATE_REHEARSAL_ORIGIN else ALTERNATE_REHEARSAL_ORIGIN
        rehearsal_failures = rehearsal_product_url_check(rehearsal_origin)
        print(f"product_url_rehearsal_origin={rehearsal_origin}")
        if rehearsal_failures:
            print("PRODUCT URL REHEARSAL FAIL")
            for item in rehearsal_failures:
                print(f"- {item}")
            failures.extend(rehearsal_failures)
        else:
            print("PRODUCT URL REHEARSAL PASS — metadata rewrites; both product URLs remain byte-exact")
    cname = (ROOT / "CNAME").read_text(encoding="utf-8").strip()
    rehearsed_host = origin.replace("https://", "").replace("http://", "").split("/")[0]
    cname_matches = cname == rehearsed_host
    print(f"mode={'indexable' if args.indexable else 'staging-safe'}")
    print(f"origin={origin}")
    print(f"dry_run={args.dry_run}")
    print("CNAME/DNS: unchanged external steps; this script never mutates CNAME or DNS.")
    print(f"CNAME file={cname}")
    print(f"rehearsed_host={rehearsed_host}")
    if cname_matches:
        print("CNAME matches the rehearsed origin host.")
    else:
        print(
            f"CNAME mismatch: file is {cname!r}, rehearsed origin host is {rehearsed_host!r}."
        )
        print("The current CNAME does not yet match the rehearsed production host.")
        print("This is not a deploy-ready production PASS.")
    print("sample_urls:")
    print(f"  home={origin}/")
    print(f"  portfolio={origin}/portfolio.html")
    print(f"  robots={'Allow: /' if args.indexable else 'Disallow: /'}")
    if failures:
        print("FAIL")
        for item in failures:
            print(f"- {item}")
        return 1
    if args.dry_run:
        if cname_matches:
            print("DRY-RUN PASS — metadata transformation rehearsal; no files written")
        else:
            print("DRY-RUN PASS — metadata transformation rehearsal only; no files written")
            print(
                f"Remaining external action: point DNS/CNAME from {cname} to {rehearsed_host} "
                "before any production cutover. Do not treat this rehearsal as deploy-ready."
            )
        return 0
    for rel, text in files.items():
        (ROOT / rel).write_text(text, encoding="utf-8")
    print("WRITE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
