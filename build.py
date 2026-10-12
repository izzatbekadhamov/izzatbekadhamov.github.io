#!/usr/bin/env python3
"""Izzatbek shaxsiy sayti uchun statik sayt generatori.

Ishlatish:
    python3 build.py            # ommaviy sayt -> dist/
    python3 build.py --drafts   # qoralamalar bilan preview -> dist-drafts/

Kontent `content/` papkasida, dizayn `assets/` papkasida va shu fayldagi
shablonlarda saqlanadi. Tashqi kutubxonalar talab qilinmaydi (Python 3.8+).
"""

import datetime
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"

DRAFTS = "--drafts" in sys.argv
OUT = ROOT / ("dist-drafts" if DRAFTS else "dist")

MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]
WORDS_PER_MINUTE = 180
CASE_STEPS = [
    ("Vaziyat", "Qanday sharoit va kontekst bo‘lgan"),
    ("Muammo", "Aniq nima ishlamagan"),
    ("Qilingan ishlar", "Qanday qadamlar qo‘yilgan"),
    ("Natija", "Nima o‘zgardi va qanday o‘lchandi"),
    ("Olingan saboq", "Keyingi safar nima boshqacha bo‘ladi"),
]

warnings = []


# ---------------------------------------------------------------- yordamchilar

def esc(value):
    return html.escape(str(value), quote=True)


def load_json(name):
    return json.loads((CONTENT / name).read_text("utf-8"))


def slugify(text):
    text = text.lower()
    text = re.sub(r"[‘’ʻʼ'`]", "", text)
    text = re.sub(r"[^a-z0-9а-яё]+", "-", text)
    return text.strip("-") or "bolim"


def parse_bool(value):
    return str(value).strip().lower() in ("true", "ha", "yes", "1")


def parse_doc(path):
    """Markdown fayl: `---` orasidagi `kalit: qiymat` sozlamalar + matn."""
    text = path.read_text("utf-8").replace("\r\n", "\n")
    meta, body = {}, text
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        for line in front.strip().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, _, value = line.partition(":")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            meta[key.strip()] = value
    meta["slug"] = path.stem
    meta["body"] = body.strip()
    meta["draft"] = parse_bool(meta.get("draft", "false"))
    return meta


def format_date(value):
    try:
        d = datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None, "Sana belgilanmagan"
    return d, f"{d.year}-yil {d.day}-{MONTHS[d.month - 1]}"


def reading_time(text):
    words = len(re.findall(r"\w+", text))
    return f"{max(1, round(words / WORDS_PER_MINUTE))} daqiqa o‘qish"


# ---------------------------------------------------------------- markdown

def inline(text):
    codes = []

    def keep_code(m):
        codes.append("<code>" + esc(m.group(1)) + "</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = esc(text)
    text = re.sub(r"\[\[(.+?)\]\]", r'<mark class="todo">\1</mark>', text)

    def link(m):
        label, url = m.group(1), html.unescape(m.group(2))
        if not re.match(r"^(https?://|mailto:|/|#)", url):
            return label
        attrs = ' rel="noopener"' if url.startswith("http") else ""
        return f'<a href="{esc(url)}"{attrs}>{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def table(rows):
    """`| a | b |` ko‘rinishidagi jadval. Ikkinchi qator `---` / `---:` bo‘lsa, birinchisi sarlavha."""
    def cells(row):
        return [c.strip() for c in row.strip().strip("|").split("|")]

    head, align = None, None
    body_rows = [cells(r) for r in rows]
    if len(body_rows) > 1 and all(re.match(r"^:?-{3,}:?$", c) for c in body_rows[1]):
        head = body_rows[0]
        align = ["num" if c.endswith(":") and not c.startswith(":") else "" for c in body_rows[1]]
        body_rows = body_rows[2:]
    align = align or [""] * len(body_rows[0])

    def cell(tag, text, n):
        cls = f' class="{align[n]}"' if n < len(align) and align[n] else ""
        scope = ' scope="col"' if tag == "th" else ""
        return f"<{tag}{cls}{scope}>{inline(text)}</{tag}>"

    html_rows = []
    if head:
        html_rows.append("<thead><tr>" + "".join(cell("th", c, n) for n, c in enumerate(head)) + "</tr></thead>")
    html_rows.append("<tbody>" + "".join(
        "<tr>" + "".join(cell("td", c, n) for n, c in enumerate(r)) + "</tr>" for r in body_rows
    ) + "</tbody>")
    return ('<div class="table-wrap" role="region" aria-label="Jadval" tabindex="0">'
            f'<table>{"".join(html_rows)}</table></div>')


def markdown(src):
    """Kichik Markdown: sarlavhalar, paragraflar, ro‘yxatlar, jadvallar, iqtibos, chiziq."""
    lines = src.split("\n")
    out, para, headings, used_ids = [], [], [], set()
    i = 0

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        s = lines[i].strip()
        if not s:
            flush()
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            flush()
            level = min(max(len(m.group(1)), 2), 4)
            title = m.group(2).strip()
            hid = base = slugify(title)
            n = 2
            while hid in used_ids:
                hid, n = f"{base}-{n}", n + 1
            used_ids.add(hid)
            if level == 2:
                headings.append((hid, title))
            out.append(f'<h{level} id="{hid}">{inline(title)}</h{level}>')
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,})$", s):
            flush()
            out.append("<hr>")
            i += 1
            continue

        if s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            paras = [p for p in " \n".join(quote).split("\n \n")]
            inner = "".join(
                "<p>" + inline(" ".join(p.split())) + "</p>" for p in paras if p.strip()
            )
            out.append("<blockquote>" + inner + "</blockquote>")
            continue

        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(table(rows))
            continue

        ordered = bool(re.match(r"^\d+[.)]\s+", s))
        if ordered or re.match(r"^[-*]\s+", s):
            flush()
            pattern = r"^\d+[.)]\s+" if ordered else r"^[-*]\s+"
            items = []
            while i < len(lines) and re.match(pattern, lines[i].strip()):
                items.append(re.sub(pattern, "", lines[i].strip()))
                i += 1
                while (i < len(lines) and lines[i].startswith(("  ", "\t"))
                       and lines[i].strip() and not re.match(pattern, lines[i].strip())):
                    items[-1] += " " + lines[i].strip()
                    i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue

        para.append(s)
        i += 1

    flush()
    return "\n".join(out), headings


