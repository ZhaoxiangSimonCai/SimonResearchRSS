"""Render docs/papers.json into a single-file docs/index.html dashboard."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from dateutil import parser as dateparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "src" / "templates"
PAPERS_JSON = REPO_ROOT / "docs" / "papers.json"
OUT_HTML = REPO_ROOT / "docs" / "index.html"


def main() -> int:
    if not PAPERS_JSON.exists():
        print(
            f"error: {PAPERS_JSON} not found. Run `python src/fetch_and_score.py` first.",
            file=sys.stderr,
        )
        return 1

    with open(PAPERS_JSON) as f:
        data = json.load(f)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("dashboard.html.j2")

    updated_at_raw = data.get("updated_at") or datetime.utcnow().isoformat()
    try:
        updated_dt = dateparser.parse(updated_at_raw)
        updated_human = updated_dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        updated_human = updated_at_raw

    papers_json_inline = json.dumps(data["papers"], ensure_ascii=False)
    # Guard against accidental </script> in abstracts breaking the inline block.
    papers_json_inline = papers_json_inline.replace("</", "<\\/")

    html = template.render(
        updated_human=updated_human,
        count=data.get("count", 0),
        tier_counts=data.get("tier_counts", {"high": 0, "medium": 0, "low": 0}),
        library_size=data.get("library_size", 0),
        feeds=data.get("feeds", []),
        papers_json=papers_json_inline,
    )
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_HTML, "w") as f:
        f.write(html)
    print(f"wrote {OUT_HTML} ({len(html)//1024} KB, {data.get('count', 0)} papers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
