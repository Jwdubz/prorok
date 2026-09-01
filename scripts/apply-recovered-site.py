#!/usr/bin/env python3
"""Write static galleries, manifests, sitemaps, and staging-safe chrome."""

from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prorok_assets import (  # noqa: E402
    SETMORE_CONSULT_URL,
    BUSINESS_NAME,
    FROZEN_GROUPS,
    FROZEN_MANIFEST,
    GOOGLE_MAPS_CID,
    LOCAL_MANIFEST,
    NOJS_BOOT,
    PERSON_NAME,
    PREVIEW_ORIGIN,
    ROOT,
    business_same_as,
    group_note,
    parse_page_index,
    person_same_as,
    restore_product_urls,
    shield_product_urls,
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
ROBOTS = "noindex, nofollow, noarchive, nosnippet, noimageindex"
FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;800&family=Shippori+Mincho:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
    '<link rel="stylesheet" href="assets/site.css">'
)
SCRIPTS = (
    '<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>\n'
    '<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/ScrollTrigger.min.js"></script>\n'
    '<script src="https://cdn.jsdelivr.net/npm/lenis@1.1.13/dist/lenis.min.js"></script>\n'
    '<script src="assets/config.js"></script>\n'
    '<script src="assets/site.js"></script>'
)
PRODUCTS = [
    {
        "title": "Gwap Geisha Print",
        "price": "$40",
        "copy": "Hand printed on 18×15 cotton posters.",
        "url": "https://www.dylanprorok.com/store/p/gwap-geisha-print",
        "ids": ["MER-PRT-001", "MER-PRT-002", "MER-PRT-003"],
    },
    {
        "title": "Ko Omote T-Shirt",
        "price": "$30",
        "copy": "100% cotton blank with a hand-woven label.",
        "url": "https://www.dylanprorok.com/store/p/ko-omote-t-shirt",
        "ids": ["MER-SHT-001", "MER-SHT-002", "MER-SHT-003"],
    },
]


def h(text: str) -> str:
    return html.escape(text, quote=True)


def load_library() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    payload = json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))
    assets = [row for row in payload["assets"] if row.get("status") in {"ok", "reused"}]
    by_id = {row["asset_id"]: row for row in assets}
    groups = {}
    with FROZEN_GROUPS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            groups[row["duplicate_group"]] = row
    return assets, by_id, groups


def load_csv_rows() -> list[dict]:
    with FROZEN_MANIFEST.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def page_url(page: str, origin: str) -> str:
    return f"{origin}/" if page == "index.html" else f"{origin}/{page}"


def og_block(page: str, origin: str, title: str, description: str, image: dict) -> str:
    url = page_url(page, origin)
    image_url = f"{origin}/{image['src']}"
    return f"""<link rel="canonical" href="{h(url)}" />
<meta name="robots" content="{ROBOTS}" />
<meta property="og:site_name" content="Dylan Prorok" />
<meta property="og:type" content="{'profile' if page == 'about.html' else 'website'}" />
<meta property="og:title" content="{h(title)}" />
<meta property="og:description" content="{h(description)}" />
<meta property="og:url" content="{h(url)}" />
<meta property="og:image" content="{h(image_url)}" />
<meta property="og:image:width" content="{image['width']}" />
<meta property="og:image:height" content="{image['height']}" />
<meta property="og:locale" content="en_US" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{h(title)}" />
<meta name="twitter:description" content="{h(description)}" />
<meta name="twitter:image" content="{h(image_url)}" />"""


def json_ld(page: str, origin: str, title: str, page_type: str, image_src: str) -> str:
    url = page_url(page, origin)
    person_image = f"{origin}/{image_src}"
    graph = [
        {
            "@type": page_type,
            "@id": f"{url}#webpage",
            "url": url,
            "name": title,
            "isPartOf": {"@id": f"{origin}/#website"},
            "about": {"@id": f"{origin}/#person"},
        },
        {
            "@type": "Person",
            "@id": f"{origin}/#person",
            "name": PERSON_NAME,
            "jobTitle": "Japanese tattoo artist",
            "url": f"{origin}/",
            "image": person_image,
            "worksFor": {"@id": f"{origin}/#studio"},
            "sameAs": person_same_as(),
        },
        {
            "@type": ["TattooParlor", "LocalBusiness"],
            "@id": f"{origin}/#studio",
            "name": BUSINESS_NAME,
            "url": f"{origin}/",
            "image": person_image,
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "3827 Sunset Rd",
                "addressLocality": "Las Vegas",
                "addressRegion": "NV",
                "postalCode": "89120",
                "addressCountry": "US",
            },
            "sameAs": business_same_as(),
        },
    ]
    if page == "index.html":
        graph.insert(
            0,
            {
                "@type": "WebSite",
                "@id": f"{origin}/#website",
                "url": f"{origin}/",
                "name": "Dylan Prorok",
                "publisher": {"@id": f"{origin}/#person"},
            },
        )
    return (
        '<script type="application/ld+json">\n'
        + json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=None)
        + "\n</script>"
    )


