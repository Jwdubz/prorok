#!/usr/bin/env python3
"""Shared path, label, and grouping helpers for the recovered Prorok library."""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_DATA = ROOT / "data" / "legacy-assets"
FROZEN_MANIFEST = LEGACY_DATA / "asset-manifest.csv"
FROZEN_GROUPS = LEGACY_DATA / "duplicate-groups.csv"
VISUAL_LABELS = LEGACY_DATA / "visual-label-suggestions.csv"
SITE_ASSETS = ROOT / "data" / "site-assets.json"
LOCAL_MANIFEST = ROOT / "media" / "local-manifest.json"
PREVIEW_ORIGIN = "https://prorok.jarrettwroten.com"
PRODUCTION_ORIGIN = "https://www.dylanprorok.com"
SETMORE_CONSULT_URL = "https://dylanproroktattoo.setmore.com/"
GOOGLE_MAPS_CID = "https://www.google.com/maps?cid=12163001512038007552"
BUSINESS_NAME = "Dylan Prorok Tattoo"
PERSON_NAME = "Dylan Prorok"
PRODUCT_URLS = (
    "https://www.dylanprorok.com/store/p/gwap-geisha-print",
    "https://www.dylanprorok.com/store/p/ko-omote-t-shirt",
)
NOJS_BOOT = (
    '<script>document.documentElement.className='
    'document.documentElement.className.replace(/\\bno-js\\b/,"js");'
    'document.documentElement.dataset.motion=new URLSearchParams(location.search).get("motion")==="reduced"?"reduced":"full";</script>'
)

SUBDIR_BY_SUBCATEGORY = {
    "irezumi": Path("media/portfolio/irezumi"),
    "color": Path("media/portfolio/color"),
    "black-and-grey": Path("media/portfolio/black-and-grey"),
    "aggregate-only": Path("media/portfolio/other"),
    "flash-sheet": Path("media/flash"),
    "painting-or-illustration-or-mural": Path("media/art"),
    "print": Path("media/merch"),
    "shirt": Path("media/merch"),
}

PRIMARY_ROUTE = {
    "irezumi": "/irezumi",
    "color": "/color",
    "black-and-grey": "/bng",
    "aggregate-only": "/flash-1",
    "flash-sheet": "/flash",
    "painting-or-illustration-or-mural": "/art",
    "print": "/store/p/gwap-geisha-print",
    "shirt": "/store/p/ko-omote-t-shirt",
}

WEAK_EXACT = {
    "custom original japanese tattoo flash las vegas",
    "las vegas japanese fine artist professional muralist tattoo artist",
}

FILENAME_LIKE = re.compile(
    r"(?ix)^("
    r"IMG_\d+"
    r"|DSC_?\d+"
    r"|FullSizeRender"
    r"|[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}"
    r")\.(jpe?g|png|webp|heic|heif)$"
)

# Retained first-pass captions, with the Medusa placement correction.
HAND_AUTHORED = {
    "TAT-IRE-051": (
        "Black and grey Japanese dragon backpiece",
        "Dragon backpiece",
    ),
    "TAT-IRE-003": (
        "Japanese peony and cherry blossom sleeve with wind-bar background",
        "Peony sleeve",
    ),
    "TAT-IRE-080": (
        "Kitsune mask and cherry blossoms tattooed on a hand",
        "Kitsune hand",
    ),
    "TAT-IRE-034": (
        "Black and grey sleeve with red: snake, cat, and hannya mask",
        "Snake and cat sleeve",
    ),
    "TAT-IRE-060": (
        "Full-color Japanese dragon and koi sleeve",
        "Dragon and koi sleeve",
    ),
    "TAT-IRE-084": (
        "Black and grey geisha, peony, and koi sleeve",
        "Geisha sleeve",
    ),
    "TAT-IRE-065": (
        "Black and grey Japanese tiger thigh tattoo with waves",
        "Tiger thigh",
    ),
    "TAT-IRE-042": (
        "Black and grey sleeve with red: snake, peony, and chrysanthemum",
        "Snake and peony sleeve",
    ),
    "TAT-IRE-007": (
        "Japanese omamori and cherry blossom sleeve with wind-bar background",
        "Omamori sleeve",
    ),
    "TAT-COL-008": (
        "Color illustrative Medusa and snakes on an upper back and shoulder",
        "Medusa upper back",
    ),
    "TAT-BNG-001": (
        "Black and grey illustrative two-faced panther on a forearm",
        "Panther forearm",
    ),
}

SPELLING = (
    (re.compile(r"(?i)\boma\s+mori\b"), "omamori"),
    (re.compile(r"(?i)\bwine\s+bar\b"), "wind-bar"),
    (re.compile(r"(?i)\bwin\s+bar\b"), "wind-bar"),
    (re.compile(r"(?i)\bwind\s+bar\b"), "wind-bar"),
    (re.compile(r"(?i)\bfinger\s*waves?\b"), "finger waves"),
    (re.compile(r"(?i)\bdarma\b"), "Daruma"),
    (re.compile(r"(?i)\byokia\b"), "yokai"),
    (re.compile(r"(?i)\bblack,\s+and\s+gray\b"), "black and grey"),
    (re.compile(r"(?i)\bblack\s+and\s+gray\b"), "black and grey"),
)

VIEW_FALLBACK = {
    "irezumi": "Japanese tattoo by Dylan Prorok — portfolio view {n:02d}",
    "color": "Illustrative color tattoo by Dylan Prorok — portfolio view {n:02d}",
    "black-and-grey": "Black and grey tattoo by Dylan Prorok — portfolio view {n:02d}",
    "aggregate-only": "Tattoo by Dylan Prorok — additional work {n:02d}",
    "flash-sheet": "Flash archive view {n:02d}",
    "painting-or-illustration-or-mural": "Artwork archive view {n:02d}",
    "print": "Gwap Geisha Print — product view {n:02d}",
    "shirt": "Ko Omote T-Shirt — product view {n:02d}",
}