# ---------------------------------------------------------------- kontent

SITE = load_json("sayt.json")
HOME = load_json("bosh-sahifa.json")
CATEGORIES = load_json("kategoriyalar.json")
CATEGORY_TITLES = {c["slug"]: c["title"] for c in CATEGORIES}
# SITE_URL muhit o‘zgaruvchisi sozlamadagi site_url ni almashtiradi (GitHub Pages yig‘ishida ishlatiladi).
SITE_URL = (os.environ.get("SITE_URL") or SITE.get("site_url", "")).rstrip("/")
# Sayt ichki papkada joylashsa (masalan, user.github.io/meningsaytim.uz), barcha havolalarga shu yo‘l qo‘shiladi.
BASE_PATH = urlparse(SITE_URL).path.rstrip("/")
YEAR = datetime.date.today().year


def visible(items):
    return [x for x in items if DRAFTS or not x.get("draft")]


def check_public(doc, kind):
    if not doc["draft"] and "[[" in doc["body"]:
        warnings.append(f"{kind} '{doc['slug']}' e’lon qilingan, lekin to‘ldirilmagan [[...]] joylari bor.")


def load_cases():
    cases = []
    for path in sorted((CONTENT / "keyslar").glob("*.md")):
        doc = parse_doc(path)
        check_public(doc, "Keys")
        cases.append(doc)
    cases.sort(key=lambda c: (int(c.get("order") or 999), c["title"]))
    return visible(cases)


def load_articles():
    articles = []
    for path in sorted((CONTENT / "maqolalar").glob("*.md")):
        doc = parse_doc(path)
        check_public(doc, "Maqola")
        if doc.get("category") not in CATEGORY_TITLES:
            warnings.append(f"Maqola '{doc['slug']}': noma’lum kategoriya '{doc.get('category')}'.")
        doc["date_obj"], doc["date_text"] = format_date(doc.get("date"))
        if doc["date_obj"] is None and not doc["draft"]:
            warnings.append(f"Maqola '{doc['slug']}': sana YYYY-MM-DD ko‘rinishida yozilmagan.")
        doc["reading"] = reading_time(doc["body"])
        articles.append(doc)
    # Yangi sana avval; bir kunda chiqqanlar `order` bo‘yicha.
    articles.sort(key=lambda a: (-(a["date_obj"] or datetime.date.min).toordinal(),
                                 int(a.get("order") or 999)))
    return visible(articles)


def load_materials():
    materials = []
    for path in sorted((CONTENT / "materiallar").glob("*.md")):
        doc = parse_doc(path)
        check_public(doc, "Material")
        file_name = (doc.get("file") or "").strip()
        file_path = CONTENT / "fayllar" / file_name if file_name else None
        if file_name and not file_path.is_file():
            warnings.append(f"Material '{doc['slug']}': fayl topilmadi ({file_name}).")
            file_path = None
        doc["file_path"] = file_path
        materials.append(doc)
    materials.sort(key=lambda m: (int(m.get("order") or 999), m["title"]))
    return visible(materials)


# ---------------------------------------------------------------- shablonlar

def asset_url(name):
    """Fayl o‘zgarganda brauzer keshi yangilanishi uchun versiya qo‘shadi."""
    digest = hashlib.md5((ASSETS / name).read_bytes()).hexdigest()[:8]
    return f"/assets/{name}?v={digest}"


def absolute(path):
    return SITE_URL + path if SITE_URL else None