def nav(current: str) -> str:
    home = "" if current == "index.html" else "index.html"
    def href(target: str) -> str:
        if target.startswith("#"):
            return target if current == "index.html" else f"index.html{target}"
        return target
    def current_attr(page: str) -> str:
        return ' aria-current="page"' if current == page else ""
    shop_current = current in {"flash.html", "art.html", "merch.html"}
    return f"""<header class="site-header">
  <nav class="nav" aria-label="Primary">
    <a class="nav__mark" href="{href('#top')}"><i>和彫</i><span>Dylan Prorok</span></a>
    <button type="button" class="nav__toggle" aria-expanded="false" aria-controls="site-menu">Menu</button>
    <div class="nav__panel" id="site-menu">
      <div class="nav__links">
        <a href="portfolio.html" class="nav__portfolio"{current_attr("portfolio.html")}>Portfolio</a>
        <a href="{href('#scale')}">Scale</a>
        <a href="{href('#work')}">Work</a>
        <a href="{href('#healed')}">Healed</a>
        <a href="{href('#craft')}">Process</a>
        <a href="about.html"{current_attr("about.html")}>About</a>
        <div class="nav__more">
          <button type="button" class="nav__more-btn" aria-expanded="false" aria-controls="nav-shop">Shop</button>
          <div class="nav__sub" id="nav-shop">
            <a href="flash.html"{current_attr("flash.html")}>Flash</a>
            <a href="art.html"{current_attr("art.html")}>Art</a>
            <a href="merch.html"{current_attr("merch.html")}>Merch</a>
          </div>
        </div>
        <a href="booking.html"{current_attr("booking.html")}>Tattoo inquiry</a>
        <a href="{h(SETMORE_CONSULT_URL)}" class="nav__cta" target="_blank" rel="noopener">Book</a>
      </div>
    </div>
  </nav>
</header>"""


def visit_footer(current: str) -> str:
    book_current = ' aria-current="page"' if current == "booking.html" else ""
    return f"""<section class="visit" id="visit">
  <div class="visit__inner">
    <h2>Come find me.</h2>
    <div class="visit__block">
      <h3>Studio</h3>
      <p>Heritage Tattoo<br />3827 Sunset Rd<br />Las Vegas, NV 89120</p>
    </div>
    <div class="visit__block">
      <h3>Usual hours</h3>
      <p>Tuesday – Saturday<br />Noon – 8pm</p>
    </div>
    <div class="visit__block">
      <h3>Booking</h3>
      <p><a href="{h(SETMORE_CONSULT_URL)}" target="_blank" rel="noopener">Book a virtual consultation</a><br />
         <a href="booking.html"{book_current}>Send a tattoo inquiry</a><br />
         or DM me — I answer both.</p>
    </div>
    <div class="visit__block">
      <h3>Elsewhere</h3>
      <p><a href="https://www.instagram.com/dylanprorok/" target="_blank" rel="noopener">@dylanprorok</a> ·
         <a href="https://www.tiktok.com/@dylanprorok_dylontattoo" target="_blank" rel="noopener">TikTok</a><br />
         <a href="https://www.instagram.com/heritagetattoolv/" target="_blank" rel="noopener">@heritagetattoolv</a></p>
    </div>
  </div>
</section>

<footer class="foot">
  <span>© 2026 Dylan Prorok</span>
  <nav class="foot__links" aria-label="Footer">
    <a href="portfolio.html"{' aria-current="page"' if current == 'portfolio.html' else ''}>Portfolio</a>
    <a href="about.html"{' aria-current="page"' if current == 'about.html' else ''}>About</a>
    <a href="flash.html"{' aria-current="page"' if current == 'flash.html' else ''}>Flash</a>
    <a href="art.html"{' aria-current="page"' if current == 'art.html' else ''}>Art</a>
    <a href="merch.html"{' aria-current="page"' if current == 'merch.html' else ''}>Merch</a>
    <a href="booking.html"{' aria-current="page"' if current == 'booking.html' else ''}>Tattoo inquiry</a>
    <a href="{h(SETMORE_CONSULT_URL)}" target="_blank" rel="noopener">Book</a>
  </nav>
  <span class="foot__seal">彫</span>
  <span>Las Vegas, Nevada</span>
</footer>"""


def dock() -> str:
    return f"""<a class="consult-dock" id="consult-dock"
   href="{h(SETMORE_CONSULT_URL)}"
   target="_blank" rel="noopener">Book a Virtual Consultation</a>"""


