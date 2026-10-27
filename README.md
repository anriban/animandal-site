# animandal.com

The personal academic website of Anirban Mandal. It's a static site: all content lives in plain-text files under `content/`, and `build.py` turns them into HTML in `_site/`. You don't need a CMS, a database or any packages, only Python 3.12+.

```
content/
  site.toml           profile, bio, research interests, education, links, contact
  news.toml           short news items (home page feed + News page)
  publications.toml   every publication
  projects.toml       research projects (Research page)
  awards.toml         funding awards ([[grant]]) and honors ([[honor]])
  service.toml        professional service: advisory roles, organizing, program committees, panels, reviewing
  media.toml          press coverage (News page)
  cv.toml             CV-only content: summary, positions, thesis details, talks, teaching
assets/
  style.css, site.js, favicon.svg
  cv.css              CV layout and typography (page size, fonts, colors)
  images/profile.jpg  ← add your photo here
build.py              builds the website
cv.py                 builds the CV (cv/cv.html and cv/Anirban_Mandal_CV.pdf)
```

## Preview locally

```sh
python3 build.py --serve      # then open http://localhost:8000
```

Run `python3 build.py` again after each edit and refresh the browser. If an entry is missing a required field, the build stops and tells you which file and entry to fix.

## Common edits

**Add a publication:** copy a block in `content/publications.toml` and edit it:

```toml
[[publication]]
year = 2027
title = "My New Paper"
authors = "K. Thareja, A. Mandal, and E. Deelman"
venue = "Proceedings of SC'27, St. Louis, MO, November 2027"
type = "conference"        # journal | conference | workshop | chapter | preprint | report | poster | thesis
url = "https://doi.org/..."
status = "to appear"       # optional; delete the line once it's published
award = "Best Paper Award" # optional
selected = true            # optional; also lists it on the home page
```

Your name is bolded automatically. The name variants are listed in `highlight_author` in `site.toml`.

**Add a news item:** add a block at the top of `content/news.toml`:

```toml
[[item]]
date = "2027-03"
kind = "award"   # paper | grant | award | talk | service | people | media
text = "Our paper on [FABRIC](https://fabric-testbed.net) won **Best Paper** at XYZ '27."
```

**Add a grant or honor:** add a `[[grant]]` or `[[honor]]` block to `content/awards.toml`. NSF award numbers are linked to the NSF award page automatically.

**Add a program committee or review panel:** edit `content/service.toml`. For a new year on an existing committee, update its `years`; for a new panel, add the date to that agency's `dates` list.

**Move a project to "Previous":** in `content/projects.toml`, change `status = "current"` to `status = "previous"`.

**Change the photo:** save a square image as `assets/images/profile.jpg`. Until then the site shows your initials.

Text fields support simple Markdown: `[link](https://...)`, `**bold**`, `*italic*`.

## The CV

The CV is built from the **same content files** as the website, so updating the site also updates the CV. Publications, grants, honors, service, research interests and contact details all come from the shared files. Only the CV-specific parts live in `content/cv.toml`.

```sh
python3 cv.py          # writes cv/cv.html and cv/Anirban_Mandal_CV.pdf
python3 cv.py --html   # HTML only; open cv/cv.html in a browser and print to PDF yourself
```

`cv.py` prints the PDF with Google Chrome in headless mode. If Chrome is installed somewhere unusual, run `CHROME=/path/to/chrome python3 cv.py`. The date in the page footer updates automatically.

### What goes where

| To add or change… | Edit | Shows up in |
|---|---|---|
| A publication, a best paper award on a paper | `publications.toml` | site + CV |
| A new grant (set `role = "PI"` or `"Co-PI"`) | `awards.toml` `[[grant]]` | site + CV |
| A new honor | `awards.toml` `[[honor]]` (or `cv.toml` `[[extra_honor]]` for CV only) | site + CV |
| A program committee, review panel, editorial or advisory role | `service.toml` | site + CV |
| Research interests, education, contact details, profile links | `site.toml` | site + CV |
| A new job title or promotion | `cv.toml` `[[position]]` (and `role` in `site.toml` for the website) | CV (+ site) |
| A talk, keynote, panel or webinar | `cv.toml` `[[talk]]` | CV |
| Students mentored, courses, REU cohorts | `cv.toml` `[[teaching]]` | CV |
| The summary paragraph at the top | `cv.toml` `summary` | CV |

### Keeping it current: a routine

- **When something happens** (a paper accepted, a grant awarded, a new PC invitation), add it to the matching file, then run `python3 build.py && python3 cv.py`.
- **Once a year** (for example, while writing your annual self-evaluation):
  - Re-read the `summary` in `cv.toml`. Update the funding total ("more than $40M") and publication count if they've grown.
  - Change `status = "to appear"` papers to published and add their DOI links.
  - Move finished projects to `status = "previous"` in `projects.toml`.
  - Add the year's NSF/DOE panels to `service.toml` and extend program committee `years`.
  - Add the year's talks to `cv.toml`.
- **When your title changes**, add a new `[[position]]` at the top of `cv.toml`, close the old one's `dates` (e.g. `"2024–2027"`), and update `headline` in `cv.toml` and `role` in `site.toml`.

### Changing the look

`assets/cv.css` controls the layout. Common tweaks:
- Use A4 instead of US Letter: change `size: Letter` to `size: A4`.
- Make it shorter: lower the body `font` size (currently 9.6pt), or remove a section from the list in `render()` in `cv.py`.
- Change the section order: reorder the list in `render()` in `cv.py`.
- Change how publications are grouped: edit `publication_groups` in `cv.toml`.

### Publishing the CV on the website

The website's **CV** button links to this PDF (`cv_url = "cv/Anirban_Mandal_CV.pdf"` in `site.toml`). `build.py` copies every PDF in `cv/` into the site, so there is no copy step.

The GitHub deploy job can't run Chrome, so it publishes the PDF you committed. After changing anything that appears in the CV:

```sh
python3 cv.py
git add cv/Anirban_Mandal_CV.pdf content/ && git commit -m "Update CV" && git push
```

## Publishing

`_site/` is a plain folder of HTML, so any static host will work:

- **GitHub Pages (recommended):** push this folder to a GitHub repository. In *Settings → Pages*, set *Source* to **GitHub Actions**. The included workflow (`.github/workflows/deploy.yml`) rebuilds and publishes the site on every push. You can even edit the `.toml` files directly on github.com.
- **Netlify / Cloudflare Pages:** set the build command to `python3 build.py` and the output directory to `_site`.
- **Any web server:** run `python3 build.py` and upload the contents of `_site/`.

The site is served at `www.animandal.com` from GitHub Pages. The domain is registered at Squarespace, where DNS points `www` (CNAME to `anriban.github.io`) and the bare domain (GitHub Pages' A/AAAA records) at GitHub. The domain itself is set under *Settings → Pages → Custom domain*. To move to another host, change those DNS records. Old Google Sites URLs that have no page of their own (`/home`, `/media`) redirect to their new location via the `REDIRECTS` table in `build.py`; add to it if another old link turns up broken.
