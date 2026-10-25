# Anirban Mandal's academic website and CV

Static site generator (stdlib Python 3.12+, no dependencies) plus a CV generator that share the same content files.
`README.md` has the full editing guide, including a "what goes where" table for every kind of update.

- Source repo: https://github.com/anriban/animandal-site (deployed to GitHub Pages by `.github/workflows/deploy.yml` on every push to `main`)
- Live preview: https://anriban.github.io/animandal-site/
- `www.animandal.com` still points to the old Google Sites site (domain at Squarespace). Do not add a `CNAME` file or a custom domain unless asked; switching the domain is a separate, deliberate step.

## Commands

```sh
python3 build.py           # builds _site/ (also copies cv/*.pdf into _site/cv/)
python3 build.py --serve   # build and serve at http://localhost:8000
python3 cv.py              # writes cv/cv.html and cv/Anirban_Mandal_CV.pdf (headless Chrome)
```

## Where content lives

All content is in `content/*.toml`; the field reference is in the comment header of each file.

| Update | File |
| --- | --- |
| Publication | `publications.toml` (`selected = true` to feature it on the home page) |
| Grant / honor | `awards.toml` (`[[grant]]` with `role`, `[[honor]]`) |
| Project | `projects.toml` |
| News item / press coverage | `news.toml` / `media.toml` |
| Committees, panels, reviewing | `service.toml` |
| Bio, interests, education, links, contact | `site.toml` |
| Positions, talks, teaching, CV summary | `cv.toml` (CV only) |

## Rules for every update

1. Edit the content file(s), matching the existing style of neighboring entries (author format "A. Mandal", venue with place and month, `type` from the allowed list).
2. Always run both `python3 build.py` and `python3 cv.py`, even if the change seems site-only. Most content appears in both, and the deploy job cannot regenerate the PDF, so the committed `cv/Anirban_Mandal_CV.pdf` must be current.
3. Check the result: the build summary counts, the changed entry in `_site/`, and the PDF page count.
4. When a change makes a related item stale, mention it (for example a new paper may warrant a news item; a new grant changes the funding total in `cv.toml`'s `summary`).
5. Git: commit content changes together with the regenerated PDF in one commit. Ask before pushing, because a push publishes the site. `_site/` and `cv/cv.html` are gitignored.