def layout(*, title, description, path, body, og_type="website", is_draft=False):
    page_meta = SITE.get("meta", {}).get(path)
    if page_meta:
        full_title = page_meta["title"]
        description = page_meta.get("description") or description
    else:
        full_title = SITE["title"] if path == "/" else f"{title} — {SITE['name']}"
    canonical = absolute(path)
    meta = [
        f'<meta name="description" content="{esc(description)}">',
        f'<meta property="og:title" content="{esc(full_title)}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:site_name" content="{esc(SITE["title"])}">',
        '<meta property="og:locale" content="uz_UZ">',
    ]
    if canonical:
        meta.append(f'<link rel="canonical" href="{esc(canonical)}">')
        meta.append(f'<meta property="og:url" content="{esc(canonical)}">')
    if SITE.get("og_image"):
        image = absolute(SITE["og_image"]) or SITE["og_image"]
        meta.append(f'<meta property="og:image" content="{esc(image)}">')
        meta.append('<meta name="twitter:card" content="summary_large_image">')
    else:
        meta.append('<meta name="twitter:card" content="summary">')
    if DRAFTS or is_draft:
        meta.append('<meta name="robots" content="noindex, nofollow">')
    meta_html = "\n  ".join(meta)

    banner = ""
    if DRAFTS:
        banner = ('<div class="draft-banner" role="note">Qoralama rejimi: bu preview '
                  'e’lon qilinmagan materiallarni ham ko‘rsatadi.</div>')

    return f"""<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(full_title)}</title>
  {meta_html}
  <meta name="theme-color" content="#FAF8F3">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,300;0,6..72,400;0,6..72,500;1,6..72,400&display=swap">
  <link rel="stylesheet" href="{asset_url('style.css')}">
  <script>document.documentElement.classList.add('js')</script>
  <script src="{asset_url('main.js')}" defer></script>
</head>
<body>
  <a class="skip-link" href="#asosiy">Asosiy matnga o‘tish</a>
  {banner}
  {header(path)}
  <main id="asosiy" tabindex="-1">
{body}
  </main>
  {footer(path)}
</body>
</html>
"""


def nav_current(href, path):
    if href == "/":
        return path == "/"
    return path.startswith(href)


def header(path):
    items = []
    for item in SITE["nav"]:
        current = ' aria-current="page"' if nav_current(item["href"], path) else ""
        cls = ' class="nav-cta"' if item.get("cta") else ""
        items.append(f'<li{cls}><a href="{esc(item["href"])}"{current}>{esc(item["label"])}</a></li>')
    return f"""<header class="site-header">
    <div class="wrap header-inner">
      <a class="brand" href="/" aria-label="{esc(SITE['name'])} — bosh sahifa">
        <span class="brand-mark" aria-hidden="true">{esc(SITE['name'][:1])}</span>
        <span class="brand-name">{esc(SITE['name'])}<span class="brand-role"> · {esc(SITE['role'])}</span></span>
      </a>
      <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="sayt-menyu">
        <span class="nav-toggle-icon" aria-hidden="true"></span><span>Menyu</span>
      </button>
      <nav id="sayt-menyu" class="site-nav" aria-label="Asosiy menyu">
        <ul>{''.join(items)}</ul>
      </nav>
    </div>
  </header>"""


def footer(path="/"):
    links = "".join(
        f'<li><a href="{esc(i["href"])}">{esc(i["label"])}</a></li>' for i in SITE["nav"]
    )
    top = ""
    if path not in ("/", "/aloqa/"):
        statement = re.sub(r"\*", "", HOME["hero"]["title"])
        top = f"""<div class="wrap footer-top">
      <p class="footer-statement">{esc(statement)}</p>
      <a class="btn btn-light" href="/aloqa/">Bog‘lanish <span class="arrow" aria-hidden="true">→</span></a>
    </div>"""
    return f"""<footer class="site-footer">
    {top}
    <div class="wrap footer-grid">
      <div class="footer-brand">
        <p class="footer-name"><span class="brand-mark" aria-hidden="true">{esc(SITE['name'][:1])}</span>{esc(SITE['name'])} · {esc(SITE['role'])}</p>
        <p class="footer-tagline">{esc(SITE['tagline'])}</p>
      </div>
      <nav aria-label="Pastki menyu">
        <ul class="footer-links">{links}</ul>
      </nav>
      {contact_list(compact=True)}
    </div>
    <div class="wrap footer-bottom">
      <p>© {YEAR} {esc(SITE['name'])}</p>
      <a href="#asosiy" class="to-top">Yuqoriga <span aria-hidden="true">↑</span></a>
    </div>
  </footer>"""


def contact_list(compact=False):
    """Faqat manzili berilgan aloqalarni ko‘rsatadi; bo‘shlari yashiriladi."""
    rows = []
    for c in SITE["contacts"]:
        url = (c.get("url") or "").strip()
        if not url:
            continue
        label = esc(c["label"])
        shown = esc(c.get("display") or re.sub(r"^(mailto:|https?://(www\.)?)", "", url))
        external = url.startswith("http")
        attrs = ' target="_blank" rel="noopener"' if external else ""
        new_tab = '<span class="visually-hidden"> (yangi oynada ochiladi)</span>' if external else ""
        note = ""
        if c.get("note") and not compact:
            note = f'<span class="contact-note">{esc(c["note"])}</span>'
        rows.append(
            f'<li><a class="contact-row" href="{esc(url)}"{attrs}>'
            f'<span class="contact-label">{label}{note}</span>'
            f'<span class="contact-value">{shown}{new_tab}</span>'
            f'<span class="contact-arrow" aria-hidden="true">↗</span></a></li>'
        )
    if not rows:
        return ""
    cls = "contact-list contact-list--compact" if compact else "contact-list"
    return f'<ul class="{cls}" aria-label="Aloqa manzillari">{"".join(rows)}</ul>'


def portrait(compact=False):
    if SITE.get("portrait"):
        inner = f'<img src="{esc(SITE["portrait"])}" alt="{esc(SITE.get("portrait_alt", ""))}" width="640" height="800" fetchpriority="high">'
    else:
        inner = f'<span class="monogram" aria-hidden="true">{esc(SITE["name"][:1])}</span>'
    cls = "portrait portrait--compact" if compact else "portrait"
    return f"""<figure class="{cls}">
        <div class="portrait-frame">{inner}</div>
        <figcaption><span>{esc(SITE['name'])}</span><span>{esc(SITE['role'])} · {esc(SITE['workplace'])}</span></figcaption>
      </figure>"""


