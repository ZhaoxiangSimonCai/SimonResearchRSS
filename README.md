# SimonResearchRSS

A personalised academic paper feed that runs weekly via GitHub Actions, scores incoming papers against your Paperpile library + a hand-tuned keyword profile (+ optional LLM rerank against a private knowledgebase), and publishes a static dashboard to GitHub Pages. The dashboard is mobile-friendly, supports manual light/dark theming, and tracks read/unread state locally in your browser.

## How it works

1. **Reference index** — `data/library.json` (your Paperpile export) is encoded once with `sentence-transformers/all-MiniLM-L6-v2` and cached to `data/reference.npz`. The "added to Paperpile" timestamp is captured for recency weighting.
2. **Fetch** — weekly, pull RSS/Atom feeds listed in `config.yaml` (Nature/Cell family journals + bioRxiv subject feeds + arXiv category queries).
3. **Dedupe** — drop any paper already in your library (matched by DOI, arXiv ID, or normalised title).
4. **Stage 1 score** — for each candidate paper:
   - `embedding_score` = **recency-weighted** max cosine similarity to your library, mapped to 0–100. Each library paper's contribution is multiplied by `max(0.5 ** (years_since_added / half_life), floor)`, so recent additions count more than old ones.
   - `keyword_score`  = weighted substring match against Tier1 (30 pts) / Tier2 (15) / Tier3 (7) keywords, capped at 100
   - `final_score`    = 0.7 × embedding_score + 0.3 × keyword_score
5. **(Optional) LLM rerank** — when enabled, every stage-1-scored paper is re-scored by the Anthropic API against your research profile / knowledgebase and blended back into `final_score`. Cached by paper ID + model + KB hash so only genuinely new papers cost API calls. See "Optional: LLM second-stage scoring" below.
6. **Source weighting** — each paper's final score is multiplied by its feed's `weight` (default 1.0). bioRxiv uses 0.76 and arXiv uses 0.65–0.72, so preprints need a higher raw score to reach must-read tier. This surfaces the transferable gems from the preprint firehose without drowning the top tier.
7. **Rank-based tiers** — papers are sorted by final score and the top N per tier are kept, subject to a minimum-score floor per tier (see "Tier shape" in Customising below). Everything that doesn't fit any tier is **dropped from the output entirely** — the published `docs/papers.json` only contains the curated ~90 papers per run.
8. **Render** — write `docs/papers.json` and a self-contained `docs/index.html`.
9. **Deploy** — commit changes to main and publish `docs/` via GitHub Pages.

### Dashboard features

- **Tier filter**: button row on desktop, native dropdown on mobile. Shows live unread counts per tier.
- **Text search**: client-side fuzzy search over title, abstract, authors, and journal.
- **Read/unread tracking**: mark papers read (✓ button on each card), optionally hide read papers. State persists in `localStorage` and survives weekly updates because paper IDs are stable.
- **Light/dark theme toggle**: ☀/☾ button in the header, preference persisted in `localStorage`. Falls back to your OS theme if you haven't set a manual override.
- **Source-type colour coding**: each card has a coloured left border + icon pill — blue book for peer-reviewed journals, green DNA for bioRxiv, amber lightning for arXiv — for fast visual scanning.
- **Collapsible description**: on narrow viewports the "About this feed" blurb collapses into a toggle so the sticky header stays compact.

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

All knobs live in `config.yaml`:

- **Research profile keywords** — `research_profile.tier1_keywords` (30 pts each), `tier2_keywords` (15 pts), `tier3_keywords` (7 pts). Used for the keyword score component. These are unioned with the `## Keywords for Paper Matching` section of `data/knowledgebase.md` if present.
- **Scoring** — `scoring`:
  - `nn_sim_low` / `nn_sim_high`: weighted-cosine range that maps to 0–100. Raise the floor if irrelevant papers score too high.
  - `weights.nn` / `weights.keyword`: blend between semantic similarity and keyword matching (default 0.7 / 0.3).
- **Tier shape (rank-based caps + score floors)** — `scoring.tiers` controls how many papers end up in the dashboard and how they're distributed. Each tier has a `max_count` (cap) and a `min_score` (floor). A paper is greedy-assigned to the highest tier where (a) there's still room under `max_count` and (b) its `final_score >= min_score`. Papers that don't fit any tier are **dropped from the output entirely**.
  ```yaml
  scoring:
    tiers:
      high:   {max_count: 10, min_score: 40}   # must-read
      medium: {max_count: 30, min_score: 30}   # worth scanning
      low:    {max_count: 50, min_score: 22}   # on the radar
  ```
  - **To shrink/grow the dashboard**: adjust `max_count` on each tier. Defaults give a curated ~90 papers per week.
  - **To protect against weak weeks**: raise `min_score` on any tier. For example, `high.min_score: 55` means the must-read tier can be empty in a slow week rather than promoting mediocre papers just to fill the 10 slots.
  - **To loosen for high-intake weeks**: lower the floors. They're safety nets; caps are the primary control.
