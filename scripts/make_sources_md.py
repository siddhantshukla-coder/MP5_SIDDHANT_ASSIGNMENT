"""Regenerate SOURCES.md from data/raw/sources/sources.csv and data/raw/manual/resources.csv."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
docs = list(csv.DictReader(open(ROOT / "data/raw/sources/sources.csv", encoding="utf-8")))
res = list(csv.DictReader(open(ROOT / "data/raw/manual/resources.csv", encoding="utf-8")))
lines = ["# SOURCES", "",
         "Every record in `data/processed/` carries `source_url`, `retrieved_on`, `source_type` and `source_locator`. "
         "This file lists the underlying sources. Regenerate with `python scripts/make_sources_md.py`.", "",
         "## Official IIT Bhilai documents (raw files in `data/raw/sources/`)", "",
         "| File | Document | URL | Retrieved | Licence | How obtained |", "|---|---|---|---|---|---|"]
for d in docs:
    lines.append(f"| `{d['file']}` | {d['title']} | {d['source_url']} | {d['retrieved_on']} | {d['licence']} | {d['how_obtained']} |")
lines += ["", f"## Open learning resources ({len(res)})", "",
          "| # | Resource | Provider | Licence | Licence evidence | URL | Read from | Retrieved |", "|---|---|---|---|---|---|---|---|"]
for i, r in enumerate(res, 1):
    lines.append(f"| {i} | {r['title']} | {r['provider']} | {r['licence']} | {r['licence_url']} | {r['url']} | {r['source_url']} | {r['retrieved_on']} |")
lines += ["", "## Notes", "",
          "- NPTEL licence: NPTEL states its MOOC content is under Creative Commons Attribution-ShareAlike; the version is not "
          "stated on the pages read, and the evidence is a secondary source. Confirm on each course page before reuse.",
          "- MIT OCW: CC BY-NC-SA 4.0 per MIT Open Learning's terms (non-commercial, attribution, share-alike).",
          "- The skill taxonomy and course/resource-to-skill links are authored for this KB (`source_type = manual`), "
          "judged from the official syllabus text they point to.", ""]
(ROOT / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")
print(f"SOURCES.md: {len(docs)} documents, {len(res)} resources")
