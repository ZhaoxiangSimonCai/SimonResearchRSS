# Research Feed: Project Summary

## What this is

A personalised academic paper feed reader that runs daily via GitHub Actions, scores papers against your research profile using local sentence embeddings (zero API cost), and deploys a static dashboard to GitHub Pages.

## Architecture

- **Fetch**: Pull RSS feeds from bioRxiv, arXiv, PubMed, and journal-specific feeds
- **Score**: Encode papers and your research profile with `all-MiniLM-L6-v2` (sentence-transformers), blend 70% semantic similarity with 30% keyword matching
- **Render**: Generate a static HTML dashboard with search, filtering by tier (must-read / worth scanning / on the radar)
- **Deploy**: GitHub Actions cron (daily 7am AEST) commits to `docs/` and deploys via GitHub Pages

## Project structure

```
research-feed/
├── config.yaml                        # Research profile, keywords, feed URLs, scoring params
├── requirements.txt                   # feedparser, numpy, pyyaml, sentence-transformers
├── src/
│   ├── fetch_and_score.py             # Main pipeline: fetch RSS, deduplicate, score, save JSON
│   └── generate_dashboard.py          # Converts papers.json into docs/index.html
├── docs/                              # Output dir (GitHub Pages root)
│   ├── papers.json                    # Scored papers data
│   └── index.html                     # Dashboard
└── .github/workflows/
    └── update-feed.yml                # Daily cron + GitHub Pages deploy
```

## Setup steps

1. Create a GitHub repo and push all files
2. Enable GitHub Pages: Settings > Pages > Source: GitHub Actions
3. Customise `config.yaml` (keywords, feeds, thresholds)
4. Trigger manually: Actions > Update Research Feed > Run workflow
5. Dashboard appears at `https://<username>.github.io/<repo-name>/`

## Scoring details

- **Semantic similarity**: Cosine similarity between paper text and research profile embedding, mapped from [0.15, 0.55] to [0, 100]
- **Keyword boost**: Tier1 keywords = 30pts, Tier2 = 15pts, Tier3 = 7pts
- **Blend**: 0.7 * embedding_score + 0.3 * keyword_score
- **Tiers**: high (>= 60), medium (>= 30), low (< 30)

## Research profile (pre-configured)

Tier1 (must-read): DIA-MS, data-independent acquisition, cancer proteomics, foundation model, federated learning, synthetic lethality, multi-omics integration, ProCan

Tier2 (high relevance): mass spectrometry, label-free quantification, cancer cell lines, drug response prediction, self-supervised learning, CRISPR screen, pan-cancer, transfer learning, multimodal learning

Tier3 (moderate): proteogenomics, single-cell proteomics, transformer, deep learning, cancer genomics, biomarker discovery, clinical proteomics, protein language model

## Possible extensions

- Slack webhook for daily top-5 notifications
- Semantic Scholar API for citation-aware boosting
- Read/unread tracking via a state JSON file
- Weekly LLM-generated digest summaries (optional API usage)
- Additional feeds (e.g. Nature Communications, Cell Reports, HUPO journals)