- **Recency weighting** — `scoring.recency_half_life_years` (default 5) and `scoring.recency_floor` (default 0.2). Library papers added more recently count more; older ones decay exponentially with this half-life and never fall below the floor.
- **Lookback window** — `fetch.lookback_days` (default 10 for weekly cadence).

### Managing feeds

Feeds live in `config.yaml` → `feeds:` block. Each entry is one line with optional fields for source weighting:

```yaml
feeds:
  - {name: Nature, url: "https://www.nature.com/nature.rss"}
  - {name: arXiv cs.LG, url: "...", weight: 0.75, max_papers: 40}
```

| Field | Purpose |
|---|---|
| `name` | Display label on the dashboard |
| `url` | RSS/Atom URL |
| `weight` (optional, default `1.0`) | Multiplier applied to the paper's final score before tier assignment. Lower values demote noisy sources so they need a higher raw score to reach must-read. |
| `max_papers` (optional, default `fetch.max_papers_per_feed`) | Per-feed entry cap. Useful for high-volume feeds like arXiv. |

To **add a feed**: append a new line. The pipeline picks up changes on the next workflow run — no code changes needed.

**Currently fetching 18 feeds**:

| # | Feed | URL | Weight | Cap |
|---|---|---|---|---|
| 1 | Nature | `https://www.nature.com/nature.rss` | 1.0 | 100 |
| 2 | Nature Methods | `https://www.nature.com/nmeth.rss` | 1.0 | 100 |
| 3 | Nature Biotechnology | `https://www.nature.com/nbt.rss` | 1.0 | 100 |
| 4 | Nature Medicine | `https://www.nature.com/nm.rss` | 1.0 | 100 |
| 5 | Nature Communications | `https://www.nature.com/ncomms.rss` | 1.0 | 100 |
| 6 | Nature Machine Intelligence | `https://www.nature.com/natmachintell.rss` | 1.0 | 100 |
| 7 | Nature Cancer | `https://www.nature.com/natcancer.rss` | 1.0 | 100 |
| 8 | Nature Reviews Cancer | `https://www.nature.com/nrc.rss` | 1.0 | 100 |
| 9 | Cell | `https://www.cell.com/cell/inpress.rss` | 1.0 | 100 |
| 10 | Cancer Cell | `https://www.cell.com/cancer-cell/inpress.rss` | 1.0 | 100 |
| 11 | Molecular Cell | `https://www.cell.com/molecular-cell/inpress.rss` | 1.0 | 100 |
| 12 | bioRxiv Cancer Biology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=cancer_biology` | **0.76** | 100 |
| 13 | bioRxiv Bioinformatics | `https://connect.biorxiv.org/biorxiv_xml.php?subject=bioinformatics` | **0.76** | 100 |
| 14 | bioRxiv Systems Biology | `https://connect.biorxiv.org/biorxiv_xml.php?subject=systems_biology` | **0.76** | 100 |
| 15 | bioRxiv Biochemistry | `https://connect.biorxiv.org/biorxiv_xml.php?subject=biochemistry` | **0.76** | 100 |
| 16 | arXiv cs.LG (ML) | `http://export.arxiv.org/api/query?...cs.LG...` | **0.65** | 40 |
| 17 | arXiv cs.CV (vision / pathology) | `http://export.arxiv.org/api/query?...cs.CV...` | **0.65** | 30 |
| 18 | arXiv q-bio.QM (comp biology) | `http://export.arxiv.org/api/query?...q-bio.QM...` | **0.72** | 40 |