def local_relpath(row: dict) -> Path:
    sub = row["source_subcategory"]
    return SUBDIR_BY_SUBCATEGORY[sub] / f"{row['asset_id']}.webp"


def fetch_url(source_url: str) -> str:
    if "?" in source_url:
        return f"{source_url}&format=1500w"
    return f"{source_url}?format=1500w"


def parse_page_index(row: dict) -> tuple[int, int]:
    primary = PRIMARY_ROUTE.get(row["source_subcategory"], "")
    best = 10_000
    found = False
    for part in (row.get("page_order") or "").split("|"):
        if ":" not in part:
            continue
        route, _, idx = part.partition(":")
        try:
            number = int(idx)
        except ValueError:
            continue
        if route == primary:
            return (0, number)
        if not found or number < best:
            best = number
            found = True
    return (1, best if found else 10_000)


def view_number(rows: list[dict], asset_id: str) -> int:
    row = next(r for r in rows if r["asset_id"] == asset_id)
    siblings = [
        r
        for r in rows
        if r["source_category"] == row["source_category"]
        and r["source_subcategory"] == row["source_subcategory"]
    ]
    siblings.sort(key=lambda r: (parse_page_index(r), r["asset_id"]))
    return siblings.index(row) + 1


def is_weak_label(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return True
    if FILENAME_LIKE.match(value):
        return True
    lowered = value.lower()
    if lowered in WEAK_EXACT:
        return True
    if lowered.startswith("hand made japanese style art made in the us"):
        return True
    if lowered.startswith("hand made t-shirt, original artwork"):
        return True
    return False


def normalize_spelling(text: str) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    for pattern, repl in SPELLING:
        value = pattern.sub(repl, value)
    value = re.sub(r"(?i)\bLas Vegas\b,?\s*", "", value)
    value = re.sub(r"(?i)\bVegas\b,?\s*", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" ,.-")


def short_caption(alt: str) -> str:
    cleaned = alt.strip()
    if len(cleaned) <= 64:
        return cleaned[0].upper() + cleaned[1:] if cleaned else cleaned
    cut = cleaned[:64]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;.") + "…"


@lru_cache(maxsize=1)
def load_visual_labels() -> dict[str, tuple[str, str]]:
    if not VISUAL_LABELS.exists():
        return {}
    labels: dict[str, tuple[str, str]] = {}
    with VISUAL_LABELS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            asset_id = (row.get("asset_id") or "").strip()
            alt = (row.get("proposed_alt") or "").strip()
            caption = (row.get("proposed_caption") or "").strip()
            if asset_id and alt and caption:
                labels[asset_id] = (alt, caption)
    return labels


def labels_for(row: dict, rows: list[dict]) -> tuple[str, str]:
    visual = load_visual_labels().get(row["asset_id"])
    if visual:
        return visual
    authored = HAND_AUTHORED.get(row["asset_id"])
    if authored:
        return authored
    legacy = row.get("legacy_alt_or_description") or ""
    n = view_number(rows, row["asset_id"])
    fallback = VIEW_FALLBACK[row["source_subcategory"]].format(n=n)
    if is_weak_label(legacy):
        return fallback, fallback
    alt = normalize_spelling(legacy)
    if not alt or is_weak_label(alt):
        return fallback, fallback
    if alt[0].islower():
        alt = alt[0].upper() + alt[1:]
    return alt, short_caption(alt)


def group_note(group_id: str, relationship: str, member_ids: list[str]) -> str:
    if group_id.startswith("FLA-SHEET-"):
        return "Same flash sheet, two archive photographs."
    if group_id.startswith("ART-CTX-"):
        return "Possible contextual or alternate view of the same work."
    if group_id == "CROSS-F19-A07-A30":
        return "Same artwork photographed across the flash and art archives."
    if relationship == "alternate-view":
        return "Alternate views of the same work."
    if relationship == "contextual-view":
        return "Contextual views of the same work."
    if relationship == "likely-same-work":
        return "Likely the same work, shown together."
    if relationship == "same-work-cross-category":
        return "The same work across archive rooms."
    return "Related archive views."


def shield_product_urls(text: str) -> tuple[str, dict[str, str]]:
    tokens: dict[str, str] = {}
    for index, url in enumerate(PRODUCT_URLS):
        token = f"__PROROK_PRODUCT_URL_{index}__"
        tokens[token] = url
        text = text.replace(url, token)
    return text, tokens


def restore_product_urls(text: str, tokens: dict[str, str]) -> str:
    for token, url in tokens.items():
        text = text.replace(token, url)
    return text


def person_same_as(existing: list[str] | None = None) -> list[str]:
    values = list(existing or [
        "https://www.instagram.com/dylanprorok/",
        "https://www.tiktok.com/@dylanprorok_dylontattoo",
    ])
    if GOOGLE_MAPS_CID not in values:
        values.append(GOOGLE_MAPS_CID)
    return values


def business_same_as(existing: list[str] | None = None) -> list[str]:
    values = list(existing or [
        "https://www.instagram.com/dylanprorok/",
        "https://www.instagram.com/heritagetattoolv/",
        "https://www.tiktok.com/@dylanprorok_dylontattoo",
    ])
    if GOOGLE_MAPS_CID not in values:
        values.append(GOOGLE_MAPS_CID)
    return values
