# SimonResearchRSS

A personalised academic paper feed that runs daily via GitHub Actions, scores incoming papers against your Paperpile library + a hand-tuned keyword profile, and publishes a static dashboard to GitHub Pages. Zero API cost — all scoring runs on CPU with local sentence embeddings.

## How it works

1. **Reference index** — `data/library.json` (your Paperpile export, 991 papers, 898 with abstracts) is encoded once with `sentence-transformers/all-MiniLM-L6-v2` and cached to `data/reference.npz`.
2. **Fetch** — daily, pull RSS feeds listed in `config.yaml` (Nature/Cell family journals + bioRxiv subject feeds).
3. **Dedupe** — drop any paper already in your library (matched by DOI, arXiv ID, or normalised title).
4. **Score** — for each candidate paper:
   - `embedding_score` = max cosine similarity to any paper in your library, mapped to 0–100
   - `keyword_score`  = weighted substring match against Tier1 (30 pts) / Tier2 (15) / Tier3 (7) keywords, capped at 100
   - `final_score`    = 0.7 × embedding_score + 0.3 × keyword_score
   - Tier: high (≥60), medium (≥30), low (<30)
5. **Render** — write `docs/papers.json` and a self-contained `docs/index.html` with tier filter + text search.
6. **Deploy** — commit changes to main and publish `docs/` via GitHub Pages.

## Setup

1. **Push this repo to GitHub** (private is fine for Pages too, if you have Pro).
2. **Enable Pages**: Settings → Pages → Source: **GitHub Actions**.
3. **Trigger manually**: Actions → *Update Research Feed* → Run workflow.
4. Dashboard appears at `https://<username>.github.io/<repo-name>/`.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Build the reference index (one-time, or whenever library.json changes)
python src/build_reference.py

# Pull feeds, score, render
python src/fetch_and_score.py
python src/generate_dashboard.py

# Preview the dashboard
open docs/index.html
```

First run downloads the ~90 MB sentence-transformers model into `~/.cache/huggingface`. Subsequent runs reuse it.

## Customising

- **Research profile keywords** — edit `config.yaml` → `research_profile` → `tier1_keywords` / `tier2_keywords` / `tier3_keywords`.
- **Feeds** — edit `config.yaml` → `feeds` (list of `{name, url}` objects). See note on URL verification below.
- **Scoring thresholds** — edit `config.yaml` → `scoring`:
  - `nn_sim_low` / `nn_sim_high`: cosine range that maps to 0–100. Raise the floor if irrelevant papers score too high.
  - `weights.nn` / `weights.keyword`: blend between semantic similarity and keyword matching.
  - `tiers.high` / `tiers.medium`: tier cutoffs.
- **Lookback window** — `config.yaml` → `fetch.lookback_days` (default 14).

## Refreshing your Paperpile library

1. Re-export your library from Paperpile as JSON.
2. Replace `data/library.json` with the new file.
3. Commit and push. The next workflow run will detect the hash change and rebuild `data/reference.npz`.

## Files

| Path | Purpose |
|---|---|
| `config.yaml` | Feeds, keyword tiers, scoring parameters |
| `data/library.json` | Paperpile export (source of truth for your interests) |
| `data/reference.npz` | Cached library embeddings (auto-rebuilt on library change) |
| `data/reference_meta.json` | DOIs/titles/labels for dedupe + cache sentinel |
| `src/build_reference.py` | Encodes library → reference index |
| `src/fetch_and_score.py` | Daily pipeline: fetch → dedupe → score |
| `src/generate_dashboard.py` | Renders `docs/papers.json` → `docs/index.html` |
| `src/templates/dashboard.html.j2` | Jinja2 HTML template |
| `docs/` | GitHub Pages root (`papers.json` + `index.html`) |
| `.github/workflows/update-feed.yml` | Daily cron + Pages deploy |

## Notes

- RSS URLs for Nature and Cell journals change periodically. If a feed starts returning 0 entries, verify its URL at the publisher's site. `fetch_and_score.py` logs each feed's entry count on every run.
- The first real run is a good time to tune `nn_sim_low` / `nn_sim_high` — check the tier distribution in `docs/papers.json` and adjust if the "must-read" tier is empty or over-stuffed.
- Ideas for future iterations are in `SUMMARY.md` → "Possible extensions" (Slack webhook, read/unread tracking, LLM digest).
