#!/usr/bin/env python3
"""Build the static site from content/*.toml into _site/.

Usage:
    python3 build.py           # build into _site/
    python3 build.py --serve   # build, then preview at http://localhost:8000

Needs only Python 3.12+ (uses the standard-library tomllib). No packages to install.
"""

import datetime as dt
import hashlib
import html
import http.server
import re
import shutil
import socketserver
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
OUT = ROOT / "_site"

PUB_TYPES = {
    "journal": "Journal",
    "conference": "Conference",
    "workshop": "Workshop",
    "chapter": "Book chapter",
    "preprint": "Preprint",
    "report": "Report",
    "poster": "Poster",
    "thesis": "Thesis",
}
NEWS_KINDS = {"paper", "grant", "award", "talk", "service", "people", "media"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

NAV = [
    ("index.html", "Home"),
    ("research.html", "Research"),
    ("publications.html", "Publications"),
    ("awards.html", "Awards"),
    ("service.html", "Service"),
    ("news.html", "News"),
    ("contact.html", "Contact"),
]

# old Google Sites URLs that search engines still link to; each gets a stub page that redirects
REDIRECTS = {
    "home.html": "index.html",
    "media.html": "news.html#media",
}


# ------------------------------------------------------------------ helpers

def load(name):
    path = CONTENT / f"{name}.toml"
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Error in content/{name}.toml: {e}")


def esc(s):
    return html.escape(str(s), quote=True)


def md(text):
    """Escape text, then render [links](url), **bold** and *italic*."""
    s = esc(text)
    s = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{m.group(2)}"{ext(m.group(2))}>{m.group(1)}</a>',
        s,
    )
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def ext(url):
    """Attributes for links that leave the site or open a PDF (such as the CV): both open in a new tab."""
    u = html.unescape(url)
    return ' target="_blank" rel="noopener"' if re.match(r"https?://", u) or u.lower().endswith(".pdf") else ""


