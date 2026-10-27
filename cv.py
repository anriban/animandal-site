#!/usr/bin/env python3
"""Build the CV (HTML + PDF) from the same content/*.toml files as the website.

Usage:
    python3 cv.py            # writes cv/cv.html and cv/<filename>.pdf
    python3 cv.py --html     # HTML only (no Chrome needed), e.g. to preview in a browser

The PDF is printed with Google Chrome (or Chromium) in headless mode. Set CHROME=/path/to/chrome
if it is installed somewhere unusual. Then run `python3 build.py` to publish the PDF with the site.
"""

import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

from build import PUB_TYPES, esc, pub_types, highlight, link, load, md, require

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "cv"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]
PUB_PREFIX = {"journal": "J", "conference": "C", "workshop": "W", "chapter": "B",
              "report": "R", "preprint": "R", "poster": "R", "thesis": "R"}
TALK_KINDS = {"invited": "Invited talk", "panel": "Panel", "presentation": "Presentation",
              "poster": "Poster", "tutorial": "Tutorial", "webinar": "Webinar"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month(d):
    y, m = str(d).split("-")[:2]
    return f"{MONTHS[int(m) - 1]} {y}"


def section(title, body, cls=""):
    return f'<section class="cv-section {cls}"><h2>{esc(title)}</h2>{body}</section>'


def entry(main, side="", sub="", extra=""):
    side_html = f'<div class="when">{side}</div>' if side else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f'<div class="entry"><div class="what"><div class="main">{main}</div>{sub_html}{extra}</div>{side_html}</div>'


# ------------------------------------------------------------------ sections

def header(site, cv):
    p, c = site["profile"], site["contact"]
    links = {l.get("icon"): l for l in site.get("links", [])}
    items = [link(f"mailto:{c['email']}", esc(c["email"]))]
    if c.get("phone"):
        items.append(esc(c["phone"]))
    url = site["site"].get("url", "")
    if url:
        items.append(link(url, esc(url.replace("https://", "").replace("http://", ""))))
    if "orcid" in links:
        items.append(link(links["orcid"]["url"], "ORCID " + esc(links["orcid"]["url"].rsplit("/", 1)[-1])))
    if "scholar" in links:
        items.append(link(links["scholar"]["url"], "Google Scholar"))
    return f"""<header class="cv-header">
  <h1>{esc(p["name"])}<span>, {esc(p.get("honorific", ""))}</span></h1>
  <p class="headline">{esc(cv["headline"])}</p>
  <p class="contact">{esc(c["address"])}</p>
  <p class="contact">{" <span class=dot>·</span> ".join(items)}</p>
</header>"""


def profile(site, cv, pubs, grants, honors):
    stats = (f'<p class="stats"><strong>{len(pubs)}</strong> publications <span class="dot">·</span> '
             f'<strong>{len(grants)}</strong> NSF and DOE research grants <span class="dot">·</span> '
             f'<strong>{len(honors)}</strong> honors and awards</p>')
    interests = ", ".join(esc(i) for i in site["profile"].get("interests", []))
    body = f'<p class="summary">{md(cv["summary"])}</p>{stats}<p class="interests"><span class="label">Research interests:</span> {interests}.</p>'
    return section("Profile", body, "profile")


def experience(cv):
    out = []
    for pos in cv.get("position", []):
        bullets = "".join(f"<li>{md(b)}</li>" for b in pos.get("bullets", []))
        extra = f'<ul class="bullets">{bullets}</ul>' if bullets else ""
        sub = esc(pos["org"]) + (f' <span class="note">{esc(pos["note"])}</span>' if pos.get("note") else "")
        out.append(entry(f'<strong>{esc(pos["title"])}</strong>', esc(pos["dates"]), sub, extra))
    return section("Professional Experience", "".join(out))


def education(cv):
    out = []
    for e in cv.get("education", []):
        details = []
        if e.get("thesis"):
            details.append(f'Thesis: <em>{esc(e["thesis"])}</em>')
        if e.get("advisor"):
            details.append(f'Advisor: {esc(e["advisor"])}')
        out.append(entry(f'<strong>{esc(e["degree"])}</strong>, {esc(e["school"])}', esc(e["year"]), " · ".join(details)))
    return section("Education", "".join(out))


def honors_section(awards, cv, names):
    items = []
    for h in awards.get("honor", []):
        items.append((int(h["year"]), h["title"], h["event"], h.get("paper", "")))
    for h in cv.get("extra_honor", []):
        items.append((int(h["year"]), h["title"], h["event"], h.get("paper", "")))
    items.sort(key=lambda x: -x[0])
    rows = "".join(
        entry(f'<strong>{esc(t)}</strong>, {esc(ev)}', str(y), f'<em>“{esc(paper)}”</em>' if paper else "")
        for y, t, ev, paper in items
    )
    return section("Honors and Awards", rows), items


def funding(awards):
    out = []
    for g in awards.get("grant", []):
        meta = [f'{esc(g["agency"])} {esc(g.get("program", ""))}'.strip()]
        if g.get("award"):
            meta.append(f'Award {esc(g["award"])}')
        if g.get("amount"):
            meta.append(f'{esc(g["amount"])} total')
        role = f'<span class="role">{esc(g["role"])}</span> ' if g.get("role") else ""
        collab = f'<div class="small">Partners: {esc(", ".join(g.get("collaborators", [])))}</div>' if g.get("collaborators") else ""
        out.append(entry(f'{role}<strong>{esc(g["title"])}</strong>', f'{esc(g["start"])} – {esc(g["end"])}', " · ".join(meta), collab))
    note = '<p class="note-line">Amounts are total award budgets across all collaborating institutions.</p>'
    return section("Research Funding", note + "".join(out))


def publications(cv, pubs, names):
    groups = []
    for grp in cv.get("publication_groups", []):
        items = [x for x in pubs if pub_types(x)[0] in grp["types"]]
        if not items:
            continue
        prefix = PUB_PREFIX.get(grp["types"][0], "P")
        lis = []
        for i, x in enumerate(items):
            label = f"{prefix}{len(items) - i}"
            title = esc(x["title"])
            if x.get("url"):
                title = link(x["url"], title)
            flags = []
            if x.get("status"):
                flags.append(f'<span class="flag">{esc(x["status"])}</span>')
            if x.get("award"):
                flags.append(f'<span class="flag award">★ {esc(x["award"])}</span>')
            typ = "" if len(grp["types"]) == 1 else f' <span class="kind">[{esc(PUB_TYPES.get(pub_types(x)[0], ""))}]</span>'
            authors = highlight(x["authors"].rstrip(". "), names)
            lis.append(f'<li><span class="num">{label}</span><div>{authors}. '
                       f'“{title}.” <em>{md(x["venue"])}</em>.{typ} {"".join(flags)}</div></li>')
        groups.append(f'<h3>{esc(grp["title"])} <span class="count">({len(items)})</span></h3><ol class="pubs">{"".join(lis)}</ol>')
    lead = '<p class="note-line">Reverse chronological within each category. Names in bold are mine.</p>'
    return section("Publications", lead + "".join(groups), "pubs-section")


def talks(cv):
    lis = "".join(
        f'<li><span class="num">{esc(month(t["date"]))}</span><div>“{esc(t["title"])}.” {esc(t["event"])}. '
        f'<span class="kind">{esc(TALK_KINDS.get(t.get("kind", ""), ""))}</span></div></li>'
        for t in cv.get("talk", [])
    )
    return section("Talks and Presentations", f'<ol class="talks">{lis}</ol>')


def service(svc):
    lead = "".join(
        entry(f'<strong>{esc(l["role"])}</strong>, {esc(l["org"])}', esc(l.get("years", "")))
        for l in svc.get("leadership", [])
    )
    org = "".join(
        entry(f'<strong>{esc(o["role"])}</strong>, {esc(o["event"])}', esc(o.get("years", "")))
        for o in svc.get("organizing", [])
    )
    pcs = "".join(
        f'<li><strong>{esc(p["venue"])}</strong>{(" (" + esc(p["role"]) + ")") if p.get("role") else ""}: {esc(p["years"])}</li>'
        for p in svc.get("pc", [])
    )
    panels = "".join(
        f'<li><strong>{esc(p["agency"])}</strong>: {esc(", ".join(p["dates"]))}</li>' for p in svc.get("panel", [])
    )
    rev = "; ".join(f'{esc(r["venue"])} ({esc(r["years"])})' for r in svc.get("reviewer", []))
    early = svc.get("early_reviewing", {}).get("text", "")
    body = (f'<h3>Leadership and Advisory Roles</h3>{lead}'
            f'<h3>Conference and Workshop Organization</h3>{org}'
            f'<h3>Program Committees</h3><ul class="cols">{pcs}</ul>'
            f'<h3>Proposal Review Panels</h3><ul class="plain">{panels}</ul>'
            f'<h3>Journal Reviewing</h3><p class="small">{rev}.</p>'
            + (f'<p class="small">{esc(early)}</p>' if early else ""))
    return section("Professional Service", body)


def teaching(cv):
    out = "".join(
        entry(f'<strong>{esc(t["role"])}</strong>', esc(t["dates"]), esc(t["org"]),
              f'<div class="small">{esc(t["note"])}</div>' if t.get("note") else "")
        for t in cv.get("teaching", [])
    )
    return section("Mentoring and Teaching", out)


# ------------------------------------------------------------------ document

def render():
    site = load("site")
    cv = load("cv")
    pubs = load("publications").get("publication", [])
    awards = load("awards")
    svc = load("service")
    require(cv.get("position", []), ["title", "org", "dates"], "cv")
    require(cv.get("talk", []), ["date", "title", "event"], "cv")
    pubs.sort(key=lambda x: -int(x["year"]))
    names = site["site"]["highlight_author"]
    honors_html, honors = honors_section(awards, cv, names)
    updated = dt.date.today().strftime("%B %Y")
    name = site["profile"]["name"]
    body = "".join([
        header(site, cv["cv"]),
        profile(site, cv["cv"], pubs, awards.get("grant", []), honors),
        experience(cv),
        education(cv),
        honors_html,
        funding(awards),
        publications(cv["cv"], pubs, names),
        talks(cv),
        service(svc),
        teaching(cv),
    ])
    css = (ROOT / "assets" / "cv.css").read_text(encoding="utf-8")
    css = css.replace("__FOOTER__", f"{name} · Curriculum Vitae · {updated}")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{esc(name)} – Curriculum Vitae</title>
<meta name="author" content="{esc(name)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&family=Source+Serif+4:opsz,wght@8..60,600&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body>{body}</body></html>
"""


def find_chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for c in CHROME_CANDIDATES:
        if os.path.isfile(c) or shutil.which(c):
            return c
    return None


def main():
    OUT.mkdir(exist_ok=True)
    html_path = OUT / "cv.html"
    html_path.write_text(render(), encoding="utf-8")
    print(f"Wrote {html_path.relative_to(ROOT)}")
    if "--html" in sys.argv:
        return
    chrome = find_chrome()
    if not chrome:
        sys.exit("Chrome/Chromium not found. Install it or set CHROME=/path/to/chrome (or use --html and print from a browser).")
    pdf_path = OUT / load("cv")["cv"].get("filename", "CV.pdf")
    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=10000",
         f"--print-to-pdf={pdf_path}", html_path.as_uri()],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"Wrote {pdf_path.relative_to(ROOT)} ({pdf_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