def section_head(num, label, title, intro="", action="", hid=""):
    id_attr = f' id="{hid}"' if hid else ""
    intro_html = f'<p class="section-intro">{esc(intro)}</p>' if intro else ""
    return f"""<div class="section-head rv">
        <p class="section-label"><span class="section-num">{num}</span>{esc(label)}</p>
        <div class="section-heading">
          <h2 class="section-title"{id_attr}>{esc(title)}</h2>
          {intro_html}
          {action}
        </div>
      </div>"""


def draft_badge(item):
    return '<span class="badge">Qoralama</span>' if item.get("draft") else ""


def step_flow():
    steps = "".join(
        f'<li class="rv" style="--d:{n}"><span class="t-num">{n + 1:02d}</span>'
        f'<span class="t-title">{esc(t)}</span><span class="t-text">{esc(hint)}</span></li>'
        for n, (t, hint) in enumerate(CASE_STEPS)
    )
    return f'<ol class="timeline" aria-label="Keys tuzilmasi">{steps}</ol>'


def case_cards(cases, heading="h3"):
    cards = []
    for n, c in enumerate(cases):
        cards.append(f"""<li class="card rv" style="--d:{n}">
          <p class="card-topic">{esc(c.get('topic', ''))}{draft_badge(c)}</p>
          <{heading} class="card-title">{esc(c['title'])}</{heading}>
          <p class="card-text">{esc(c.get('summary', ''))}</p>
          <a class="card-link" href="/keyslar/{c['slug']}/">Batafsil o‘qish<span class="visually-hidden">: {esc(c['title'])}</span> <span class="arrow" aria-hidden="true">→</span></a>
        </li>""")
    return f'<ul class="card-grid" role="list">{"".join(cards)}</ul>'


def cases_empty(heading="h3"):
    return f"""<div class="empty empty--cases rv">
        <div class="empty-copy">
          <p class="empty-kicker"><span class="pulse" aria-hidden="true"></span>Tayyorlanmoqda</p>
          <{heading} class="empty-title">Birinchi keyslar ustida ishlayapman</{heading}>
          <p>Har bir keys real vaziyatga asoslanadi va bir xil tuzilmada yoziladi — o‘quvchi qarorlar qanday qabul qilinganini bosqichma-bosqich ko‘ra oladi.</p>
          <p class="empty-note">Shu mavzular bo‘yicha fikr almashmoqchi bo‘lsangiz, <a href="/aloqa/">bog‘laning</a>.</p>
        </div>
        {step_flow()}
      </div>"""


def post_list(articles, heading="h3"):
    rows = []
    for a in articles:
        cat = a.get("category", "")
        rows.append(f"""<li class="post" data-category="{esc(cat)}">
          <p class="post-meta"><span class="post-cat">{esc(CATEGORY_TITLES.get(cat, ''))}</span><span class="dot" aria-hidden="true">·</span><time datetime="{esc(a.get('date', ''))}">{esc(a['date_text'])}</time><span class="dot" aria-hidden="true">·</span><span>{esc(a['reading'])}</span>{draft_badge(a)}</p>
          <{heading} class="post-title"><a href="/maqolalar/{a['slug']}/">{esc(a['title'])}</a></{heading}>
          <p class="post-summary">{esc(a.get('summary', ''))}</p>
        </li>""")
    return f'<ul class="post-list" role="list">{"".join(rows)}</ul>'


def articles_empty(heading="h3"):
    topics = "".join(
        f'<li class="rv" style="--d:{n}"><span class="toc-num">{n + 1:02d}</span>'
        f'<span class="toc-title">{esc(c["title"])}</span></li>'
        for n, c in enumerate(CATEGORIES)
    )
    return f"""<div class="empty empty--articles">
        <div class="empty-copy rv">
          <p class="empty-kicker"><span class="pulse" aria-hidden="true"></span>Tayyorlanmoqda</p>
          <{heading} class="empty-title">Birinchi maqolalar yozilmoqda</{heading}>
          <p>Amaliyotdan kelib chiqqan qisqa va aniq yozuvlar. Mavzular mundarijasi:</p>
        </div>
        <ol class="toc-list" role="list">{topics}</ol>
      </div>"""


def page_head(eyebrow, title, lead, extra=""):
    eyebrow_html = f'<p class="eyebrow">{eyebrow}</p>' if eyebrow else ""
    return f"""<header class="page-head">
      <div class="wrap page-head-inner">
        {extra}
        {eyebrow_html}
        <h1 class="page-title reveal reveal-2">{esc(title)}</h1>
        <p class="lead reveal reveal-3">{esc(lead)}</p>
      </div>
    </header>"""


# ---------------------------------------------------------------- sahifalar