def inquiry_form(prefix: str) -> str:
    def i(name: str) -> str:
        return f"{prefix}{name}" if prefix else name

    return f"""<form class="inquiry" data-prorok-form="inquiry" action="{h(SETMORE_CONSULT_URL)}" method="get" novalidate>
    <div class="field">
      <label class="field__label" for="{i('name')}">Name</label>
      <input id="{i('name')}" name="name" data-field-name="name" data-js-enable type="text" autocomplete="name" required disabled aria-describedby="{i('name-error')}" />
      <p class="field__error" id="{i('name-error')}"></p>
    </div>

    <div class="field">
      <label class="field__label" for="{i('description')}">Tattoo description</label>
      <p class="field__hint" id="{i('description-hint')}">Include style, subject matter, black and grey or full color, and a brief description of why you’re getting the tattoo.</p>
      <p class="field__example" id="{i('description-ex')}">Example: Japanese style Kitsune fox full color tattoo to represent my grandfather</p>
      <textarea id="{i('description')}" name="description" data-field-name="description" data-js-enable required disabled aria-describedby="{i('description-hint')} {i('description-ex')} {i('description-error')}"></textarea>
      <p class="field__error" id="{i('description-error')}"></p>
    </div>

    <div class="field">
      <label class="field__label" for="{i('placement')}">Tattoo placement and size</label>
      <p class="field__hint" id="{i('placement-hint')}">Include where on the body you’d like to place the tattoo. Include the approximate size or if you’d like a full sleeve.</p>
      <p class="field__example" id="{i('placement-ex')}">Example: Right inner forearm about 5x7 inches, or Right arm full sleeve</p>
      <textarea id="{i('placement')}" name="placement" data-field-name="placement" data-js-enable required disabled aria-describedby="{i('placement-hint')} {i('placement-ex')} {i('placement-error')}"></textarea>
      <p class="field__error" id="{i('placement-error')}"></p>
    </div>

    <div class="field">
      <label class="field__label" for="{i('email')}">Email</label>
      <input id="{i('email')}" name="email" data-field-name="email" data-js-enable type="email" autocomplete="email" required disabled aria-describedby="{i('email-error')}" />
      <p class="field__error" id="{i('email-error')}"></p>
    </div>

    <div class="field">
      <label class="check" for="{i('newsletter')}">
        <input id="{i('newsletter')}" name="newsletter" data-field-name="newsletter" data-js-enable type="checkbox" value="yes" disabled />
        <span>Optional: email me when merchandise or flash releases go up. Leave this unchecked if you only want a reply about this tattoo.</span>
      </label>
    </div>

    <div class="field">
      <label class="field__label" for="{i('phone')}">Phone</label>
      <input id="{i('phone')}" name="phone" data-field-name="phone" data-js-enable type="tel" autocomplete="tel" disabled aria-describedby="{i('phone-hint')}" />
      <p class="field__hint" id="{i('phone-hint')}">Optional. Use this if you would rather be reached by phone.</p>
    </div>

    <fieldset class="field" data-field="location" aria-describedby="{i('location-error')}">
      <legend class="field__label">Where are you looking to get tattooed?</legend>
      <div class="radios">
        <label class="radio" for="{i('loc-local')}">
          <input id="{i('loc-local')}" name="location" data-field-name="location" data-js-enable type="radio" value="las-vegas-local" required disabled />
          <span>Las Vegas local</span>
        </label>
        <label class="radio" for="{i('loc-travel')}">
          <input id="{i('loc-travel')}" name="location" data-field-name="location" data-js-enable type="radio" value="traveling-to-las-vegas" disabled />
          <span>Traveling to Las Vegas</span>
        </label>
        <label class="radio" for="{i('loc-guest')}">
          <input id="{i('loc-guest')}" name="location" data-field-name="location" data-js-enable type="radio" value="out-of-town-convention-or-guest-spot" disabled />
          <span>Out-of-town convention or guest spot</span>
        </label>
      </div>
      <p class="field__error" id="{i('location-error')}"></p>
    </fieldset>

    <div class="field field--file">
      <label class="field__label" for="{i('photos')}">Photo references</label>
      <p class="field__hint" id="{i('photos-hint')}">Please include photo references of tattoos or artwork you like. Please do not send AI-rendered images of your ideas. Accepted formats: JPEG, PNG, WebP, and HEIC. Multiple files are welcome. Each file should stay under 10 MB.</p>
      <input id="{i('photos')}" name="photos" data-field-name="photos" data-js-enable type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif" multiple disabled aria-describedby="{i('photos-hint')} {i('photos-error')}" />
      <p class="field__error" id="{i('photos-error')}"></p>
    </div>

    <div class="form-actions">
      <button class="btn btn--seal" type="submit"><span>Book a virtual consultation</span></button>
    </div>
    <div class="form-status" role="status" aria-live="polite" hidden></div>
  </form>"""


def figure_markup(asset: dict, eager: bool = False, extra_class: str = "") -> str:
    attrs = [
        f'src="{h(asset["local_path"])}"',
        f'alt="{h(asset["alt"])}"',
        f'width="{asset["width"]}"',
        f'height="{asset["height"]}"',
        'decoding="async"',
    ]
    if eager:
        attrs.append('loading="eager"')
        attrs.append('fetchpriority="high"')
    else:
        attrs.append('loading="lazy"')
    cls = f' class="{extra_class}"' if extra_class else ""
    group = f' data-group="{h(asset["duplicate_group"])}"' if asset.get("duplicate_group") else ""
    return (
        f'<figure{cls} data-asset-id="{h(asset["asset_id"])}"{group}>\n'
        f'        <img {" ".join(attrs)} />\n'
        f'        <figcaption>{h(asset["caption"])}</figcaption>\n'
        f"      </figure>"
    )


