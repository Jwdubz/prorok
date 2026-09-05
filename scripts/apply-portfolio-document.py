#!/usr/bin/env python3
"""Apply the ordered Portfolio photographs supplied in a Google Doc.

The seed step records the source document's inline-object order and the
downloaded image integrity data. The apply step changes only the dedicated
Portfolio page, its active manifest, and the Portfolio entry in the image
sitemap; the other pages and their editorial images are left alone.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "portfolio-document.json"
IMAGE_DIR = ROOT / "media" / "portfolio" / "document-20260904"
PORTFOLIO = ROOT / "portfolio.html"
MANIFEST = ROOT / "assets" / "portfolio-manifest.json"
SITEMAP_IMAGES = ROOT / "sitemap-images.xml"
ORIGIN = "https://prorok.jarrettwroten.com"

CAPTIONS = [
    "Peony and cherry blossom sleeve.",
    "Floral charm and bell sleeve detail.",
    "Peony sleeve, full view.",
    "Floral charm and bell, angled view.",
    "Crane and peony sleeve.",
    "Crane sleeve, inner view.",
    "Dragon backpiece.",
    "Red snake and cat sleeve.",
    "Snake and peony sleeve.",
    "Peony and fox mask sleeve.",
    "Peony and fox mask, extended view.",
    "Frog procession.",
    "Dragon and Daruma sleeve.",
    "Dragon and Daruma, inner view.",
    "Geisha head with red flowers.",
    "Snake and peony thigh tattoo.",
    "Snake and peony, alternate view.",
    "Black and grey dragon sleeve.",
    "Skull-headed octopus.",
    "Black and grey tiger.",
    "Color snake and peony.",
    "Hannya mask.",
    "Geisha portrait.",
    "Geisha and hannya pair.",
    "Snake and peony neck tattoo.",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed(source_input: Path) -> None:
    source_rows = json.loads(source_input.read_text(encoding="utf-8"))
    if len(source_rows) != len(CAPTIONS):
        raise SystemExit(f"expected {len(CAPTIONS)} source images, found {len(source_rows)}")
    items = []
    for index, source_row in enumerate(source_rows, start=1):
        path = IMAGE_DIR / f"portfolio-{index:02d}.jpg"
        if not path.exists():
            raise SystemExit(f"missing downloaded source image: {path}")
        with Image.open(path) as image:
            image.load()
            image_format = image.format or ""
            width, height = image.size
        if image_format != "JPEG":
            raise SystemExit(f"{path}: expected JPEG, found {image_format}")
        caption = CAPTIONS[index - 1]
        items.append(
            {
                "order": index,
                "asset_id": f"TAT-DOC-{index:03d}",
                "source_object_id": source_row["object_id"],
                "src": path.relative_to(ROOT).as_posix(),
                "width": width,
                "height": height,
                "sha256": sha256_file(path),
                "alt": caption,
                "caption": caption,
            }
        )
    payload = {
        "version": 1,
        "source": {
            "title": "Portfolio",
            "document_id": "1f2FyO-MOKiaOUQfH712Sue2D61K-kBUoRVjR0fwocnc",
            "document_url": "https://docs.google.com/document/d/1f2FyO-MOKiaOUQfH712Sue2D61K-kBUoRVjR0fwocnc",
            "tab_id": "t.0",
            "order_basis": "Google Docs inline-object order",
        },
        "items": items,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_data() -> dict:
    if not DATA.exists():
        raise SystemExit(f"missing {DATA}; run --seed first")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    if [item.get("order") for item in items] != list(range(1, len(items) + 1)):
        raise SystemExit("portfolio-document.json order is not contiguous")
    if len(items) != len(CAPTIONS):
        raise SystemExit(f"portfolio-document.json expected {len(CAPTIONS)} items, found {len(items)}")
    return payload


def figure(item: dict, eager: bool = False) -> str:
    loading = "eager" if eager else "lazy"
    priority = ' fetchpriority="high"' if eager else ""
    return (
        f'      <figure data-asset-id="{html.escape(item["asset_id"], quote=True)}">\n'
        f'        <img src="{html.escape(item["src"], quote=True)}" '
        f'alt="{html.escape(item["alt"], quote=True)}" width="{item["width"]}" '
        f'height="{item["height"]}" decoding="async" loading="{loading}"{priority} />\n'
        f'        <figcaption>{html.escape(item["caption"])}</figcaption>\n'
        "      </figure>"
    )


def portfolio_body(items: list[dict]) -> str:
    figures = "\n".join(figure(item, eager=index == 0) for index, item in enumerate(items))
    return f'''  <div class="sec__head">
    <span class="sec__jp" aria-hidden="true">作品集</span>
    <h1 data-split>Portfolio</h1>
    <p>Sleeves, backs, thighs, and hands. Drawn to the body they live on.</p>
  </div>

  <section class="folio-cat" id="document-order" data-category="document">
    <div class="folio-cat__head">
      <h2>Irezumi</h2>
      <span aria-hidden="true">入れ墨</span>
    </div>
    <div class="folio folio-flow">
{figures}
    </div>
  </section>

  <p class="page__go"><a href="https://dylanproroktattoo.setmore.com/" target="_blank" rel="noopener">Book a virtual consultation</a></p>
'''


def apply_portfolio_page(items: list[dict]) -> None:
    text = PORTFOLIO.read_text(encoding="utf-8")
    text = text.replace(
        "media/portfolio/irezumi/TAT-IRE-051.webp",
        items[0]["src"],
    )
    text = text.replace('<meta property="og:image:width" content="1200" />', f'<meta property="og:image:width" content="{items[0]["width"]}" />')
    text = text.replace('<meta property="og:image:height" content="1600" />', f'<meta property="og:image:height" content="{items[0]["height"]}" />')
    start = text.find('<main class="page folio-page" id="main">')
    end = text.find("</main>", start)
    if start < 0 or end < 0:
        raise SystemExit("portfolio.html main boundary not found")
    opening_end = text.find(">", start) + 1
    text = text[:opening_end] + "\n" + portfolio_body(items) + text[end:]
    PORTFOLIO.write_text(text, encoding="utf-8")


def apply_manifest(items: list[dict]) -> None:
    manifest = {
        "version": 3,
        "source": {
            "title": "Portfolio",
            "document_id": "1f2FyO-MOKiaOUQfH712Sue2D61K-kBUoRVjR0fwocnc",
            "document_url": "https://docs.google.com/document/d/1f2FyO-MOKiaOUQfH712Sue2D61K-kBUoRVjR0fwocnc",
            "order_basis": "Google Docs inline-object order",
        },
        "categories": [
            {
                "id": "document-order",
                "label": "Portfolio",
                "jp": "作品集",
                "items": items,
            }
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def apply_sitemap(items: list[dict], origin: str = ORIGIN) -> None:
    text = SITEMAP_IMAGES.read_text(encoding="utf-8")
    block = [
        "  <url>",
        f"    <loc>{origin}/portfolio.html</loc>",
    ]
    for item in items:
        block.extend(
            [
                "    <image:image>",
                f"      <image:loc>{origin}/{xml_escape(item['src'])}</image:loc>",
                f"      <image:title>{xml_escape(item['caption'])}</image:title>",
                "    </image:image>",
            ]
        )
    block.append("  </url>")
    replacement = "\n".join(block)
    pattern = r"  <url>\s*<loc>" + re.escape(origin + "/portfolio.html") + r"</loc>[\s\S]*?</url>"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise SystemExit("portfolio sitemap block not found exactly once")
    SITEMAP_IMAGES.write_text(updated, encoding="utf-8")


def apply(origin: str = ORIGIN) -> None:
    payload = load_data()
    items = payload["items"]
    apply_portfolio_page(items)
    apply_manifest(items)
    apply_sitemap(items, origin)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="record downloaded files and source order")
    parser.add_argument("--source-input", type=Path, help="JSON list from the Google Docs extraction step")
    parser.add_argument("--apply", action="store_true", help="apply the canonical ordered set to site artifacts")
    args = parser.parse_args()
    if not args.seed and not args.apply:
        parser.error("choose --seed or --apply")
    if args.seed:
        if not args.source_input:
            parser.error("--seed requires --source-input")
        seed(args.source_input)
    if args.apply:
        apply()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