def hero_visual():
    if SITE.get("portrait"):
        photo = (f'<img src="{esc(SITE["portrait"])}" alt="{esc(SITE.get("portrait_alt", ""))}" '
                 f'width="800" height="1000" fetchpriority="high">')
    else:
        photo = f'<span class="monogram" aria-hidden="true">{esc(SITE["name"][:1])}</span>'
    ring = " · ".join(p["title"].upper() for p in HOME["about"]["pillars"]) + " · "
    return f"""<div class="hero-visual reveal reveal-3">
          <div class="hero-photo">{photo}</div>
          <div class="hero-badge" aria-hidden="true">
            <svg viewBox="0 0 120 120" focusable="false">
              <defs><path id="badge-ring" d="M60,60 m-45,0 a45,45 0 1,1 90,0 a45,45 0 1,1 -90,0"/></defs>
              <text><textPath href="#badge-ring" textLength="280" lengthAdjust="spacing">{esc(ring)}</textPath></text>
            </svg>
            <span class="hero-badge-mark">{esc(SITE['name'][:1])}</span>
          </div>
          <p class="hero-card">
            <span class="hero-card-dot" aria-hidden="true"></span>
            <span><span class="hero-card-label">Hozir</span>{esc(SITE['role'])} · {esc(SITE['workplace'])}</span>
          </p>
        </div>"""


def build_home(cases, articles):
    h = HOME["hero"]
    focus_items = ("".join(f"<li>{esc(x)}</li>" for x in HOME["focus"])
                   + "".join(f'<li class="dup">{esc(x)}</li>' for x in HOME["focus"]))
    areas = "".join(
        f"""<li class="rv" style="--d:{n}">
            <span class="area-num">{n + 1:02d}</span>
            <h3 class="area-title">{esc(a['title'])}</h3>
            <p class="area-text">{esc(a['text'])}</p>
          </li>"""
        for n, a in enumerate(HOME["areas"]["items"])
    )
    ab = HOME["about"]
    about_paragraphs = "".join(
        f'<p class="{"about-lead" if n == 0 else "body-text"}">{esc(p)}</p>'
        for n, p in enumerate(ab["paragraphs"])
    )
    formula_parts = []
    for n, p in enumerate(ab["pillars"]):
        if n:
            formula_parts.append('<li class="formula-op" aria-hidden="true">+</li>')
        formula_parts.append(
            f'<li class="formula-item rv" style="--d:{n}"><span class="formula-num">{n + 1:02d}</span>'
            f'<h3 class="formula-title">{esc(p["title"])}</h3><p>{esc(p["text"])}</p></li>'
        )
    audience = "".join(
        f'<li class="aud-card rv" style="--d:{n}"><span class="aud-num">{n + 1:02d}</span>'
        f'<h3 class="aud-title">{esc(a["title"])}</h3><p>{esc(a["text"])}</p></li>'
        for n, a in enumerate(HOME["audience"]["items"])
    )

    cs = HOME["cases"]
    if cases:
        cases_html = case_cards(cases[:3])
        cases_action = '<a class="text-link" href="/keyslar/">Barcha keyslar <span aria-hidden="true">→</span></a>'
    else:
        cases_html, cases_action = cases_empty(), ""

    ar = HOME["articles"]
    if articles:
        articles_html = post_list(articles[:3])
        articles_action = '<a class="text-link" href="/maqolalar/">Barcha maqolalar <span aria-hidden="true">→</span></a>'
    else:
        articles_html, articles_action = articles_empty(), ""

    ct = HOME["contact"]

    body = f"""
    <section class="hero" aria-labelledby="hero-title">
      <div class="wrap hero-grid">
        <div class="hero-text">
          <p class="eyebrow reveal">{esc(h['eyebrow'])}</p>
          <h1 id="hero-title" class="display reveal reveal-2">{inline(h['title'])}</h1>
          <p class="lead reveal reveal-3">{esc(h['lead'])}</p>
          <div class="actions reveal reveal-4">
            <a class="btn btn-primary" href="{esc(h['primary']['href'])}">{esc(h['primary']['label'])} <span class="arrow" aria-hidden="true">→</span></a>
            <a class="btn btn-secondary" href="{esc(h['secondary']['href'])}">{esc(h['secondary']['label'])}</a>
          </div>
        </div>
        {hero_visual()}
      </div>
    </section>

    <div class="marquee" role="region" aria-label="Faoliyat yo‘nalishlari">
      <div class="marquee-track">
        <ul class="marquee-list">{focus_items}</ul>
        <ul class="marquee-list" aria-hidden="true">{focus_items}</ul>
      </div>
    </div>

    <section class="section" aria-labelledby="yonalishlar">
      <div class="wrap">
        {section_head("01", HOME['areas']['label'], HOME['areas']['title'], hid="yonalishlar")}
        <div class="split-main">
          <ol class="areas" role="list">{areas}</ol>
        </div>
      </div>
    </section>

    <section class="section section--dark" aria-labelledby="men-haqimda">
      <div class="wrap">
        {section_head("02", ab['label'], ab['title'], hid="men-haqimda")}
        <div class="split-main about-intro rv">
          {about_paragraphs}
        </div>
        <ul class="formula" role="list">{''.join(formula_parts)}</ul>
        <div class="split-main">
          <a class="text-link" href="{esc(ab['link']['href'])}">{esc(ab['link']['label'])} <span aria-hidden="true">→</span></a>
        </div>
      </div>
    </section>

    <section class="section section--sand" aria-labelledby="kim-uchun">
      <div class="wrap">
        {section_head("03", HOME['audience']['label'], HOME['audience']['title'], hid="kim-uchun")}
        <div class="split-main">
          <ul class="aud-grid" role="list">{audience}</ul>
        </div>
      </div>
    </section>

    <section class="section" id="keyslar" aria-labelledby="keyslar-title">
      <div class="wrap">
        {section_head("04", cs['label'], cs['title'], cs['intro'], cases_action, hid="keyslar-title")}
        <div class="split-main">{cases_html}</div>
      </div>
    </section>

    <section class="section" aria-labelledby="maqolalar-title">
      <div class="wrap">
        {section_head("05", ar['label'], ar['title'], ar['intro'], articles_action, hid="maqolalar-title")}
        <div class="split-main">{articles_html}</div>
      </div>
    </section>

    <section class="section section--contact" id="aloqa" aria-labelledby="aloqa-title">
      <div class="wrap">
        <div class="contact-panel rv">
          <div class="contact-panel-head">
            <p class="section-label"><span class="section-num">06</span>{esc(ct['label'])}</p>
            <h2 class="contact-panel-title" id="aloqa-title">{esc(ct['title'])}<span class="accent-dot">.</span></h2>
            <p class="contact-panel-text">{esc(ct['text'])}</p>
          </div>
          {contact_list()}
        </div>
      </div>
    </section>
"""
    return layout(title=SITE["title"], description=SITE["description"], path="/", body=body)