def clustered(assets: list[dict], groups: dict[str, dict], category: str | None = None, subcategory: str | None = None) -> list[list[dict]]:
    filtered = [
        row
        for row in assets
        if (category is None or row["source_category"] == category)
        and (subcategory is None or row["source_subcategory"] == subcategory)
    ]
    filtered.sort(key=lambda row: (parse_page_index(row), row["asset_id"]))
    emitted: set[str] = set()
    clusters: list[list[dict]] = []
    by_id = {row["asset_id"]: row for row in filtered}
    for row in filtered:
        if row["asset_id"] in emitted:
            continue
        group_id = row.get("duplicate_group") or ""
        group = groups.get(group_id)
        if group:
            members = []
            for member_id in group["member_asset_ids"].split("|"):
                if member_id in by_id:
                    members.append(by_id[member_id])
            if members:
                members.sort(key=lambda item: (parse_page_index(item), item["asset_id"]))
                clusters.append(members)
                emitted.update(item["asset_id"] for item in members)
                continue
        clusters.append([row])
        emitted.add(row["asset_id"])
    return clusters


def render_clusters(clusters: list[list[dict]], groups: dict[str, dict], grid_class: str, first_eager: bool) -> str:
    parts = []
    eager_used = not first_eager
    for cluster in clusters:
        eager = not eager_used
        eager_used = True
        if len(cluster) == 1:
            wrap_open = ""
            wrap_close = ""
            body = figure_markup(cluster[0], eager=eager)
        else:
            group_id = cluster[0].get("duplicate_group") or ""
            group = groups.get(group_id, {})
            note = group_note(group_id, group.get("relationship", ""), [item["asset_id"] for item in cluster])
            wrap_open = (
                f'<div class="folio-group" data-group="{h(group_id)}">\n'
                f'      <p class="folio-group__note">{h(note)}</p>\n'
                f'      <div class="folio-group__grid">\n        '
            )
            wrap_close = "\n      </div>\n    </div>"
            body = "\n        ".join(
                figure_markup(item, eager=(eager and idx == 0)) for idx, item in enumerate(cluster)
            )
        if grid_class in {"flash-grid", "art-grid"} and len(cluster) == 1:
            extra = []
            for item, markup in ((cluster[0], body),):
                if item["source_category"] == "flash":
                    extra.append(
                        f'<article class="flash-card">{markup}\n'
                        f'      <p class="card__action"><a href="booking.html?source=flash&amp;design={h(item["asset_id"])}">Inquire about this flash</a></p>\n'
                        f"    </article>"
                    )
                else:
                    extra.append(f'<article class="art-card">{markup}</article>')
                parts.append(extra[0])
        elif grid_class in {"flash-grid", "art-grid"}:
            cards = []
            for idx, item in enumerate(cluster):
                fig = figure_markup(item, eager=(eager and idx == 0))
                if item["source_category"] == "flash":
                    cards.append(
                        f'<article class="flash-card">{fig}\n'
                        f'      <p class="card__action"><a href="booking.html?source=flash&amp;design={h(item["asset_id"])}">Inquire about this flash</a></p>\n'
                        f"    </article>"
                    )
                else:
                    cards.append(f'<article class="art-card">{fig}</article>')
            parts.append(wrap_open + "\n        ".join(cards) + wrap_close)
        else:
            parts.append(wrap_open + body + wrap_close)
    return "\n    ".join(parts)


def interior_page(
    page: str,
    title: str,
    description: str,
    page_type: str,
    image: dict,
    body: str,
    extra_scripts: str = "",
    main_class: str = "page",
    origin: str = PREVIEW_ORIGIN,
) -> str:
    return f"""<!DOCTYPE html>
<html class="no-js" lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
{NOJS_BOOT}
<title>{h(title)}</title>
<meta name="description" content="{h(description)}" />
{og_block(page, origin, title, description, image)}
{json_ld(page, origin, title, page_type, image["src"])}
{FONTS}
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<div class="grain" aria-hidden="true"></div>
<canvas id="petals" aria-hidden="true"></canvas>

{nav(page)}

{dock()}

<main class="{main_class}" id="main">
{body}
</main>

{visit_footer(page)}

{SCRIPTS}
{extra_scripts}
</body>
</html>
"""


def replace_origin_in_existing(text: str, origin: str) -> str:
    text, tokens = shield_product_urls(text)
    text = text.replace("https://www.dylanprorok.com", origin)
    text = restore_product_urls(text, tokens)
    if 'name="robots"' not in text:
        text = text.replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
            f'<meta name="robots" content="{ROBOTS}" />\n',
            1,
        )
    return text