def link(url, label, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<a href="{esc(url)}"{c}{ext(url)}>{label}</a>'


def fmt_date(d):
    """'2025-07' or '2025-07-14' -> 'Jul 2025' / 'Jul 14, 2025'."""
    parts = str(d).split("-")
    try:
        y, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return esc(d)
    if len(parts) > 2:
        return f"{MONTHS[m - 1]} {int(parts[2])}, {y}"
    return f"{MONTHS[m - 1]} {y}"


def highlight(authors, names):
    """Bold your name. One left-to-right pass, so in "A. Mandal, A. Dasgupta" only "A. Mandal" matches."""
    pattern = "|".join(re.escape(esc(n)) for n in sorted(names, key=len, reverse=True))
    return re.sub(rf"(?<![\w.])(?:{pattern})(?![\w])",
                  lambda m: f"<strong class='me'>{m.group(0).replace(' ', '&nbsp;')}</strong>", esc(authors))


def require(items, fields, where):
    for i, item in enumerate(items, 1):
        missing = [f for f in fields if not str(item.get(f, "")).strip()]
        if missing:
            title = item.get("title") or item.get("name") or item.get("text", "")[:40]
            sys.exit(f"content/{where}.toml entry #{i} ({title!r}) is missing: {', '.join(missing)}")


# ------------------------------------------------------------------ icons

ICON_PATHS = {
    "email": '<path d="M4 6h16v12H4z"/><path d="m4 7 8 6 8-6"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1"/><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1"/>',
    "doc": '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "ext": '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
}
# Brand marks rendered as short monograms (keeps the site free of third-party logo files)
MONOGRAMS = {
    "scholar": "GS", "orcid": "iD", "dblp": "db", "researchgate": "RG", "linkedin": "in",
    "github": "GH", "x": "X", "mastodon": "M", "bluesky": "bsky", "facebook": "f",
}


def icon(name, cls="icon"):
    if name in MONOGRAMS:
        return f'<span class="mono" aria-hidden="true">{MONOGRAMS[name]}</span>'
    path = ICON_PATHS.get(name, ICON_PATHS["link"])
    return (f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{path}</svg>')


# ------------------------------------------------------------------ layout

def asset_version():
    """Short hash of the CSS and JS, so browsers fetch fresh copies after every change."""
    h = hashlib.sha1()
    for name in ("style.css", "site.js"):
        h.update((ASSETS / name).read_bytes())
    return h.hexdigest()[:10]


def analytics(site):
    """Google Analytics 4 tag, if site.google_analytics is set. Skipped when previewing locally."""
    gid = site["site"].get("google_analytics")
    if not gid:
        return ""
    return f"""<script>if(!/^(localhost|127\\.0\\.0\\.1)$/.test(location.hostname)){{var s=document.createElement("script");s.async=1;s.src="https://www.googletagmanager.com/gtag/js?id={esc(gid)}";document.head.appendChild(s);window.dataLayer=window.dataLayer||[];window.gtag=function(){{dataLayer.push(arguments)}};gtag("js",new Date());gtag("config","{esc(gid)}")}}</script>
"""


def layout(site, page, title, body, description=None):
    s, p = site["site"], site["profile"]
    v = asset_version()
    full_title = s["title"] if page == "index.html" else f"{title} · {s['title']}"
    desc = description or s["description"]
    current = ' aria-current="page"'
    nav = "".join(f'<a href="{href}"{current if href == page else ""}>{label}</a>' for href, label in NAV)
    year = dt.date.today().year
    updated = dt.date.today().strftime("%B %Y")
    canonical = s.get("url", "").rstrip("/") + "/" + ("" if page == "index.html" else page)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&family=Source+Serif+4:opsz,wght@8..60,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css?v={v}">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
{analytics(site)}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="unc-logo" href="https://www.unc.edu/" target="_blank" rel="noopener"><img src="assets/images/unc-logo-white.svg" alt="The University of North Carolina at Chapel Hill" width="116" height="36"></a>
    <a class="brand" href="index.html">{esc(p["name"])}</a>
    <nav class="nav" id="nav" aria-label="Main">{nav}</nav>
    <div class="header-actions">
      <button class="icon-btn" id="theme-toggle" type="button" aria-label="Toggle dark mode">{icon("moon", "icon i-moon")}{icon("sun", "icon i-sun")}</button>
      <button class="icon-btn menu-btn" id="menu-toggle" type="button" aria-label="Menu" aria-expanded="false" aria-controls="nav">{icon("menu")}</button>
    </div>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap footer-inner">
    <a class="renci-logo" href="https://renci.org/" target="_blank" rel="noopener"><img src="assets/images/renci-logo-dark.png" alt="RENCI, Renaissance Computing Institute" width="82" height="40"></a>
    <div class="footer-text">
      <p>© {year} {esc(p["name"])} · {esc(p["organization"])}</p>
      <p class="muted">Last updated {updated}</p>
    </div>
  </div>
</footer>
<script src="assets/site.js?v={v}"></script>
</body>
</html>
"""


def page_head(title, lede=""):
    lede_html = f'<p class="lede">{md(lede)}</p>' if lede else ""
    return f'<section class="page-head"><div class="wrap"><h1>{esc(title)}</h1>{lede_html}</div></section>'


# ------------------------------------------------------------------ components

def profile_links(site, include_cv=True, vertical=False):
    p = site["profile"]
    cls = "side-link" if vertical else "chip"
    out = []
    links = site.get("links", [])
    for l in links:
        if l.get("top"):
            out.append(link(l["url"], f'{icon(l.get("icon", "link"))}<span>{esc(l["label"])}</span>', cls))
    if include_cv and p.get("cv_url"):
        out.append(link(p["cv_url"], f'{icon("doc")}<span>{esc(p.get("cv_label", "CV"))}</span>', cls if vertical else "chip chip-strong"))
    if p.get("email"):
        label = esc(p["email"]) if vertical else "Email"
        out.append(link(f"mailto:{p['email']}", f'{icon("email")}<span>{label}</span>', cls))
    for l in links:
        if not l.get("top"):
            out.append(link(l["url"], f'{icon(l.get("icon", "link"))}<span>{esc(l["label"])}</span>', cls))
    if vertical:
        return f'<ul class="side-links">{"".join(f"<li>{o}</li>" for o in out)}</ul>'
    return f'<div class="chips">{"".join(out)}</div>'


def news_item(n):
    kind = n.get("kind", "")
    badge = f'<span class="tag tag-{esc(kind)}">{esc(kind.capitalize())}</span>' if kind in NEWS_KINDS else ""
    return (f'<li class="news-item"><time datetime="{esc(n["date"])}">{fmt_date(n["date"])}</time>'
            f'<div>{badge}<p>{md(n["text"])}</p></div></li>')


def pub_types(pub):
    """A publication's types; `type` may be a single string or a list (first one is primary)."""
    t = pub.get("type", "conference")
    return [t] if isinstance(t, str) else list(t)


def pub_item(pub, names):
    links = []
    if pub.get("url"):
        links.append(link(pub["url"], "Paper", "pub-link"))
    if pub.get("pdf"):
        links.append(link(pub["pdf"], "PDF", "pub-link"))
    types = pub_types(pub)
    meta = [f'<span class="tag">{esc(PUB_TYPES.get(t, t))}</span>' for t in types]
    if pub.get("status"):
        meta.append(f'<span class="tag tag-status">{esc(pub["status"][:1].upper() + pub["status"][1:])}</span>')
    if pub.get("award"):
        meta.append(f'<span class="tag tag-award">★ {esc(pub["award"])}</span>')
    title = esc(pub["title"])
    if pub.get("url"):
        title = link(pub["url"], title)
    search = " ".join([pub["title"], pub["authors"], pub["venue"], str(pub["year"])]).lower()
    return f"""<li class="pub" data-type="{esc(" ".join(types))}" data-year="{pub['year']}" data-search="{esc(search)}">
  <h3 class="pub-title">{title}</h3>
  <p class="pub-authors">{highlight(pub["authors"], names)}</p>
  <p class="pub-line"><span class="pub-venue">{md(pub["venue"])}</span> <span class="pub-meta">{"".join(meta)}{"".join(links)}</span></p>
</li>"""


def project_card(pr, compact=False):
    links = []
    if pr.get("website"):
        links.append(link(pr["website"], f'Website {icon("ext")}', "text-link"))
    if pr.get("overview") and pr.get("overview") != pr.get("website"):
        links.append(link(pr["overview"], f'Overview {icon("ext")}', "text-link"))
    award = ""
    if pr.get("award"):
        num = esc(pr["award"])
        award = f' · Award {link(pr["award_url"], num) if pr.get("award_url") else num}'
    years = f' · <span class="nowrap">{esc(pr["years"])}</span>' if pr.get("years") else ""
    tags = "" if compact else "".join(f'<span class="tag">{esc(t)}</span>' for t in pr.get("tags", []))
    summary = "" if compact else f'<div class="card-summary clamp"><p>{md(pr["summary"])}</p></div>'
    full = f'<p class="card-sub">{esc(pr["title"])}</p>' if pr.get("title") else ""
    return f"""<article class="card project" id="{esc(slug(pr['name']))}">
  <div class="card-top"><h3>{esc(pr["name"])}</h3><span class="role">{esc(pr["role"])}</span></div>
  {full}
  <p class="card-meta">{esc(pr["funder"])}{award}{years}</p>
  {summary}
  <div class="card-foot"><div class="tags">{tags}</div><div class="card-links">{"".join(links)}</div></div>
</article>"""


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def avatar(site):
    p = site["profile"]
    photo = p.get("photo", "")
    if photo and (ROOT / photo).is_file():
        return f'<img class="avatar" src="{esc(photo)}" alt="Portrait of {esc(p["name"])}" width="400" height="400">'
    initials = "".join(w[0] for w in p["name"].split()[:2]).upper()
    return f'<div class="avatar avatar-initials" aria-hidden="true">{initials}</div>'


# ------------------------------------------------------------------ pages

def service_highlights(service):
    """A few lines for the home page, built from content/service.toml."""
    items = []
    for o in service.get("organizing", [])[:1]:
        items.append(f'<li><strong>{esc(o["role"])}</strong>, {esc(o["event"])} ({esc(o["years"])})</li>')
    for l in service.get("leadership", [])[1:3]:
        items.append(f'<li><strong>{esc(l["role"])}</strong>, {esc(l["org"])}</li>')
    pcs = [p["venue"] for p in service.get("pc", [])][:8]
    if pcs:
        items.append(f'<li><strong>Program committees</strong>: {esc(", ".join(pcs))}, and others</li>')
    panels = [p.get("short", p["agency"]) for p in service.get("panel", [])]
    if panels:
        items.append(f'<li><strong>Proposal review panels</strong>: {esc(", ".join(panels))}</li>')
    return f'<ul class="service-list">{"".join(items)}</ul>'


def build_home(site, pubs, projects, news, awards, service):
    s, p = site["site"], site["profile"]
    bio = "".join(f"<p>{md(par)}</p>" for par in p.get("bio", []))
    interests = "".join(f'<li>{esc(i)}</li>' for i in p.get("interests", []))
    edu = "".join(
        f'<li><strong>{esc(e["degree"])}</strong><span>{link(e["url"], esc(e["school"])) if e.get("url") else esc(e["school"])}, {esc(e["year"])}</span></li>'
        for e in p.get("education", [])
    )
    latest = "".join(news_item(n) for n in news[: s.get("home_news_count", 6)])
    current = [pr for pr in projects if pr.get("status") == "current"][: s.get("home_projects_count", 4)]
    proj = "".join(project_card(pr, compact=True) for pr in current)
    recent = [x for x in pubs if x.get("selected") and not x.get("award")]
    awarded = [x for x in pubs if x.get("award")]
    sel = "".join(pub_item(x, s["highlight_author"]) for x in recent)
    sel_awards = "".join(pub_item(x, s["highlight_author"]) for x in awarded)
    service_html = service_highlights(service)
    stats = [
        (len(pubs), "publications"),
        (len(awards.get("grant", [])), "funded projects"),
        (len(awards.get("honor", [])), "honors & best paper awards"),
    ]
    stats_html = "".join(f'<div class="stat"><span class="stat-n">{n}</span><span class="stat-l">{l}</span></div>' for n, l in stats)
    body = f"""
<section class="intro">
  <div class="wrap intro-grid">
    <aside class="intro-side">
      {avatar(site)}
      {profile_links(site, vertical=True)}
    </aside>
    <div class="intro-main">
      <h1>{esc(p["name"])}{", " + esc(p["honorific"]) if p.get("honorific") else ""}</h1>
      <p class="intro-role">{esc(p["role"])}<br><span>{esc(p["organization"])}</span></p>
      <div class="prose">{bio}</div>
      <div class="stats">{stats_html}</div>
      <div class="intro-facts">
        <div><h2 class="label">Research interests</h2><ul class="pill-list">{interests}</ul></div>
        <div><h2 class="label">Education</h2><ul class="edu">{edu}</ul></div>
      </div>
    </div>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="section-head"><h2 class="section-title">News</h2><a class="more" href="news.html">All news {icon("arrow")}</a></div>
    <ul class="news">{latest}</ul>
  </div>
</section>

<section class="section alt">
  <div class="wrap">
    <div class="section-head"><h2 class="section-title">Current projects</h2><a class="btn btn-small" href="research.html">All {len(projects)} projects {icon("arrow")}</a></div>
    <div class="cards">{proj}</div>
    <p class="cta"><a class="btn" href="research.html">See all {len(projects)} projects, current and past {icon("arrow")}</a></p>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="section-head"><h2 class="section-title">Selected publications</h2><a class="btn btn-small" href="publications.html">All {len(pubs)} publications {icon("arrow")}</a></div>
    <h3 class="subhead">Recent</h3>
    <ol class="pubs">{sel}</ol>
    <h3 class="subhead">Award-winning papers</h3>
    <ol class="pubs">{sel_awards}</ol>
    <p class="cta"><a class="btn" href="publications.html">See all {len(pubs)} publications {icon("arrow")}</a></p>
  </div>
</section>

<section class="section alt">
  <div class="wrap">
    <div class="section-head"><h2 class="section-title">Professional service</h2><a class="btn btn-small" href="service.html">All service {icon("arrow")}</a></div>
    {service_html}
    <p class="cta"><a class="btn" href="service.html">See all service: committees, panels, and reviewing {icon("arrow")}</a></p>
  </div>
</section>
"""
    return layout(site, "index.html", "Home", body)


def build_research(site, projects):
    groups = []
    for status, label in [("current", "Current projects"), ("previous", "Previous projects")]:
        items = [pr for pr in projects if pr.get("status") == status]
        if items:
            cards = "".join(project_card(pr) for pr in items)
            groups.append(f'<section class="section"><div class="wrap"><h2 class="section-title">{label}</h2><div class="cards cards-wide">{cards}</div></div></section>')
    body = page_head("Research", "Cyberinfrastructure research in support of science, spanning distributed systems, networked clouds and testbeds, edge-to-core workflows, performance and anomaly analysis, and CI training.") + "".join(groups)
    return layout(site, "research.html", "Research", body)


def build_publications(site, pubs):
    names = site["site"]["highlight_author"]
    years = sorted({x["year"] for x in pubs}, reverse=True)
    groups = []
    for y in years:
        items = "".join(pub_item(x, names) for x in pubs if x["year"] == y)
        groups.append(f'<section class="pub-year" id="y{y}" data-year-group><h2 class="year-head">{y}</h2><ol class="pubs">{items}</ol></section>')
    present = [t for t in PUB_TYPES if any(t in pub_types(x) for x in pubs)]
    filters = '<button type="button" class="filter is-active" data-filter="all">All</button>' + "".join(
        f'<button type="button" class="filter" data-filter="{t}">{PUB_TYPES[t]}</button>' for t in present
    )
    jump = "".join(f'<a href="#y{y}">{y}</a>' for y in years)
    profiles = "".join(
        link(l["url"], f'{icon(l.get("icon", "link"))}<span>{esc(l["label"])}</span>', "chip")
        for l in site.get("links", []) if l.get("icon") in ("scholar", "orcid", "dblp", "researchgate")
    )
    body = page_head("Publications") + f"""
<section class="section pubs-page">
  <div class="wrap">
    <div class="chips">{profiles}</div>
    <div class="pub-tools" role="search">
      <label class="search">{icon("search")}<span class="sr-only">Search publications</span>
        <input id="pub-search" type="search" placeholder="Search by title, author, venue, or year" autocomplete="off"></label>
      <div class="filters" role="group" aria-label="Filter by type">{filters}</div>
      <p class="pub-count" id="pub-count" aria-live="polite">{len(pubs)} publications</p>
    </div>
    <div class="pub-layout">
      <nav class="year-jump" aria-label="Jump to year">{jump}</nav>
      <div class="pub-groups">{"".join(groups)}<p class="empty" id="pub-empty" hidden>No publications match your search.</p></div>
    </div>
  </div>
</section>"""
    return layout(site, "publications.html", "Publications", body)


def build_awards(site, awards):
    honors = sorted(awards.get("honor", []), key=lambda h: -int(h["year"]))
    honor_html = "".join(
        f"""<li class="honor"><span class="honor-year">{esc(h["year"])}</span><div>
  <h3>{esc(h["title"])}</h3>
  <p class="card-meta">{esc(h["event"])} · {esc(h["date"])}</p>
  {f'<p class="honor-paper">“{link(h["url"], esc(h["paper"])) if h.get("url") else esc(h["paper"])}”</p>' if h.get("paper") else ""}
  <p class="muted small">{highlight(h["recipients"], site["site"]["highlight_author"])}</p>
</div></li>"""
        for h in honors
    )
    grants = awards.get("grant", [])
    for g in grants:
        if not g.get("award_url") and g.get("agency") == "NSF" and re.fullmatch(r"\d{7}", str(g.get("award", ""))):
            g["award_url"] = f"https://www.nsf.gov/awardsearch/show-award/?AWD_ID={g['award']}"
    grant_html = "".join(
        f"""<article class="grant">
  <div class="grant-side"><span class="agency agency-{esc(g["agency"].lower())}">{esc(g["agency"])}</span><span class="amount">{esc(g.get("amount", ""))}</span><span class="period">{esc(g["start"])} – {esc(g["end"])}</span></div>
  <div class="grant-main">
    <h3>{esc(g["title"])}</h3>
    <p class="card-meta">{esc(g.get("program", ""))}{(" · Award " + (link(g["award_url"], esc(g["award"])) if g.get("award_url") else esc(g["award"]))) if g.get("award") else ""}</p>
    <p class="collab">{" · ".join(esc(c) for c in g.get("collaborators", []))}</p>
  </div>
</article>"""
        for g in grants
    )
    body = page_head("Awards") + f"""
<section class="section">
  <div class="wrap">
    <h2 class="section-title">Funding awards</h2>
    <p class="muted small">Amounts are total project budgets across all collaborating institutions.</p>
    <div class="grants">{grant_html}</div>
  </div>
</section>
<section class="section alt">
  <div class="wrap">
    <h2 class="section-title">Honors &amp; best paper awards</h2>
    <ul class="honors">{honor_html}</ul>
  </div>
</section>"""
    return layout(site, "awards.html", "Awards", body)


def build_service(site, a):
    def years(y):
        return f'<span class="act-years">{esc(y)}</span>' if y else ""

    def name(text, url):
        return link(url, esc(text)) if url else esc(text)

    def note(text):
        return f'<p class="act-note">{esc(text)}</p>' if text else ""

    def role_tag(text):
        return f' <span class="tag">{esc(text)}</span>' if text else ""

    lead = "".join(
        f'<li class="act"><div><strong>{esc(l["role"])}</strong>, {name(l["org"], l.get("url"))}{note(l.get("note"))}</div>{years(l.get("years"))}</li>'
        for l in a.get("leadership", [])
    )
    org = "".join(
        f'<li class="act"><div><strong>{esc(o["role"])}</strong>, {name(o["event"], o.get("url"))}</div>{years(o.get("years"))}</li>'
        for o in a.get("organizing", [])
    )
    pc = "".join(
        f'<tr><th scope="row">{esc(p["venue"])}</th><td>{esc(p["full"])}{role_tag(p.get("role"))}</td><td class="yrs">{esc(p["years"])}</td></tr>'
        for p in a.get("pc", [])
    )
    panels = "".join(
        f'<li class="act"><div><strong>{esc(p["agency"])}</strong><p class="act-note">{len(p["dates"])} panel{"s" if len(p["dates"]) != 1 else ""}: {esc(", ".join(p["dates"]))}</p></div></li>'
        for p in a.get("panel", [])
    )
    rev = "".join(f'<li><span>{esc(r["venue"])}</span> <span class="act-years">{esc(r["years"])}</span></li>' for r in a.get("reviewer", []))
    early = a.get("early_reviewing", {}).get("text", "")
    body = page_head("Service", "Leadership, conference organization, program committees, proposal review, and editorial service.") + f"""
<section class="section">
  <div class="wrap grid-2">
    <div>
      <h2 class="section-title">Leadership &amp; advisory roles</h2>
      <ul class="acts">{lead}</ul>
      <h2 class="section-title gap">Proposal review panels</h2>
      <ul class="acts">{panels}</ul>
    </div>
    <div>
      <h2 class="section-title">Conference &amp; workshop organization</h2>
      <ul class="acts">{org}</ul>
    </div>
  </div>
</section>
<section class="section alt">
  <div class="wrap">
    <h2 class="section-title">Program committees</h2>
    <div class="table-wrap"><table class="pc-table"><thead><tr><th scope="col">Venue</th><th scope="col">Full name</th><th scope="col">Years</th></tr></thead><tbody>{pc}</tbody></table></div>
  </div>
</section>
<section class="section">
  <div class="wrap">
    <h2 class="section-title">Journal reviewing</h2>
    <ul class="rev-list">{rev}</ul>
    {f'<p class="muted small">{esc(early)}</p>' if early else ""}
  </div>
</section>"""
    return layout(site, "service.html", "Service", body)


def build_news(site, news, media):
    items = "".join(news_item(n) for n in news)
    press = "".join(
        f"""<li class="press"><time datetime="{esc(m["date"])}">{fmt_date(m["date"])}</time><div>
  <h3>{link(m["url"], esc(m["title"]))}</h3>
  <p class="card-meta">{esc(m["outlet"])}{(" · " + md(m["note"])) if m.get("note") else ""}</p></div></li>"""
        for m in media
    )
    body = page_head("News") + f"""
<section class="section">
  <div class="wrap">
    <h2 class="section-title">Updates</h2>
    <ul class="news">{items}</ul>
  </div>
</section>
<section class="section alt" id="media">
  <div class="wrap">
    <h2 class="section-title">In the media</h2>
    <ul class="press-list">{press}</ul>
  </div>
</section>"""
    return layout(site, "news.html", "News", body)


def build_contact(site):
    c = site["contact"]
    rows = [
        (icon("email"), "Email", link(f"mailto:{c['email']}", esc(c["email"]))),
        (icon("phone"), "Phone", link(f"tel:{re.sub(r'[^0-9+]', '', c['phone'])}", esc(c["phone"]))) if c.get("phone") else None,
        (icon("pin"), "Office", (link(c["map_url"], esc(c["address"])) if c.get("map_url") else esc(c["address"]))),
    ]
    dl = "".join(f'<div class="contact-row">{i}<div><dt>{k}</dt><dd>{v}</dd></div></div>' for i, k, v in filter(None, rows))
    body = page_head("Contact") + f"""
<section class="section">
  <div class="wrap grid-2">
    <dl class="contact">{dl}</dl>
    <div><h2 class="section-title">Elsewhere</h2>{profile_links(site, include_cv=True)}</div>
  </div>
</section>"""
    return layout(site, "contact.html", "Contact", body)


def build_redirect(site, target):
    base = site["site"].get("url", "").rstrip("/")
    canonical = f"{base}/{'' if target == 'index.html' else target.split('#')[0]}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Redirecting…</title>
<link rel="canonical" href="{esc(canonical)}">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={esc(target)}">
</head>
<body><p>This page has moved to <a href="{esc(target)}">{esc(target)}</a>.</p></body>
</html>
"""


def build_404(site):
    body = page_head("Page not found", "The page you were looking for doesn't exist. Try the [home page](index.html).")
    return layout(site, "404.html", "Not found", body)


# ------------------------------------------------------------------ main

def build():
    site = load("site")
    pubs = load("publications").get("publication", [])
    projects = load("projects").get("project", [])
    news = load("news").get("item", [])
    media = load("media").get("item", [])
    awards = load("awards")
    service = load("service")

    require(pubs, ["year", "title", "authors", "venue"], "publications")
    require(projects, ["name", "status", "role", "funder", "summary"], "projects")
    require(news, ["date", "text"], "news")
    require(media, ["date", "title", "outlet", "url"], "media")
    require(awards.get("grant", []), ["title", "agency", "start", "end"], "awards")
    require(awards.get("honor", []), ["year", "title", "event", "date", "recipients"], "awards")
    for pub in pubs:
        for t in pub_types(pub):
            if t not in PUB_TYPES:
                sys.exit(f"Unknown publication type {t!r} for {pub['title']!r}. Use one of: {', '.join(PUB_TYPES)}")

    # stable sorts: newest first, file order kept within equal keys
    pubs.sort(key=lambda x: -int(x["year"]))
    news.sort(key=lambda n: str(n["date"]), reverse=True)
    media.sort(key=lambda m: str(m["date"]), reverse=True)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ASSETS, OUT / "assets", ignore=shutil.ignore_patterns("README*", ".DS_Store"))
    # publish the PDF made by cv.py (it is committed, since the deploy job can't run Chrome)
    for pdf in (ROOT / "cv").glob("*.pdf"):
        (OUT / "cv").mkdir(exist_ok=True)
        shutil.copy2(pdf, OUT / "cv" / pdf.name)

    pages = {
        "index.html": build_home(site, pubs, projects, news, awards, service),
        "research.html": build_research(site, projects),
        "publications.html": build_publications(site, pubs),
        "awards.html": build_awards(site, awards),
        "news.html": build_news(site, news, media),
        "service.html": build_service(site, service),
        "contact.html": build_contact(site),
        "404.html": build_404(site),
    }
    for name, content in pages.items():
        (OUT / name).write_text(content, encoding="utf-8")
    for name, target in REDIRECTS.items():
        (OUT / name).write_text(build_redirect(site, target), encoding="utf-8")

    base = site["site"].get("url", "").rstrip("/")
    urls = "".join(f"<url><loc>{esc(base)}/{'' if n == 'index.html' else n}</loc></url>" for n in pages if n != "404.html")
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', encoding="utf-8")
    (OUT / ".nojekyll").write_text("")

    print(f"Built {len(pages)} pages into {OUT.relative_to(ROOT)}/ — "
          f"{len(pubs)} publications, {len(projects)} projects, {len(news)} news, "
          f"{len(media)} media, {len(awards.get('grant', []))} grants, {len(awards.get('honor', []))} honors")


def serve(port=8000):
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(OUT), **k)
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving at http://localhost:{port}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve()
