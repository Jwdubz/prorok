#!/usr/bin/env python3
"""Static checks for the Dylan Prorok production-candidate correction."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET
import importlib.util

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prorok_assets import (  # noqa: E402
    BUSINESS_NAME,
    FROZEN_GROUPS,
    FROZEN_MANIFEST,
    GOOGLE_MAPS_CID,
    PRODUCT_URLS,
    SITE_ASSETS,
    VISUAL_LABELS,
    load_visual_labels,
)
PAGES = [
    "index.html",
    "portfolio.html",
    "about.html",
    "booking.html",
    "flash.html",
    "art.html",
    "merch.html",
]
ACUITY = "https://dylanprorok.as.me/schedule/b21deb93/appointment/61957220/calendar/10046225"
INTERNAL = (
    "worktree",
    "being recovered",
    "will land here",
    "being brought into this room",
    "until they are here",
    "as it is recovered",
)
REQUIRED_COPY = [
    ("index.html", "Designed to be seen."),
    ("index.html", "Crafted to BE remembered."),
    ("index.html", "A tattoo should be legible"),
    ("index.html", "from across the room"),
    ("index.html", "Powerful enough to be read from a distance"),
    ("index.html", "alluring to draw you closer"),
    ("index.html", "Bigger is better."),
    ("index.html", "Traditional composition crafted to individual body flow"),
    ("index.html", "Each piece begins with a picture and tracing"),
    ("index.html", "as if you were born with the tattoo"),
    ("index.html", "Scale and precision"),
    ("index.html", "The consultation is free"),
    ("index.html", "one session each month"),
    ("index.html", "free touch-ups"),
    ("index.html", "One-shot tattoos and small bangers always welcome"),
    ("about.html", "My name is Dylan Prorok"),
    ("about.html", "I’ve been tattooing in Las Vegas for nine years"),
    ("booking.html", "How to get started"),
    ("booking.html", "Tattoo description"),
    ("booking.html", "Japanese style Kitsune fox"),
    ("booking.html", "Right inner forearm about 5x7 inches"),
    ("booking.html", "Please do not send AI-rendered"),
    ("booking.html", "Las Vegas local"),
    ("booking.html", "Traveling to Las Vegas"),
    ("booking.html", "Out-of-town convention or guest spot"),
    ("flash.html", "confirmed before booking"),
    ("merch.html", "Gwap Geisha Print"),
    ("merch.html", "Ko Omote T-Shirt"),
    ("merch.html", "View current listing"),
]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.in_h1 = False
        self.in_script = False
        self.in_style = False
        self.h1_count = 0
        self.canonical = ""
        self.robots_meta: list[str] = []
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.labels_for: set[str] = set()
        self.control_ids: dict[str, str] = {}
        self._label_depth = 0
        self.has_concept_banner = False
        self.has_skip = False
        self.visible = ""
        self.form_count = 0
        self.inquiry_forms = 0
        self.figures = 0
        self.portfolio_figures = 0
        self.flash_figures = 0
        self.art_figures = 0
        self.merch_images = 0
        self.nav_cta = ""
        self.nav_hrefs: list[str] = []
        self.ids: list[str] = []
        self._section_id = ""
        self._in_folio = False
        self._in_flash = False
        self._in_art = False
        self._in_merch_gallery = False
        self._in_nav = False
        self._class_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: v or "" for k, v in attrs}
        classes = ad.get("class", "")
        self._class_stack.append(classes)
        if ad.get("id"):
            self.ids.append(ad["id"])
        if tag == "title":
            self.in_title = True
        if tag == "script":
            self.in_script = True
        if tag == "style":
            self.in_style = True
        if tag == "h1":
            self.in_h1 = True
            self.h1_count += 1
        if tag == "form":
            self.form_count += 1
            if ad.get("data-prorok-form") == "inquiry":
                self.inquiry_forms += 1
        if tag == "nav" and "nav" in classes.split():
            self._in_nav = True
        if tag == "a":
            href = ad.get("href", "")
            if href:
                self.hrefs.append(href)
                if self._in_nav:
                    self.nav_hrefs.append(href)
            if "skip-link" in classes.split():
                self.has_skip = True
            if self._in_nav and "nav__header-cta" in classes.split():
                self.nav_cta = href
        if tag in {"img", "script", "source", "video"}:
            if ad.get("src"):
                self.srcs.append(ad["src"])
        if tag == "link" and ad.get("rel") == "canonical":
            self.canonical = ad.get("href", "")
        if tag == "link" and ad.get("href") and "stylesheet" in ad.get("rel", ""):
            self.srcs.append(ad["href"])
        if tag == "meta" and ad.get("name") in {"robots", "googlebot"}:
            self.robots_meta.append(ad.get("content", ""))
        if tag == "label" and ad.get("for"):
            self.labels_for.add(ad["for"])
        if tag == "label":
            self._label_depth += 1
        if tag in {"input", "textarea", "select"} and ad.get("id"):
            self.control_ids[ad["id"]] = tag
        if tag == "div" and ad.get("id") == "concept":
            self.has_concept_banner = True
        if tag == "figure":
            self.figures += 1
            if self._in_folio:
                self.portfolio_figures += 1
            if self._in_flash:
                self.flash_figures += 1
            if self._in_art:
                self.art_figures += 1
            if self._in_merch_gallery:
                self.merch_images += 1
        if tag == "section":
            self._section_id = ad.get("id", "")
            if self._section_id in {"irezumi", "color", "bng", "additional"}:
                self._in_folio = True
            if self._section_id == "flash-library":
                self._in_flash = True
            if self._section_id == "art-library":
                self._in_art = True
        if tag == "div" and "product__gallery" in classes.split():
            self._in_merch_gallery = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "script":
            self.in_script = False
        if tag == "style":
            self.in_style = False
        if tag == "h1":
            self.in_h1 = False
        if tag == "label" and self._label_depth:
            self._label_depth -= 1
        if tag == "nav":
            self._in_nav = False
        if tag == "section":
            self._in_folio = False
            self._in_flash = False
            self._in_art = False
            self._section_id = ""
        if tag == "div" and self._class_stack and "product__gallery" in self._class_stack[-1].split():
            self._in_merch_gallery = False
        if self._class_stack:
            self._class_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_script or self.in_style:
            return
        self.visible += data


def local_path(url: str) -> Path | None:
    if url.startswith(("mailto:", "tel:")):
        return None
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        return None
    if url.startswith("#"):
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    return ROOT / path.lstrip("./")


def expected_origin() -> tuple[str, bool]:
    launch = ROOT / "assets/launch.json"
    if launch.exists():
        data = json.loads(launch.read_text(encoding="utf-8"))
        return data["origin"].rstrip("/"), bool(data.get("indexable"))
    config = (ROOT / "assets/config.js").read_text(encoding="utf-8")
    match = re.search(r'origin:\s*"(https://[^"]+)"', config)
    return (match.group(1).rstrip("/") if match else "https://prorok.jarrettwroten.com"), False


PRIVACY_FIELDS = (
    "name",
    "email",
    "phone",
    "description",
    "placement",
    "newsletter",
    "location",
    "photos",
)
MACHINE_MARKERS = (
    "/Users/jman6",
    "/mnt/c/Users/jman6",
    "/mnt/d/Users/jman6",
    "C:\\Users\\jman6",
    "C:/Users/jman6",
)
SITE_MEDIA = (
    "media/site/dylan-prorok-tattooing-large-scale-piece.webp",
    "media/site/japanese-sleeve-composition.webp",
    "media/site/dylan-prorok-artist-portrait.webp",
)
GENERIC_TATTOO_LABELS = (
    "portfolio view",
    "additional japanese work",
    "additional japanese",
    "las vegas japanese tattoo artist",
)
FILENAME_LABEL = re.compile(
    r"(?ix)^(IMG_\d+|DSC_?\d+|FullSizeRender|[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})"
    r"(\.(jpe?g|png|webp|heic|heif))?$"
)
ALLOWED_TYPES = (
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
)
ALLOWED_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_ld_blocks(raw: str) -> list[str]:
    blocks = []
    start_tag = '<script type="application/ld+json">'
    end_tag = "</script>"
    pos = 0
    while True:
        start = raw.find(start_tag, pos)
        if start < 0:
            break
        start += len(start_tag)
        end = raw.find(end_tag, start)
        if end < 0:
            break
        blocks.append(raw[start:end].strip())
        pos = end + len(end_tag)
    return blocks


def extract_forms(raw: str) -> list[str]:
    return re.findall(r"<form\b[^>]*data-prorok-form[^>]*>[\s\S]*?</form>", raw)


def decode_webp(path: Path) -> tuple[str, tuple[int, int]]:
    with Image.open(path) as image:
        image.load()
        return image.format or "", image.size


def check_correction_wave(failures: list[str]) -> None:
    public_files = (
        list(ROOT.glob("*.html"))
        + list((ROOT / "assets").glob("*.css"))
        + list((ROOT / "assets").glob("*.js"))
    )
    for path in public_files:
        raw = path.read_text(encoding="utf-8")
        if "images.squarespace-cdn.com" in raw:
            failures.append(f"{path.relative_to(ROOT).as_posix()}: public Squarespace CDN reference")

    shipped_scripts = (
        "prorok_assets.py",
        "import-legacy-assets.py",
        "apply-recovered-site.py",
        "configure-launch.py",
    )
    for name in shipped_scripts:
        path = ROOT / "scripts" / name
        raw = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for marker in MACHINE_MARKERS:
            if marker in raw:
                failures.append(f"{rel}: hard-coded machine path {marker}")
        if "/prorok-asset-audit/" in raw or "\\prorok-asset-audit\\" in raw:
            failures.append(f"{rel}: still points at the external asset-audit tree")

    try:
        FROZEN_MANIFEST.resolve().relative_to(ROOT.resolve())
        FROZEN_GROUPS.resolve().relative_to(ROOT.resolve())
        SITE_ASSETS.resolve().relative_to(ROOT.resolve())
        VISUAL_LABELS.resolve().relative_to(ROOT.resolve())
    except ValueError:
        failures.append("bundled asset paths are not inside the repository")
        return

    if not FROZEN_MANIFEST.exists() or not FROZEN_GROUPS.exists():
        failures.append("bundled legacy manifests missing under data/legacy-assets/")
        return
    if not VISUAL_LABELS.exists():
        failures.append("bundled visual-label-suggestions.csv missing under data/legacy-assets/")
        return
    manifest_rows = list(csv.DictReader(FROZEN_MANIFEST.open(newline="", encoding="utf-8")))
    group_rows = list(csv.DictReader(FROZEN_GROUPS.open(newline="", encoding="utf-8")))
    if len(manifest_rows) != 190:
        failures.append(f"bundled asset-manifest.csv expected 190 rows, found {len(manifest_rows)}")
    if len(group_rows) != 23:
        failures.append(f"bundled duplicate-groups.csv expected 23 groups, found {len(group_rows)}")
    if any(row["duplicate_group"] == "IRE-LARGE-COLOR-SLEEVE-59-60" for row in group_rows):
        failures.append("false IRE-LARGE-COLOR-SLEEVE-59-60 group is still present")
    for asset_id in ("TAT-IRE-059", "TAT-IRE-060"):
        row = next((item for item in manifest_rows if item["asset_id"] == asset_id), None)
        if not row:
            failures.append(f"missing {asset_id} in bundled manifest")
        elif row.get("duplicate_group"):
            failures.append(f"{asset_id} still grouped as {row['duplicate_group']}")
        elif row.get("duplicate_relationship") != "unique/no-known-duplicate":
            failures.append(f"{asset_id} relationship is {row.get('duplicate_relationship')!r}")

    if not SITE_ASSETS.exists():
        failures.append("missing data/site-assets.json")
    else:
        provenance = json.loads(SITE_ASSETS.read_text(encoding="utf-8"))
        site_rows = provenance.get("assets") or []
        required = {
            "source_url",
            "fetch_url",
            "local_path",
            "source_sha256",
            "output_sha256",
            "width",
            "height",
            "rights_status",
        }
        found_paths: set[str] = set()
        if len(site_rows) != 3:
            failures.append(f"site-assets.json expected 3 assets, found {len(site_rows)}")
        for row in site_rows:
            missing = required - set(row)
            if missing:
                failures.append(f"site-assets.json missing fields {sorted(missing)}")
                continue
            if row["rights_status"] != "confirmation-required":
                failures.append(f"{row.get('local_path')}: rights_status={row['rights_status']!r}")
            rel = row["local_path"]
            found_paths.add(rel)
            path = ROOT / rel
            if not path.exists():
                failures.append(f"site media missing: {rel}")
                continue
            if sha256_file(path) != row["output_sha256"]:
                failures.append(f"{rel}: output sha256 mismatch")
            fmt, size = decode_webp(path)
            if fmt != "WEBP":
                failures.append(f"{rel}: expected WEBP, found {fmt}")
            if size != (row["width"], row["height"]):
                failures.append(f"{rel}: dimensions {size} != {(row['width'], row['height'])}")
            if max(size) > 1600:
                failures.append(f"{rel}: long edge {max(size)} exceeds 1600")
        if found_paths and found_paths != set(SITE_MEDIA):
            failures.append(f"site media paths drifted: {sorted(found_paths)}")

    index_raw = (ROOT / "index.html").read_text(encoding="utf-8")
    about_raw = (ROOT / "about.html").read_text(encoding="utf-8")
    if SITE_MEDIA[0] not in index_raw:
        failures.append("index.html scale image is not the local site WebP")
    if SITE_MEDIA[1] not in index_raw:
        failures.append("index.html first Work panel is not the local site WebP")
    if SITE_MEDIA[2] not in about_raw:
        failures.append("about.html portrait is not the local site WebP")

    local = json.loads((ROOT / "media/local-manifest.json").read_text(encoding="utf-8"))
    source_manifest = str(local.get("source_manifest") or "").replace("\\", "/")
    if any(marker in source_manifest for marker in MACHINE_MARKERS) or "prorok-asset-audit" in source_manifest:
        failures.append("local-manifest.json still names an external machine path")
    if "data/legacy-assets/asset-manifest.csv" not in source_manifest:
        failures.append("local-manifest.json source_manifest is not the bundled CSV")
    library = [row for row in local.get("assets", []) if row.get("status") in {"ok", "reused"}]
    if len(library) != 190:
        failures.append(f"local-manifest.json expected 190 usable assets, found {len(library)}")
    by_cat = {"tattoo": 0, "flash": 0, "art": 0, "merch": 0}
    for row in library:
        cat = row.get("source_category") or ""
        by_cat[cat] = by_cat.get(cat, 0) + 1
        rel = row.get("local_path") or ""
        path = ROOT / rel
        if not rel or not path.exists():
            failures.append(f"library asset missing: {rel or row.get('asset_id')}")
            continue
        if row.get("output_sha256") and sha256_file(path) != row["output_sha256"]:
            failures.append(f"{rel}: library sha256 mismatch")
            break
        fmt, size = decode_webp(path)
        if fmt != "WEBP":
            failures.append(f"{rel}: library format {fmt}")
            break
        if size != (row.get("width"), row.get("height")):
            failures.append(f"{rel}: library dimensions {size} != {(row.get('width'), row.get('height'))}")
            break
    if by_cat.get("tattoo") != 132 or by_cat.get("flash") != 20 or by_cat.get("art") != 32 or by_cat.get("merch") != 6:
        failures.append(f"library category counts drifted: {by_cat}")
    disk = {
        "tattoo": len(list((ROOT / "media/portfolio").rglob("*.webp"))),
        "flash": len(list((ROOT / "media/flash").rglob("*.webp"))),
        "art": len(list((ROOT / "media/art").rglob("*.webp"))),
        "merch": len(list((ROOT / "media/merch").rglob("*.webp"))),
    }
    if disk != {"tattoo": 132, "flash": 20, "art": 32, "merch": 6}:
        failures.append(f"rendered library WebP counts drifted: {disk}")

    config = (ROOT / "assets/config.js").read_text(encoding="utf-8")
    if 'formEndpoint: ""' not in config and "formEndpoint:''" not in config:
        failures.append("config.js formEndpoint must remain empty")
    if 'newsletterEndpoint: ""' not in config and "newsletterEndpoint:''" not in config:
        failures.append("config.js newsletterEndpoint must remain empty")
    for token in ALLOWED_TYPES:
        if token not in config:
            failures.append(f"config.js missing accepted type {token}")

    site_js = (ROOT / "assets/site.js").read_text(encoding="utf-8")
    home_js = (ROOT / "assets/home.js").read_text(encoding="utf-8")
    wheel_js = (ROOT / "assets/wheel-beat.js").read_text(encoding="utf-8")
    if "/^image\\//" in site_js:
        failures.append("site.js still allows arbitrary image/*")
    if "isAcceptedImageFile" not in site_js:
        failures.append("site.js missing exact image allowlist helper")
    for token in ALLOWED_TYPES + ALLOWED_EXTS:
        if token not in site_js:
            failures.append(f"site.js missing allowlist token {token}")
    if "maxImageBytes" not in site_js:
        failures.append("site.js missing 10 MB file-size check")
    if site_js.count("function collectFiles") != 1:
        failures.append("site.js collectFiles should exist once")
    collect_fn = re.search(r"function collectFiles\([^)]*\)\s*\{([^}]*)\}", site_js)
    if collect_fn and collect_fn.group(1).count("return") != 1:
        failures.append("site.js collectFiles has a duplicate or unreachable return")
    if re.search(r"if\s*\(\s*!window\.gsap\s*\|\|\s*!window\.ScrollTrigger\s*\)\s*return", home_js):
        failures.append("home.js still returns before hiding the loader")
    if not re.search(r"hideLoader\(\);\s*return", home_js):
        failures.append("home.js must hide the loader before the CDN-failure return")
    if "loader.style.display" not in home_js:
        failures.append("home.js must hide the loader synchronously")
    if re.search(r"if\s*\(\s*window\.Lenis\s*\)\s*\{\s*lenis\s*=\s*new Lenis", site_js):
        failures.append("site.js constructs Lenis without a RAF driver gate")
    if "new Lenis" in site_js and "hasGsapDriver" not in site_js and "hasRafDriver" not in site_js:
        failures.append("site.js missing explicit Lenis RAF driver guards")
    if "new Lenis" in site_js and "requestAnimationFrame" not in site_js:
        failures.append("site.js must provide a requestAnimationFrame driver when GSAP is absent")
    for token in (
        'addEventListener("touchstart"',
        'addEventListener("touchmove"',
        'addEventListener("touchend"',
        "state.canCaptureTouch",
        "GESTURE_QUIET_MS",
        "SCROLL_TAU_SECONDS = .41",
        'root.dataset.wheelBeatLayout = isDesktopViewport() ? "desktop" : "mobile"',
    ):
        if token not in wheel_js:
            failures.append(f"wheel-beat.js missing mobile beat token {token}")
    if '{ capture: true, passive: false }' not in wheel_js:
        failures.append("wheel-beat.js touch/wheel capture must include a non-passive path")
    if 'type.includes("touch")' not in site_js:
        failures.append("site.js must arbitrate captured touch input away from Lenis")

    merch_raw = (ROOT / "merch.html").read_text(encoding="utf-8")
    if 'data-prorok-form="newsletter"' in merch_raw:
        failures.append("merch.html: extra newsletter form must stay removed")
    for page in ("booking.html",):
        raw = (ROOT / page).read_text(encoding="utf-8")
        forms = extract_forms(raw)
        if not any('data-prorok-form="inquiry"' in form for form in forms):
            failures.append(f"{page}: missing inquiry form for privacy check")
        for form in forms:
            if ACUITY not in form:
                failures.append(f"{page}: form fallback is not the exact Acuity URL")
            if "inquiry-fallback" in form:
                failures.append(f"{page}: provisional inquiry-fallback copy is still visible")
            if "Book a virtual consultation" not in form:
                failures.append(f"{page}: empty-endpoint submit label must book the consultation")
            if 'name="location"' not in form or form.count('name="location"') < 3:
                failures.append(f"{page}: missing native location radio group")
            for field in PRIVACY_FIELDS:
                if not re.search(rf'(?<![\w-])name="{field}"', form):
                    failures.append(f"{page}: missing name={field}")
                if not re.search(rf'data-field-name="{field}"', form):
                    failures.append(f"{page}: missing data-field-name={field}")
                controls = re.findall(
                    rf'<(?:input|textarea)[^>]*(?:name="{field}"|data-field-name="{field}")[^>]*>',
                    form,
                )
                if not controls:
                    failures.append(f"{page}: no control found for {field}")
                for tag in controls:
                    if "disabled" not in tag:
                        failures.append(f"{page}: {field} must be statically disabled")
                    if "data-js-enable" not in tag:
                        failures.append(f"{page}: {field} missing data-js-enable")
            if not re.search(
                r'<fieldset[^>]*data-field="location"[^>]*aria-describedby=',
                form,
            ):
                failures.append(f"{page}: location fieldset missing aria-describedby")

    if "setAttribute(\"aria-invalid\"" not in site_js and "setAttribute('aria-invalid'" not in site_js:
        failures.append("site.js setError must set aria-invalid on controls")
    if "removeAttribute(\"aria-invalid\")" not in site_js and "removeAttribute('aria-invalid')" not in site_js:
        failures.append("site.js setError must remove aria-invalid on controls")
    if "wireExclusiveRadios" in site_js:
        failures.append("site.js still emulates radio exclusivity")
    if "enableVisitorControls" not in site_js:
        failures.append("site.js must enable visitor controls after init")
    submit_at = site_js.find('form.addEventListener("submit"')
    enable_at = site_js.find("enableVisitorControls(form);")
    if submit_at < 0 or enable_at < 0 or enable_at < submit_at:
        failures.append("site.js must attach submit before enabling visitor controls")
    if "window.location.assign(consultHref)" not in site_js:
        failures.append("site.js empty-endpoint submit must go directly to Acuity")
    empty_block = re.search(r"if\s*\(\s*!endpoint\s*\)\s*\{([^}]+)\}", site_js)
    if not empty_block or "location.assign" not in empty_block.group(1) or "validateInquiry" in empty_block.group(1):
        failures.append("site.js empty-endpoint submit must go directly to Acuity without validation")
    css = (ROOT / "assets/site.css").read_text(encoding="utf-8")
    if ".no-js .loader" not in css:
        failures.append("site.css must hide the loader in no-js")
    if ".nav__panel{display:block;position:static" not in css:
        failures.append("site.css must keep the simplified mobile navigation visible without a menu")
    if "@media (min-width:881px)" not in css:
        failures.append("site.css must keep desktop beat geometry scoped above the mobile breakpoint")
    if "touch-action:pan-x pinch-zoom" not in css:
        failures.append("site.css must reserve vertical touch for the mobile beat controller")
    check_visual_labels(failures)
    check_nojs_and_entity(failures)
    check_launch_product_urls(failures)


def load_configure_launch():
    path = ROOT / "scripts" / "configure-launch.py"
    spec = importlib.util.spec_from_file_location("configure_launch", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def check_visual_labels(failures: list[str]) -> None:
    labels = load_visual_labels()
    if len(labels) != 132:
        failures.append(f"visual labels expected 132 IDs, found {len(labels)}")
        return
    local = json.loads((ROOT / "media/local-manifest.json").read_text(encoding="utf-8"))
    tattoos = [
        row
        for row in local.get("assets", [])
        if row.get("source_category") == "tattoo" and row.get("status") in {"ok", "reused"}
    ]
    tattoo_ids = {row["asset_id"] for row in tattoos}
    if tattoo_ids != set(labels):
        missing = sorted(set(labels) - tattoo_ids)
        extra = sorted(tattoo_ids - set(labels))
        failures.append(f"visual-label IDs drifted missing={missing[:8]} extra={extra[:8]}")
        return
    for row in tattoos:
        expected_alt, expected_caption = labels[row["asset_id"]]
        if row.get("alt") != expected_alt or row.get("caption") != expected_caption:
            failures.append(f"{row['asset_id']}: local-manifest labels are not the visual-label pair")
            break
        for phrase in GENERIC_TATTOO_LABELS:
            blob = f"{row.get('alt', '')} {row.get('caption', '')}".lower()
            if phrase in blob:
                failures.append(f"{row['asset_id']}: generic tattoo label {phrase!r}")
                break
        if FILENAME_LABEL.match((row.get("alt") or "").strip()) or FILENAME_LABEL.match((row.get("caption") or "").strip()):
            failures.append(f"{row['asset_id']}: filename-only tattoo label")
    portfolio = (ROOT / "portfolio.html").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "assets/portfolio-manifest.json").read_text(encoding="utf-8"))
    seen: set[str] = set()
    for cat in manifest["categories"]:
        for item in cat["items"]:
            asset_id = item["asset_id"]
            seen.add(asset_id)
            expected_alt, expected_caption = labels[asset_id]
            if item.get("alt") != expected_alt or item.get("caption") != expected_caption:
                failures.append(f"{asset_id}: portfolio-manifest labels drifted")
                return
            fig = re.search(
                rf'<figure[^>]*data-asset-id="{re.escape(asset_id)}"[^>]*>[\s\S]*?</figure>',
                portfolio,
            )
            if not fig:
                failures.append(f"portfolio.html missing figure {asset_id}")
                return
            rendered = unescape(fig.group(0))
            if expected_alt not in rendered:
                failures.append(f"portfolio.html {asset_id}: alt is not the visual-label text")
                return
            if expected_caption not in rendered:
                failures.append(f"portfolio.html {asset_id}: caption is not the visual-label text")
                return
    if seen != set(labels):
        failures.append("portfolio-manifest IDs are not the visual-label set")
    images_map = unescape((ROOT / "sitemap-images.xml").read_text(encoding="utf-8"))
    for row in tattoos:
        title = row["caption"]
        if f"<image:title>{title}</image:title>" not in images_map:
            failures.append(f"sitemap-images.xml missing visual caption for {row['asset_id']}")
            return
    if "IRE-LARGE-COLOR-SLEEVE-59-60" in portfolio or 'data-group="IRE-LARGE-COLOR-SLEEVE-59-60"' in json.dumps(local):
        failures.append("I59/I60 false grouping remains in rendered or local manifests")


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def check_nojs_and_entity(failures: list[str]) -> None:
    css = (ROOT / "assets/site.css").read_text(encoding="utf-8")
    if ".no-js .loader{display:none!important}" not in css.replace(" ", ""):
        if ".no-js .loader" not in css or "display:none" not in css:
            failures.append("no-js CSS does not hide the loader")
    for page in PAGES:
        raw = (ROOT / page).read_text(encoding="utf-8")
        if 'class="no-js"' not in raw:
            failures.append(f"{page}: missing no-js document state")
        if "document.documentElement.className.replace" not in raw:
            failures.append(f"{page}: missing first-party no-js boot script")
        if '"TattooParlor"' in raw or '"@type":["TattooParlor"' in raw or '"@type": ["TattooParlor"' in raw:
            if f'"name": "{BUSINESS_NAME}"' not in raw and f'"name":"{BUSINESS_NAME}"' not in raw:
                failures.append(f"{page}: LocalBusiness name is not {BUSINESS_NAME}")
        if GOOGLE_MAPS_CID not in raw:
            failures.append(f"{page}: missing Google Maps CID in entity sameAs")
        if "inquiry-fallback" in raw:
            failures.append(f"{page}: visitor-facing inquiry-fallback remains")


def check_launch_product_urls(failures: list[str]) -> None:
    module = load_configure_launch()
    rehearsal = module.rehearsal_product_url_check()
    failures.extend(rehearsal)
    current = module.collect(module.current_origin(), False)
    failures.extend(module.product_urls_intact(current))
    merch = (ROOT / "merch.html").read_text(encoding="utf-8")
    for url in PRODUCT_URLS:
        if url not in merch:
            failures.append(f"merch.html missing protected product URL {url}")

    for path in ROOT.glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{path.name}: JSON parse error: {exc}")
    for path in (ROOT / "assets").glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"assets/{path.name}: JSON parse error: {exc}")
    for extra in (ROOT / "data/site-assets.json", ROOT / "media/local-manifest.json"):
        if extra.exists():
            try:
                json.loads(extra.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                failures.append(f"{extra.relative_to(ROOT).as_posix()}: JSON parse error: {exc}")
    for page in PAGES:
        for idx, block in enumerate(extract_ld_blocks((ROOT / page).read_text(encoding="utf-8"))):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                failures.append(f"{page}: JSON-LD {idx} parse error: {exc}")


def primary_book_targets(index_html: str) -> list[str]:
    targets = []
    nav = re.search(r'class="nav__header-cta"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*class="nav__header-cta"', index_html)
    if nav:
        targets.append(next(g for g in nav.groups() if g))
    else:
        cta = re.search(r'<a href="([^"]+)"[^>]*class="nav__header-cta"', index_html)
        if cta:
            targets.append(cta.group(1))
    for pattern in (
        r'<a class="btn btn--seal" href="([^"]+)"[^>]*>\s*<span>Start a project</span>',
        r'<a class="btn" href="([^"]+)"[^>]*>\s*<span>Start a consultation</span>',
        r'<a class="btn" href="([^"]+)"[^>]*>\s*<span>Start an inquiry</span>',
        r'<section class="visit"[\s\S]*?<h3>Booking</h3>\s*<p><a href="([^"]+)"',
        r'id="consult-dock"\s*href="([^"]+)"',
    ):
        match = re.search(pattern, index_html)
        if match:
            targets.append(match.group(1))
    return targets


def main() -> int:
    failures: list[str] = []
    notes: list[str] = []
    origin, indexable = expected_origin()
    parsed_pages: dict[str, PageParser] = {}

    for page in PAGES:
        path = ROOT / page
        if not path.exists():
            failures.append(f"missing page {page}")
            continue
        raw = path.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(raw)
        parsed_pages[page] = parser
        title = "".join(parser.title_parts).strip()
        if not title:
            failures.append(f"{page}: missing title")
        if parser.h1_count != 1:
            failures.append(f"{page}: expected 1 h1, found {parser.h1_count}")
        expected = f"{origin}/" if page == "index.html" else f"{origin}/{page}"
        if parser.canonical != expected:
            failures.append(f"{page}: canonical {parser.canonical!r} != {expected!r}")
        robots_blob = " ".join(parser.robots_meta).lower() + raw.lower()
        if indexable:
            if "noindex" in robots_blob:
                failures.append(f"{page}: noindex remains in indexable mode")
        else:
            if "noindex" not in robots_blob or "nofollow" not in robots_blob:
                failures.append(f"{page}: missing noindex/nofollow for preview host")
        if parser.has_concept_banner or "Unofficial Design Concept" in raw:
            failures.append(f"{page}: concept banner still present")
        if not parser.has_skip:
            failures.append(f"{page}: missing skip link")
        if 'property="og:title"' not in raw or 'name="twitter:card"' not in raw:
            failures.append(f"{page}: missing Open Graph or Twitter metadata")
        if "application/ld+json" not in raw:
            failures.append(f"{page}: missing JSON-LD")
        if "TattooParlor" not in raw or "Person" not in raw:
            failures.append(f"{page}: JSON-LD missing Person or TattooParlor")
        visible = parser.visible.lower()
        for phrase in INTERNAL:
            if phrase in visible:
                failures.append(f"{page}: visitor-facing internal phrase {phrase!r}")
        if "manifest" in visible and "portfolio" not in page:
            if re.search(r"\bmanifest\b", visible):
                failures.append(f"{page}: visitor-facing 'manifest'")
        if len(parser.ids) != len(set(parser.ids)):
            dup = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
            failures.append(f"{page}: duplicate ids {dup}")

        for href in parser.hrefs:
            if href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                continue
            target = local_path(href.split("?")[0])
            if target and not target.exists():
                failures.append(f"{page}: broken href {href}")
        for src in parser.srcs:
            if src.startswith(("http://", "https://", "data:")):
                continue
            target = local_path(src.split("?")[0])
            if target and not target.exists():
                failures.append(f"{page}: broken src {src}")

        unlabeled = []
        for cid in parser.control_ids:
            if cid not in parser.labels_for:
                unlabeled.append(cid)
        if unlabeled:
            still = []
            for cid in unlabeled:
                if not re.search(rf"<label[^>]*>[\s\S]*?id=\"{re.escape(cid)}\"", raw):
                    still.append(cid)
            if still:
                failures.append(f"{page}: unlabeled controls {still}")

        if page == "booking.html" and parser.inquiry_forms < 1:
            failures.append("booking.html: missing inquiry form")
        if parser.nav_cta != ACUITY:
            failures.append(f"{page}: header consultation CTA must use the exact Acuity URL")
        expected_mark = "#top" if page == "index.html" else "index.html#top"
        expected_nav_hrefs = [expected_mark, "portfolio.html", ACUITY]
        if parser.nav_hrefs != expected_nav_hrefs:
            failures.append(
                f"{page}: primary header must contain only mark, Portfolio, and consultation CTA; "
                f"found {parser.nav_hrefs}"
            )
        if 'class="nav__toggle"' in raw or 'class="nav__more-btn"' in raw:
            failures.append(f"{page}: obsolete mobile menu or Shop control remains in primary header")

    index_raw = (ROOT / "index.html").read_text(encoding="utf-8")
    if 'data-prorok-form="inquiry"' in index_raw or 'class="inquiry-chapter"' in index_raw:
        failures.append("index.html: homepage inquiry form must stay removed")
    if 'id="start"' in index_raw:
        failures.append("index.html: leftover How to get started teaser #start")

    folio = parsed_pages.get("portfolio.html")
    if folio and folio.portfolio_figures != 132:
        failures.append(f"portfolio.html: expected 132 figures, found {folio.portfolio_figures}")
    flash = parsed_pages.get("flash.html")
    if flash and flash.flash_figures != 20:
        failures.append(f"flash.html: expected 20 figures, found {flash.flash_figures}")
    art = parsed_pages.get("art.html")
    if art and art.art_figures != 32:
        failures.append(f"art.html: expected 32 figures, found {art.art_figures}")
    merch = parsed_pages.get("merch.html")
    if merch and merch.merch_images != 6:
        failures.append(f"merch.html: expected 6 merch images, found {merch.merch_images}")

    for page, snippet in REQUIRED_COPY:
        text = (ROOT / page).read_text(encoding="utf-8")
        if snippet not in text:
            failures.append(f"{page}: missing required copy {snippet!r}")

    config = (ROOT / "assets/config.js").read_text(encoding="utf-8")
    empty_endpoint = 'formEndpoint: ""' in config or "formEndpoint:''" in config
    if empty_endpoint:
        targets = primary_book_targets(index_raw)
        if not targets:
            failures.append("index.html: could not find primary Book paths")
        booking_only = [href for href in targets if "booking.html" in href and "as.me" not in href]
        if booking_only:
            failures.append(
                "empty-endpoint build: primary Book paths point only to booking.html: "
                + ", ".join(booking_only)
            )
        if ACUITY not in index_raw:
            failures.append("index.html: missing working Acuity consultation URL")
        if "Tattoo inquiry" not in index_raw or "booking.html" not in index_raw:
            failures.append("index.html: missing Tattoo inquiry route to booking.html")
    if re.search(r"sk-[A-Za-z0-9]{10,}", config) or re.search(r"apiKey\s*[:=]\s*['\"][^'\"]+", config):
        failures.append("config.js appears to contain a secret")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if indexable:
        if "Disallow: /" in robots and "Allow: /" not in robots:
            failures.append("robots.txt blocks crawlers in indexable mode")
    else:
        if "Disallow: /" not in robots:
            failures.append("robots.txt must Disallow / on the preview host")
    if f"Sitemap: {origin}/sitemap.xml" not in robots:
        failures.append("robots.txt sitemap origin mismatch")

    try:
        ET.parse(ROOT / "sitemap.xml")
        ET.parse(ROOT / "sitemap-pages.xml")
        ET.parse(ROOT / "sitemap-images.xml")
    except ET.ParseError as exc:
        failures.append(f"sitemap XML parse error: {exc}")

    pages_map = (ROOT / "sitemap-pages.xml").read_text(encoding="utf-8")
    page_locs = re.findall(r"<loc>(.*?)</loc>", pages_map)
    expected_locs = [f"{origin}/"] + [f"{origin}/{p}" for p in PAGES if p != "index.html"]
    if sorted(page_locs) != sorted(expected_locs):
        failures.append(f"sitemap-pages.xml locs mismatch: {page_locs}")

    manifest = json.loads((ROOT / "assets/portfolio-manifest.json").read_text(encoding="utf-8"))
    manifest_files = []
    for cat in manifest["categories"]:
        for item in cat["items"]:
            rel = item["src"]
            manifest_files.append(rel)
            if not (ROOT / rel).exists():
                failures.append(f"manifest asset missing: {rel}")
    if len(manifest_files) != 132:
        failures.append(f"portfolio-manifest.json expected 132 items, found {len(manifest_files)}")
    images_map = (ROOT / "sitemap-images.xml").read_text(encoding="utf-8")
    image_locs = re.findall(r"<image:loc>(.*?)</image:loc>", images_map)
    if len(image_locs) < 132:
        failures.append(f"sitemap-images.xml expected at least 132 images, found {len(image_locs)}")
    for rel in manifest_files:
        if f"{origin}/{rel}" not in image_locs:
            failures.append(f"sitemap-images.xml missing {rel}")
            break
    if any("squarespace-cdn.com" in loc for loc in image_locs):
        failures.append("sitemap-images.xml advertises Squarespace CDN URLs")
    if origin != "https://www.dylanprorok.com" and any(
        loc.startswith("https://www.dylanprorok.com/") for loc in image_locs
    ):
        failures.append("preview sitemap advertises production image URLs")

    cname = (ROOT / "CNAME").read_text(encoding="utf-8").strip()
    if cname != "prorok.jarrettwroten.com":
        failures.append(f"CNAME changed to {cname!r}")

    local_manifest = json.loads((ROOT / "media/local-manifest.json").read_text(encoding="utf-8"))
    rights = {row.get("rights_status") for row in local_manifest.get("assets", [])}
    if rights - {"confirmation-required", None}:
        failures.append(f"local manifest rights_status drifted: {rights}")

    check_correction_wave(failures)

    if "alluring enough to draw you closer" in index_raw:
        failures.append("index.html still uses the uncorrected supplied headline")
    if BUSINESS_NAME not in index_raw:
        failures.append("index.html missing Dylan Prorok Tattoo business name")
    if GOOGLE_MAPS_CID not in index_raw:
        failures.append("index.html missing Google Maps CID in entity markup")
    if "Dylan Prorok Tattoo on Google" not in index_raw:
        failures.append("index.html missing updated Google review source label")
    if "IRE-LARGE-COLOR-SLEEVE-59-60" in (ROOT / "portfolio.html").read_text(encoding="utf-8"):
        failures.append("portfolio.html still groups TAT-IRE-059 and TAT-IRE-060")

    if failures:
        print("FAIL")
        for item in failures:
            print(f"- {item}")
        return 1
    print("PASS")
    print(f"checked {len(PAGES)} HTML pages against origin {origin} indexable={indexable}")
    print(f"portfolio manifest images: {len(manifest_files)}")
    print(f"image sitemap entries: {len(image_locs)}")
    for note in notes:
        print(f"note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