def ensure_nojs_document(text: str) -> str:
    text = re.sub(r"<html(?:\s+class=\"[^\"]*\")?\s+lang=\"en\">", '<html class="no-js" lang="en">', text, count=1)
    if "document.documentElement.className.replace" not in text:
        text = text.replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
            f"{NOJS_BOOT}\n",
            1,
        )
    return text


def replace_inquiry_block(text: str, prefix: str) -> str:
    return re.sub(
        r'<form class="inquiry" data-prorok-form="inquiry"[\s\S]*?</form>',
        inquiry_form(prefix),
        text,
        count=1,
    )


def ensure_maps_cid_in_sameas(text: str) -> str:
    def add_cid(match: re.Match[str]) -> str:
        block = match.group(0)
        if GOOGLE_MAPS_CID in block:
            return block
        return block[:-1] + f',"{GOOGLE_MAPS_CID}"]'

    return re.sub(r'"sameAs":\s*\[[^\]]*\]', add_cid, text)


def patch_shared_chrome(text: str, page: str) -> str:
    current = ' aria-current="page"' if page == "booking.html" else ""
    text = re.sub(
        r'<a href="booking\.html" class="nav__cta"(?: aria-current="page")?>Book</a>',
        f'<a href="booking.html"{current}>Tattoo inquiry</a>\n'
        f'        <a href="{h(SETMORE_CONSULT_URL)}" class="nav__cta" target="_blank" rel="noopener">Book</a>',
        text,
        count=1,
    )
    text = re.sub(
        r'<p><a href="booking\.html"(?: aria-current="page")?>Start an inquiry</a><br />\s*or DM me — I answer both\.<br />I’ll contact you to schedule\.</p>',
        f'<p><a href="{h(SETMORE_CONSULT_URL)}" target="_blank" rel="noopener">Book a virtual consultation</a><br />\n'
        f'         <a href="booking.html"{current}>Send a tattoo inquiry</a><br />\n'
        f"         or DM me — I answer both.</p>",
        text,
        count=1,
    )
    text = re.sub(
        r'(<nav class="foot__links" aria-label="Footer">.*?<a href="merch\.html"(?: aria-current="page")?>Merch</a>\s*)<a href="booking\.html"(?: aria-current="page")?>Book</a>',
        rf'\1<a href="booking.html"{current}>Tattoo inquiry</a>\n'
        f'    <a href="{h(SETMORE_CONSULT_URL)}" target="_blank" rel="noopener">Book</a>',
        text,
        count=1,
        flags=re.S,
    )
    return text