def build_about():
    doc = parse_doc(CONTENT / "men-haqimda.md")
    content, _ = markdown(doc["body"])
    focus = [x.strip() for x in doc.get("focus", "").split("·") if x.strip()]
    focus = focus or [a["title"] for a in HOME["areas"]["items"]]
    areas = "".join(f"<li>{esc(x)}</li>" for x in focus)
    if doc.get("button_url"):
        external = doc["button_url"].startswith("http")
        attrs = ' target="_blank" rel="noopener"' if external else ""
        new_tab = '<span class="visually-hidden"> (yangi oynada ochiladi)</span>' if external else ""
        button = (f'<a class="btn btn-primary btn-block" href="{esc(doc["button_url"])}"{attrs}>'
                  f'{esc(doc.get("button_label", "Bog‘lanish"))}{new_tab} <span class="arrow" aria-hidden="true">↗</span></a>')
    else:
        button = '<a class="btn btn-secondary btn-block" href="/aloqa/">Bog‘lanish</a>'
    body = f"""
    {page_head(esc(SITE['name'] + ' · ' + SITE['role']), doc['title'], doc['lead'])}
    <div class="wrap about-layout">
      <div class="prose">{content}</div>
      <aside class="about-aside" aria-label="Qisqacha">
        {portrait(compact=True)}
        <div class="aside-block">
          <p class="aside-title">Ish yo‘nalishlari</p>
          <ul class="aside-list">{areas}</ul>
        </div>
        {button}
      </aside>
    </div>
"""
    return layout(title=doc["title"], description=doc.get("description", SITE["description"]),
                  path="/men-haqimda/", body=body)


def build_cases_index(cases):
    content = case_cards(cases, heading="h2") if cases else cases_empty(heading="h2")
    body = f"""
    {page_head("Keyslar", "Amaliy keyslar", HOME["cases"]["intro"])}
    <div class="wrap page-body">{content}</div>
"""
    return layout(title="Amaliy keyslar",
                  description="Izzatbekning HRD amaliyotidan keyslar: rekruting, onboarding va rahbarlar kompetensiyalari.",
                  path="/keyslar/", body=body)


def build_case(case):
    content, headings = markdown(case["body"])
    toc = ""
    if headings:
        links = "".join(f'<li><a href="#{hid}">{esc(t)}</a></li>' for hid, t in headings)
        toc = f"""<aside class="case-toc" aria-label="Keys tuzilmasi">
        <p class="aside-title">Keys tuzilmasi</p>
        <ol>{links}</ol>
      </aside>"""
    draft_note = ""
    if case["draft"]:
        draft_note = '<p class="draft-note">Bu keys qoralama. U ommaviy saytda ko‘rinmaydi.</p>'
    back = '<a class="back-link" href="/keyslar/"><span aria-hidden="true">←</span> Barcha keyslar</a>'
    body = f"""
    <article>
    {page_head("Keys · " + esc(case.get('topic', '')), case['title'], case.get('summary', ''), back)}
    <div class="wrap case-layout">
      {toc}
      <div class="prose case-body">{draft_note}{content}</div>
    </div>
    <div class="wrap-narrow article-end">
      <a class="text-link" href="/keyslar/"><span aria-hidden="true">←</span> Barcha keyslar</a>
    </div>
    </article>
"""
    return layout(title=case["title"], description=case.get("summary", SITE["description"]),
                  path=f"/keyslar/{case['slug']}/", body=body, og_type="article",
                  is_draft=case["draft"])


def build_articles_index(articles):
    if articles:
        used = {a.get("category") for a in articles}
        chips = ['<button type="button" class="chip" data-value="all" aria-pressed="true">Barchasi</button>']
        chips += [
            f'<button type="button" class="chip" data-value="{esc(c["slug"])}" aria-pressed="false">{esc(c["title"])}</button>'
            for c in CATEGORIES if c["slug"] in used
        ]
        content = f"""<div class="filters" data-filter role="group" aria-label="Mavzu bo‘yicha filtr" hidden>{''.join(chips)}</div>
        <p class="visually-hidden" aria-live="polite" data-filter-status></p>
        {post_list(articles, heading="h2")}
        <p class="filter-empty" data-filter-empty hidden>Bu mavzuda hozircha maqola yo‘q.</p>"""
    else:
        content = articles_empty(heading="h2")
    body = f"""
    {page_head("Maqolalar", "Maqolalar va fikrlar", HOME["articles"]["intro"])}
    <div class="wrap page-body">{content}</div>
"""
    return layout(title="Maqolalar va fikrlar",
                  description="Rekruting, onboarding, rahbarlik va HRning biznesdagi o‘rni haqida maqolalar.",
                  path="/maqolalar/", body=body)