**About preprint weighting**: bioRxiv and arXiv are firehoses for cutting-edge work but aren't peer-reviewed and produce very high volume. Source weights penalise the raw final score: with `high.min_score: 40`, a bioRxiv paper needs raw ≈53 to clear the must-read floor and an arXiv cs.LG paper needs raw ≈62, vs 40 for a Nature/Cell journal paper. Combined with the rank-based `high.max_count: 10` cap, this surfaces genuinely transferable preprints (foundation models, multi-omics, vision-language for biology, etc.) without drowning the top tier in ML noise. The three arXiv feeds use arXiv's query API (the old `/rss/` endpoint returns zero entries — it's dead).

**The query API format** lets you filter by any arXiv category:
```
http://export.arxiv.org/api/query?search_query=cat:<category>&sortBy=submittedDate&sortOrder=descending&max_results=40
```
Useful categories: `cs.LG` (ML), `cs.CV` (vision), `cs.AI` (AI broadly), `stat.ML` (statistical ML), `q-bio.QM` (quantitative methods in biology), `q-bio.GN` (genomics), `q-bio.BM` (biomolecules). You can also combine with `AND`/`OR`: `cat:cs.LG+AND+cat:q-bio.QM` for papers cross-listed between ML and comp biology.

**Suggested additional feeds** you may want:
- Mol. Cell. Proteomics, Bioinformatics, Nucleic Acids Res. (URLs change periodically — check the publisher's site)
- arXiv stat.ML — overlap with cs.LG but sometimes has unique papers
- OpenReview (ICLR/NeurIPS) — no RSS, but arXiv cs.LG already catches most of these

**If a feed returns 0 entries**: the URL has likely moved. `fetch_and_score.py` logs `got N entries` per feed every run, so dead feeds are easy to spot. Visit the publisher's site, find the new RSS link, update `config.yaml`, push.

### Optional: LLM second-stage scoring

The default pipeline (embeddings + keywords + recency) scores papers cheaply on CPU. You can optionally enable a second pass that re-scores shortlisted papers using the Anthropic API. This produces a much cleaner medium-tier ranking at very low cost (~$3.60/month with Sonnet 4.6; ~$1.20/month with Haiku 4.5). Cached by paper ID across runs.

**Privacy note**: when a private knowledgebase is in use (next section), the LLM also generates a one-sentence reason alongside each score. That reason is grounded in your KB and can echo unpublished project details, so reasons are kept **only** in the local cache file (`data/llm_cache.json`) — they are *never* written to `docs/papers.json` and never shown on the public dashboard. The cache file itself is gitignored and persisted across CI runs via the GitHub Actions cache (not via git commits).

**One-time setup**:

1. Get an API key from https://console.anthropic.com/settings/keys
2. Add it to GitHub secrets:
   - Repo → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `ANTHROPIC_API_KEY`
   - Value: `sk-ant-...`
3. Edit `config.yaml`:
   ```yaml
   scoring:
     llm_rerank:
       enabled: true                # flip this on
       model: claude-sonnet-4-6     # or claude-haiku-4-5 for ~3x cheaper
   ```
4. (Optional) Tune `scoring.llm_rerank.profile_brief` — a 2–3 sentence summary of your interests that the LLM uses as context. Ignored if you set up a private knowledgebase (next section).
5. Push and trigger the workflow manually.

**For local runs**: `export ANTHROPIC_API_KEY=sk-ant-...` before running `python src/fetch_and_score.py`. To inspect why the LLM scored a paper a particular way, open `data/llm_cache.json` locally — each entry has the full reason text.

### Private research knowledgebase (optional, sensitive content)

For much better LLM judgment, you can supply a rich personal research knowledgebase (active projects, methods, collaborators, keyword tiers, unpublished ideas, grant strategy). This is kept **out of the repo** because it may contain sensitive content — it's gitignored and restored into the CI runner from an encrypted GitHub Secret at workflow time.

**How it works**:
- The file lives locally at `data/knowledgebase.md` (gitignored — never committed).
- CI restores it from the `KB_CONTENT` secret into the runner's filesystem before `fetch_and_score.py` runs.
- The pipeline uses the KB as the LLM system prompt (replacing the short `profile_brief`) and parses its "Keywords for Paper Matching" section for tier1/2/3 keyword scoring.
- When the KB changes, its sha256 invalidates the LLM cache, so scores are recomputed under the new context.
- When `KB_CONTENT` is empty, the pipeline falls back gracefully to `profile_brief` from `config.yaml`.

**First-time setup**:

1. Create `data/knowledgebase.md` locally with sections like:
   ```
   # Personal Research Knowledgebase
   ## Research Identity
   ...
   ## Core Research Areas
   ### 1. ...
   ## Keywords for Paper Matching
   ### Tier 1: Direct match to active work
   keyword1, keyword2, ...
   ### Tier 2: Core methods and adjacent domains
   ...
   ### Tier 3: Broader interest
   ...
   ```
2. Push its content into the `KB_CONTENT` secret:
   ```bash
   gh secret set KB_CONTENT < data/knowledgebase.md
   ```
   Or via the GitHub web UI: Settings → Secrets and variables → Actions → New repository secret → name `KB_CONTENT`, paste the file contents.
3. Trigger the workflow; it will restore the KB from the secret and use it for scoring.

**Updating the KB**: edit `data/knowledgebase.md` locally, then resync:
```bash
gh secret set KB_CONTENT < data/knowledgebase.md
```
Next workflow run will pick up the change automatically (and invalidate the LLM cache).

**Privacy note**: GitHub Secrets are encrypted at rest, never shown in logs (even if your workflow tries to `echo` them), and only accessible to workflows running on branches you control. For a public repo, this is a reasonable balance between CI automation and content privacy.

If the API key is missing or `enabled: false`, the pipeline gracefully skips the LLM stage and produces a valid `papers.json` with the embedding+keyword scores.

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
- Tier distribution is controlled by `scoring.tiers.{high,medium,low}.{max_count,min_score}`. The caps (`max_count`) fix the dashboard shape; the floors (`min_score`) are safety nets that stop the pipeline from promoting mediocre papers into a tier just to fill its quota in a weak week. Watch `finalize_tiers: kept N, dropped M` in the workflow logs — if the caps are consistently filled, the floors are permissive enough; if a tier is under-filled week after week, lower its floor.
- Ideas for future iterations are in `SUMMARY.md` → "Possible extensions" (Slack webhook, LLM digest email, cross-device read-state sync).