def patch_index(origin: str, og_image: dict) -> None:
    path = ROOT / "index.html"
    text = path.read_text(encoding="utf-8")
    text = replace_origin_in_existing(text, origin)
    text = ensure_nojs_document(text)
    text = text.replace(
        f'content="{origin}/dylan-portrait.jpg"',
        f'content="{origin}/{og_image["src"]}"',
    )
    text = patch_shared_chrome(text, "index.html")
    text = replace_inquiry_block(text, "home-")
    text = text.replace("alluring enough to draw you closer", "alluring to draw you closer")
    text = text.replace("Dylan Prorok at Heritage Tattoo", BUSINESS_NAME)
    text = text.replace("Dylan Prorok Tattoos on Google", f"{BUSINESS_NAME} on Google")
    text = text.replace(
        "media/site/dylon-prorok-original-japenese-tattoo-art-las-vegas-nevada.webp",
        "media/site/dylan-prorok-tattooing-large-scale-piece.webp",
    )
    text = text.replace("media/site/IMG_0518.webp", "media/site/japanese-sleeve-composition.webp")
    text = text.replace(
        "media/site/dylon-prorok-las-vegas-artist-and-tatoo.webp",
        "media/site/dylan-prorok-artist-portrait.webp",
    )
    text = ensure_maps_cid_in_sameas(text)
    text = text.replace(
        '<a class="btn btn--seal" href="booking.html"><span>Start a project</span></a>',
        f'<a class="btn btn--seal" href="{h(SETMORE_CONSULT_URL)}" target="_blank" rel="noopener"><span>Start a project</span></a>',
    )
    text = text.replace(
        '<a class="btn" href="booking.html"><span>Start an inquiry</span></a>',
        f'<a class="btn" href="{h(SETMORE_CONSULT_URL)}" target="_blank" rel="noopener"><span>Start a consultation</span></a>',
    )
    text = text.replace('<li>Merch <span><a href="merch.html">Future releases</a></span></li>',
                        '<li>Merch <span><a href="merch.html">Prints and shirts</a></span></li>')
    chapter = f"""<section class="inquiry-chapter" id="inquiry">
  <div class="inquiry-chapter__inner">
    <div class="sec__head">
      <span class="sec__jp" aria-hidden="true">始め</span>
      <h2 data-split>How to get started</h2>
      <p>I’d love to sit down and discuss your tattoo ideas more in depth. Whether you’re looking for a fully custom piece, know exactly what subject matter you’d like tattooed, or would just like to ask a few questions before committing to a tattoo, it all begins with a consultation.</p>
      <p>Fill out the form below to get started. I will respond as soon as possible. I’m excited to see what we can create together.</p>
    </div>
    {inquiry_form("home-")}
  </div>
</section>

"""
    if 'id="inquiry"' not in text:
        text = text.replace('<section class="scale" id="scale">', chapter + '<section class="scale" id="scale">')
    text = re.sub(
        r'<section class="start" id="start">[\s\S]*?</section>\n\n',
        "",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")


def patch_simple_page(page: str, origin: str, og_image: dict, extras: list[tuple[str, str]] | None = None) -> None:
    path = ROOT / page
    text = path.read_text(encoding="utf-8")
    text = replace_origin_in_existing(text, origin)
    text = ensure_nojs_document(text)
    text = text.replace(
        f'content="{origin}/dylan-portrait.jpg"',
        f'content="{origin}/{og_image["src"]}"',
    )
    text = patch_shared_chrome(text, page)
    text = text.replace("Dylan Prorok at Heritage Tattoo", BUSINESS_NAME)
    if page == "booking.html":
        text = replace_inquiry_block(text, "")
    if page == "about.html":
        text = text.replace(
            "media/site/dylon-prorok-las-vegas-artist-and-tatoo.webp",
            "media/site/dylan-prorok-artist-portrait.webp",
        )
    text = ensure_maps_cid_in_sameas(text)
    if page == "booking.html" and GOOGLE_MAPS_CID not in text:
        text = text.replace(
            f'"name":"{BUSINESS_NAME}","url":"{origin}/"',
            f'"name":"{BUSINESS_NAME}","url":"{origin}/","sameAs":{json.dumps(business_same_as())}',
        )
    for old, new in extras or []:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def write_gallery_pages(assets: list[dict], groups: dict[str, dict], origin: str, images: dict[str, dict]) -> None:
    irezumi = clustered(assets, groups, "tattoo", "irezumi")
    color = clustered(assets, groups, "tattoo", "color")
    bng = clustered(assets, groups, "tattoo", "black-and-grey")
    other = clustered(assets, groups, "tattoo", "aggregate-only")
    flash = clustered(assets, groups, "flash")
    art = clustered(assets, groups, "art")

    portfolio_body = f"""  <div class="sec__head">
    <span class="sec__jp" aria-hidden="true">作品集</span>
    <h1 data-split>Portfolio</h1>
    <p>Sleeves, backs, thighs, and hands. Drawn to the body they live on. Irezumi, illustrative color, and black and grey each have their own room.</p>
  </div>

  <nav class="folio-jump" aria-label="Portfolio categories">
    <a href="#irezumi">Irezumi</a>
    <a href="#color">Illustrative Color</a>
    <a href="#bng">Black &amp; Grey</a>
    <a href="#additional">Additional work</a>
  </nav>

  <section class="folio-cat" id="irezumi" data-category="irezumi">
    <div class="folio-cat__head">
      <h2>Irezumi</h2>
      <span aria-hidden="true">入れ墨</span>
    </div>
    <div class="folio folio-flow">
    {render_clusters(irezumi, groups, "folio-flow", True)}
    </div>
  </section>

  <section class="folio-cat" id="color" data-category="color">
    <div class="folio-cat__head">
      <h2>Illustrative Color</h2>
      <span aria-hidden="true">色彩</span>
    </div>
    <div class="folio folio-flow">
    {render_clusters(color, groups, "folio-flow", False)}
    </div>
  </section>

  <section class="folio-cat" id="bng" data-category="bng">
    <div class="folio-cat__head">
      <h2>Black &amp; Grey</h2>
      <span aria-hidden="true">墨</span>
    </div>
    <div class="folio folio-flow">
    {render_clusters(bng, groups, "folio-flow", False)}
    </div>
  </section>

  <section class="folio-cat" id="additional" data-category="other">
    <div class="folio-cat__head">
      <h2>Additional work</h2>
      <span aria-hidden="true">他</span>
    </div>
    <div class="folio folio-flow">
    {render_clusters(other, groups, "folio-flow", False)}
    </div>
  </section>

  <p class="page__go"><a href="{h(SETMORE_CONSULT_URL)}" target="_blank" rel="noopener">Book a virtual consultation</a></p>
"""
    (ROOT / "portfolio.html").write_text(
        interior_page(
            "portfolio.html",
            "Portfolio — Dylan Prorok, Las Vegas Japanese Tattoo Artist",
            "Irezumi, illustrative color, and black-and-grey tattoos by Dylan Prorok at Heritage Tattoo in Las Vegas. Sleeves, backs, thighs, and hands drawn to the body.",
            "WebPage",
            images["portfolio"],
            portfolio_body,
            main_class="page folio-page",
            origin=origin,
        ),
        encoding="utf-8",
    )

    flash_body = f"""  <div class="sec__head">
    <span class="sec__jp" aria-hidden="true">下絵</span>
    <h1 data-split>Flash</h1>
    <p>Pre-drawn work for a one-shot sitting, or a starting point for a custom idea. Size, placement, whether a design can be repeated, and the price are confirmed before booking.</p>
  </div>

  <div class="doors__grid" style="margin-top:0">
    <div class="door door--primary">
      <i>小</i>
      <h2>Inquire about a design</h2>
      <p>Size, placement, whether a design can be repeated, and the price are confirmed before we book.</p>
      <a class="btn btn--seal" href="booking.html?source=flash"><span>Start an inquiry</span></a>
    </div>
    <div class="door">
      <i>大</i>
      <h2>Or bring a custom idea</h2>
      <p>One-shot tattoos and small bangers are always welcome. A custom idea can be finished according to your allotted budget.</p>
      <a class="btn" href="booking.html"><span>Describe the piece</span></a>
    </div>
  </div>

  <section class="folio-cat" id="flash-library" aria-labelledby="flash-library-title">
    <div class="folio-cat__head">
      <h2 id="flash-library-title">Flash archive</h2>
      <span aria-hidden="true">図</span>
    </div>
    <div class="flash-grid">
    {render_clusters(flash, groups, "flash-grid", True)}
    </div>
  </section>
"""
    (ROOT / "flash.html").write_text(
        interior_page(
            "flash.html",
            "Flash — Dylan Prorok, Las Vegas Japanese Tattoo Artist",
            "Browse Dylan Prorok’s pre-drawn flash and inquire about a one-shot tattoo in Las Vegas. Size, placement, and price are confirmed before booking.",
            "CollectionPage",
            images["flash"],
            flash_body,
            origin=origin,
        ),
        encoding="utf-8",
    )

    art_body = f"""  <div class="sec__head">
    <span class="sec__jp" aria-hidden="true">絵画</span>
    <h1 data-split>Art</h1>
    <p>Paintings, murals, and work beyond skin.</p>
  </div>
  <section class="folio-cat" id="art-library" aria-labelledby="art-library-title">
    <div class="folio-cat__head">
      <h2 id="art-library-title">Artwork archive</h2>
      <span aria-hidden="true">画</span>
    </div>
    <div class="art-grid">
    {render_clusters(art, groups, "art-grid", True)}
    </div>
  </section>
"""
    (ROOT / "art.html").write_text(
        interior_page(
            "art.html",
            "Art — Dylan Prorok, Paintings and Murals",
            "Paintings, murals, and work beyond skin by Dylan Prorok.",
            "CollectionPage",
            images["art"],
            art_body,
            origin=origin,
        ),
        encoding="utf-8",
    )

    product_html = []
    by_id = {row["asset_id"]: row for row in assets}
    for product in PRODUCTS:
        figs = []
        for idx, asset_id in enumerate(product["ids"]):
            asset = by_id[asset_id]
            figs.append(figure_markup(asset, eager=(idx == 0)))
        product_html.append(
            f"""  <article class="product">
    <h2>{h(product["title"])}</h2>
    <p class="product__price">{h(product["price"])}</p>
    <p class="product__copy">{h(product["copy"])}</p>
    <div class="product__gallery">
      {chr(10).join(figs)}
    </div>
    <a class="product__go" href="{h(product["url"])}" target="_blank" rel="noopener">View current listing</a>
  </article>"""
        )
    merch_body = f"""  <div class="sec__head">
    <span class="sec__jp" aria-hidden="true">物</span>
    <h1 data-split>Merch</h1>
    <p>A hand-printed Gwap Geisha poster and the Ko Omote T-shirt, available through the current listings.</p>
  </div>
  <div class="product-list">
{chr(10).join(product_html)}
  </div>
"""
    (ROOT / "merch.html").write_text(
        interior_page(
            "merch.html",
            "Merch — Dylan Prorok",
            "Gwap Geisha Print and Ko Omote T-Shirt from Dylan Prorok. A $40 print and a $30 shirt, through the current listings.",
            "WebPage",
            images["merch"],
            merch_body,
            origin=origin,
        ),
        encoding="utf-8",
    )


def write_manifests(assets: list[dict], origin: str) -> None:
    def items_for(category: str, subcategory: str | None = None) -> list[dict]:
        rows = [
            row
            for row in assets
            if row["source_category"] == category
            and (subcategory is None or row["source_subcategory"] == subcategory)
        ]
        rows.sort(key=lambda row: (parse_page_index(row), row["asset_id"]))
        return [
            {
                "asset_id": row["asset_id"],
                "src": row["local_path"],
                "width": row["width"],
                "height": row["height"],
                "alt": row["alt"],
                "caption": row["caption"],
                "duplicate_group": row.get("duplicate_group") or "",
            }
            for row in rows
        ]

    portfolio = {
        "version": 2,
        "note": "Generated from media/local-manifest.json. Do not invent subjects, titles, or availability.",
        "categories": [
            {"id": "irezumi", "label": "Irezumi", "jp": "入れ墨", "items": items_for("tattoo", "irezumi")},
            {"id": "color", "label": "Illustrative Color", "jp": "色彩", "items": items_for("tattoo", "color")},
            {"id": "bng", "label": "Black & Grey", "jp": "墨", "items": items_for("tattoo", "black-and-grey")},
            {"id": "other", "label": "Additional work", "jp": "他", "items": items_for("tattoo", "aggregate-only")},
        ],
    }
    (ROOT / "assets/portfolio-manifest.json").write_text(
        json.dumps(portfolio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ROOT / "assets/flash-manifest.json").write_text(
        json.dumps({"version": 2, "items": items_for("flash")}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (ROOT / "assets/art-manifest.json").write_text(
        json.dumps({"version": 2, "items": items_for("art")}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (ROOT / "assets/merch-manifest.json").write_text(
        json.dumps({"version": 2, "items": items_for("merch")}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    page_locs = [page_url(page, origin) for page in PAGES]
    pages_xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc in page_locs:
        pages_xml.append("  <url>")
        pages_xml.append(f"    <loc>{h(loc)}</loc>")
        pages_xml.append("  </url>")
    pages_xml.append("</urlset>\n")
    (ROOT / "sitemap-pages.xml").write_text("\n".join(pages_xml), encoding="utf-8")

    image_pages = {
        "portfolio.html": [row for row in assets if row["source_category"] == "tattoo"],
        "flash.html": [row for row in assets if row["source_category"] == "flash"],
        "art.html": [row for row in assets if row["source_category"] == "art"],
        "merch.html": [row for row in assets if row["source_category"] == "merch"],
    }
    images_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    for page, rows in image_pages.items():
        images_xml.append("  <url>")
        images_xml.append(f"    <loc>{h(page_url(page, origin))}</loc>")
        for row in rows:
            images_xml.append("    <image:image>")
            images_xml.append(f"      <image:loc>{h(origin + '/' + row['local_path'])}</image:loc>")
            images_xml.append(f"      <image:title>{h(row['caption'])}</image:title>")
            images_xml.append("    </image:image>")
        images_xml.append("  </url>")
    images_xml.append("</urlset>\n")
    (ROOT / "sitemap-images.xml").write_text("\n".join(images_xml), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>{h(origin)}/sitemap-pages.xml</loc>
  </sitemap>
  <sitemap>
    <loc>{h(origin)}/sitemap-images.xml</loc>
  </sitemap>
</sitemapindex>
""",
        encoding="utf-8",
    )
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nDisallow: /\n\nSitemap: {origin}/sitemap.xml\n",
        encoding="utf-8",
    )
    (ROOT / "assets/launch.json").write_text(
        json.dumps(
            {
                "origin": origin,
                "indexable": False,
                "preview_origin": PREVIEW_ORIGIN,
                "production_origin": "https://www.dylanprorok.com",
                "note": "Default rehearsal is the GitHub preview host. configure-launch.py is the only switch.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def pick_image(assets: list[dict], asset_id: str, fallback_src: str, width: int, height: int) -> dict:
    by_id = {row["asset_id"]: row for row in assets}
    row = by_id.get(asset_id)
    if row:
        return {"src": row["local_path"], "width": row["width"], "height": row["height"]}
    return {"src": fallback_src, "width": width, "height": height}


def main() -> int:
    if not LOCAL_MANIFEST.exists():
        print("missing media/local-manifest.json; run import-legacy-assets.py first", file=sys.stderr)
        return 1
    assets, _by_id, groups = load_library()
    origin = PREVIEW_ORIGIN
    images = {
        "index": {"src": "dylan-portrait.jpg", "width": 617, "height": 849},
        "about": {"src": "dylan-portrait.jpg", "width": 617, "height": 849},
        "booking": {"src": "dylan-portrait.jpg", "width": 617, "height": 849},
        "portfolio": pick_image(assets, "TAT-IRE-051", "dylan-portrait.jpg", 617, 849),
        "flash": pick_image(assets, "FLA-001", "dylan-portrait.jpg", 617, 849),
        "art": pick_image(assets, "ART-001", "dylan-portrait.jpg", 617, 849),
        "merch": pick_image(assets, "MER-PRT-001", "dylan-portrait.jpg", 617, 849),
    }
    write_gallery_pages(assets, groups, origin, images)
    write_manifests(assets, origin)
    patch_index(origin, images["index"])
    patch_simple_page(
        "booking.html",
        origin,
        images["booking"],
        extras=[
            (
                "Start a tattoo consultation with Dylan Prorok in Las Vegas. Describe the work, placement, and references, then book a virtual consultation if the form cannot send yet.",
                "Start a tattoo consultation with Dylan Prorok in Las Vegas. Describe the work, placement, and references. The consultation is free and can be done virtually or in person.",
            ),
        ],
    )
    patch_simple_page(
        "about.html",
        origin,
        images["about"],
        extras=[
            (
                '<p class="page__go" style="text-align:left;margin-top:1.8rem"><a href="booking.html">Begin a consultation</a></p>',
                f'<p class="page__go" style="text-align:left;margin-top:1.8rem"><a href="{h(SETMORE_CONSULT_URL)}" target="_blank" rel="noopener">Book a virtual consultation</a></p>',
            )
        ],
    )
    print(f"applied recovered site from {len(assets)} local assets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