def build_article(article, articles):
    content, _ = markdown(article["body"])
    cat = article.get("category", "")
    cat_title = CATEGORY_TITLES.get(cat, "")
    draft_note = ""
    if article["draft"]:
        draft_note = '<p class="draft-note">Bu maqola qoralama. U ommaviy saytda ko‘rinmaydi.</p>'
    article_cta = ""
    if article.get("cta_url"):
        article_cta = (f'<p class="article-cta"><a class="btn btn-primary" href="{esc(article["cta_url"])}" target="_blank" rel="noopener">'
                       f'{esc(article.get("cta_label", "Batafsil"))}<span class="visually-hidden"> (yangi oynada ochiladi)</span> '
                       '<span class="arrow" aria-hidden="true">↗</span></a></p>')
    others = [a for a in articles if a["slug"] != article["slug"]]
    related = [a for a in others if a.get("category") == cat][:2] or others[:2]
    related_html = ""
    if related:
        related_html = f"""<section class="related" aria-labelledby="yana-oqing">
      <div class="wrap-narrow">
        <h2 id="yana-oqing" class="related-title">Yana o‘qing</h2>
        {post_list(related)}
      </div>
    </section>"""
    body = f"""
    <article class="article">
      <header class="article-head">
        <div class="wrap-narrow">
          <a class="back-link" href="/maqolalar/"><span aria-hidden="true">←</span> Maqolalar</a>
          <p class="eyebrow"><a href="/maqolalar/?mavzu={esc(cat)}">{esc(cat_title)}</a></p>
          <h1 class="article-title">{esc(article['title'])}</h1>
          <p class="lead">{esc(article.get('summary', ''))}</p>
          <p class="article-meta"><time datetime="{esc(article.get('date', ''))}">{esc(article['date_text'])}</time><span class="dot" aria-hidden="true">·</span><span>{esc(article['reading'])}</span></p>
        </div>
      </header>
      <div class="wrap-narrow">
        <div class="prose">{draft_note}{content}</div>
        {article_cta}
        <div class="article-end">
          <p>Fikr yoki savolingiz bo‘lsa, <a href="/aloqa/">bog‘laning</a>.</p>
        </div>
      </div>
    </article>
    {related_html}
"""
    return layout(title=article["title"], description=article.get("summary", SITE["description"]),
                  path=f"/maqolalar/{article['slug']}/", body=body, og_type="article",
                  is_draft=article["draft"])


def material_download(m):
    if not m["file_path"]:
        return ""
    size_kb = max(1, round(m["file_path"].stat().st_size / 1024))
    ext = m["file_path"].suffix.lstrip(".").upper()
    return (f'<a class="btn btn-secondary" href="/fayllar/{esc(m["file_path"].name)}" download>'
            f'Yuklab olish <span class="btn-note">{ext}, {size_kb} KB</span></a>')


def material_meta(m):
    return f"""<dl class="material-meta">
            <div><dt>Kim uchun</dt><dd>{esc(m.get('audience', ''))}</dd></div>
            <div><dt>Qaysi vazifani hal qiladi</dt><dd>{esc(m.get('task', ''))}</dd></div>
          </dl>"""


def build_materials(materials):
    if materials:
        rows = []
        for n, m in enumerate(materials):
            rows.append(f"""<li class="material rv" style="--d:{n}">
          <p class="card-topic">{esc(m.get('type', 'Material'))}{draft_badge(m)}</p>
          <h2 class="material-title">{esc(m['title'])}</h2>
          <p class="card-text">{esc(m.get('summary', ''))}</p>
          {material_meta(m)}
          <div class="material-action">
            <a class="btn btn-primary" href="/materiallar/{m['slug']}/">Materialni o‘qish<span class="visually-hidden">: {esc(m['title'])}</span> <span class="arrow" aria-hidden="true">→</span></a>
            {material_download(m)}
          </div>
        </li>""")
        content = f'<ul class="material-list" role="list">{"".join(rows)}</ul>'
    else:
        content = """<div class="empty">
        <h2 class="empty-title">Materiallar tayyorlanmoqda</h2>
        <p>Bu yerda chek-listlar, intervyu savollari va HR shablonlari joylanadi. Har bir material kim uchun ekani va qaysi vazifani hal qilishi bilan birga beriladi.</p>
        <ul class="topic-list"><li>Chek-listlar</li><li>Intervyu savollari</li><li>HR shablonlari</li></ul>
      </div>"""
    body = f"""
    {page_head("Materiallar", "Foydali materiallar", "Suhbat, onboarding va delegatsiya uchun ishda qo‘llash mumkin bo‘lgan qisqa qo‘llanmalar. Har bir material vazifani aniqroq tashkil qilishga yordam beradi.")}
    <div class="wrap page-body">{content}</div>
"""
    return layout(title="Foydali materiallar",
                  description="HR mutaxassislar va rahbarlar uchun amaliy qo‘llanmalar.",
                  path="/materiallar/", body=body)


def build_material(m, materials):
    content, _ = markdown(m["body"])
    draft_note = ""
    if m["draft"]:
        draft_note = '<p class="draft-note">Bu material qoralama. U ommaviy saytda ko‘rinmaydi.</p>'
    back = '<a class="back-link" href="/materiallar/"><span aria-hidden="true">←</span> Barcha materiallar</a>'
    download = material_download(m)
    others = [x for x in materials if x["slug"] != m["slug"]]
    other_links = "".join(
        f'<li><a href="/materiallar/{x["slug"]}/">{esc(x["title"])}</a></li>' for x in others
    )
    other_html = ""
    if other_links:
        other_html = f"""<div class="aside-block">
          <p class="aside-title">Boshqa materiallar</p>
          <ul class="aside-list aside-links">{other_links}</ul>
        </div>"""
    body = f"""
    <article>
    {page_head("Material · " + esc(m.get('type', '')), m['title'], m.get('summary', ''), back)}
    <div class="wrap about-layout material-layout">
      <div class="prose">{draft_note}{content}</div>
      <aside class="about-aside" aria-label="Material haqida">
        <div class="material-card">
          {material_meta(m)}
          {download}
        </div>
        {other_html}
      </aside>
    </div>
    </article>
"""
    return layout(title=m["title"], description=m.get("summary", SITE["description"]),
                  path=f"/materiallar/{m['slug']}/", body=body, og_type="article",
                  is_draft=m["draft"])


def build_contact():
    ct = HOME["contact"]
    topics = "".join(f"<li>{esc(t)}</li>" for t in ct.get("topics", []))
    body = f"""
    {page_head("Bog‘lanish", ct['title'], ct['text'])}
    <div class="wrap page-body contact-page">
      <div class="contact-panel">
        <div class="contact-panel-head">
          <p class="section-label">Aloqa manzillari</p>
        </div>
        {contact_list()}
      </div>
      <div class="contact-topics">
        <p class="aside-title">Qaysi mavzularda yozish mumkin?</p>
        <ul class="aside-list">{topics}</ul>
      </div>
    </div>
"""
    return layout(title="Bog‘lanish", description=ct["text"], path="/aloqa/", body=body)


def build_404():
    body = f"""
    {page_head("404", "Sahifa topilmadi", "Siz qidirgan sahifa ko‘chirilgan yoki hali yaratilmagan bo‘lishi mumkin.")}
    <div class="wrap page-body">
      <div class="actions">
        <a class="btn btn-primary" href="/">Bosh sahifaga qaytish</a>
        <a class="btn btn-secondary" href="/maqolalar/">Maqolalar</a>
      </div>
    </div>
"""
    return layout(title="Sahifa topilmadi", description="Sahifa topilmadi.", path="/404.html",
                  body=body, is_draft=True)


# ---------------------------------------------------------------- yig‘ish

def with_base_path(text):
    if not BASE_PATH:
        return text
    return re.sub(r'((?:href|src)=")/(?!/)', lambda m: f"{m.group(1)}{BASE_PATH}/", text)


def write(path, text):
    if path.endswith(("/", ".html")):
        text = with_base_path(text)
    target = OUT / path.lstrip("/")
    if path.endswith("/"):
        target = target / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, "utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ASSETS, OUT / "assets")
    for folder in ("rasmlar", "fayllar"):
        if (CONTENT / folder).is_dir():
            shutil.copytree(CONTENT / folder, OUT / folder)

    cases, articles, materials = load_cases(), load_articles(), load_materials()

    write("/", build_home(cases, articles))
    write("/men-haqimda/", build_about())
    write("/keyslar/", build_cases_index(cases))
    for c in cases:
        write(f"/keyslar/{c['slug']}/", build_case(c))
    write("/maqolalar/", build_articles_index(articles))
    for a in articles:
        write(f"/maqolalar/{a['slug']}/", build_article(a, articles))
    write("/materiallar/", build_materials(materials))
    for m in materials:
        write(f"/materiallar/{m['slug']}/", build_material(m, materials))
    write("/aloqa/", build_contact())
    write("/404.html", build_404())

    if DRAFTS:
        write("/robots.txt", "User-agent: *\nDisallow: /\n")
    elif SITE_URL:
        paths = ["/", "/men-haqimda/", "/keyslar/", "/maqolalar/", "/materiallar/", "/aloqa/"]
        paths += [f"/keyslar/{c['slug']}/" for c in cases]
        paths += [f"/maqolalar/{a['slug']}/" for a in articles]
        paths += [f"/materiallar/{m['slug']}/" for m in materials]
        urls = "".join(f"<url><loc>{esc(SITE_URL + p)}</loc></url>" for p in paths)
        write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
              f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
        write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    else:
        write("/robots.txt", "User-agent: *\nAllow: /\n")

    mode = "qoralamalar bilan" if DRAFTS else "ommaviy"
    print(f"Tayyor ({mode}): {OUT.relative_to(ROOT)}/ — "
          f"{len(cases)} keys, {len(articles)} maqola, {len(materials)} material.")
    for w in warnings:
        print("Ogohlantirish:", w)


if __name__ == "__main__":
    main()
