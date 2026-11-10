# IIT Bhilai B.Tech DSAI — source-traced knowledge base (pre-embedding)

A reproducible pipeline that turns IIT Bhilai's official B.Tech **Data Science and Artificial Intelligence** documents, plus 32 openly licensed learning resources, into clean, validated, chunked seed data for a study-planning "buddy". It stops right before embeddings: **no embedding or LLM API is called anywhere.**

```bash
pip install -r requirements.txt        # just pypdf
python run_pipeline.py                 # full run: data/raw -> data/processed   (or: make pipeline)
python run_pipeline.py --sample        # small sample (5 courses) in tests/fixtures/sample
python -m unittest discover tests      # parsers, sample run, and the broken fixture must fail
```
Exit code `0` = exported; `1` = validation failed and nothing was written.

**Result of the full run:** 28 courses, 16 prerequisite edges, 10 overlap edges, 27 rules, 32 resources, 38 skills, 210 modules, **121 chunks** — see [DATA_QUALITY.md](DATA_QUALITY.md).

## Scope
One programme in depth: B.Tech DSAI, curriculum "applicable for 2023 batch onwards" (Courses of Study, Oct 2026). Catalogue = the PL + all 17 PC courses (DSAI semester plan), 7 DS 500/600-level electives that 3rd/final-year B.Tech students may take as PE, and the 3 IC courses that DSAI courses name as prerequisites (CSL100, MAL100, ECL101). The other 11 IC courses are out of scope.

## Pipeline (high-level design)

```
data/raw/sources/*.pdf ─┐
data/raw/manual/*.csv ──┼─▶ 1 INGEST ─▶ 2 PARSE & NORMALISE ─▶ 3 VALIDATE ─▶ 4 CHUNK ─▶ 5 EXPORT ─▶ data/processed/
                        │   (sha256)    (PDF→text→course blocks;   (fail loudly)  (≤180 words,  (CSV+JSON per entity,
                        │                join with curriculum)                     with metadata) chunks.jsonl, manifest)
```

| Stage | Input | What it does | What to expect |
|---|---|---|---|
| 1 Ingest `pipeline/ingest.py` | `data/raw/**` | Never modifies raw files; fingerprints each into `data/raw/MANIFEST.json` | Warns if a raw file changed since the last run |
| 2 Parse `pipeline/extract.py`, `parse.py` | PDFs + CSVs | Extracts ~400 course blocks (code, title, credits, L-T-P, prerequisites, overlap, syllabus) from the Courses of Study PDF with pypdf; joins them to the hand-transcribed DSAI curriculum; normalises codes (`DS-201`→`DS201`), credits to numbers, semesters to 1–8 + Monsoon/Winter, PDF artefacts (`Al`→`AI`); parses prerequisite sentences into AND-of-OR edges | Never crashes on bad values: they become `None` with the raw text kept, so stage 3 can report them precisely |
| 3 Validate `pipeline/validate.py` | parsed rows | 26 checks (list in DATA_QUALITY.md) — missing course in a prerequisite, prerequisite cycle, non-numeric credits, duplicate code, missing source URL, dangling links, bad enums… plus cross-checks against the documents' own rules | Any **error** stops the run before export; warnings are printed and saved to `validation_report.json` (`--strict` makes them fatal) |
| 4 Chunk `pipeline/chunk.py` | valid rows | One overview chunk per course, syllabus chunks, one chunk per rule, resource description + weekly-outline chunks; split at sentence/`;` boundaries, ≤180 words, each prefixed with a context header | Deterministic ids `<parent>#<type>-<n>`; every chunk has `parent_id`, `chunk_type`, source and filter metadata |
| 5 Export `pipeline/export.py` | rows + chunks | Writes `data/processed/<entity>.csv/.json`, `chunks.jsonl`, `validation_report.json`, `manifest.json` (counts, fill-rates, sha256 of inputs/outputs) | Byte-identical on re-run (no timestamps) |

Messy-input handling is explicit, not silent: `data/raw/manual/known_issues.csv` records three decisions about problems in the official PDF (a misprinted code, a non-existent prerequisite code, a legacy code). Each applied decision is re-reported as a warning on every run.

## Schema (`pipeline/common.py`) and changes from the starting schema
Entities: `courses`, `prerequisites`, `course_overlaps`, `skills`, `course_skills`, `rules`, `resources`, `resource_skills`, `modules`, `chunks`. Every record carries `source_url`, `retrieved_on`, `source_type` (official / open-licence / manual).

| Change | Why |
|---|---|
| `courses.category` (IC/PL/PC/PE/OE/LA) kept alongside `course_type` (core/elective/open) | IIT Bhilai's credit rules are per category (e.g. PC ≥ 51.5), so core/elective alone can't check them |
| `courses.ltp`, `level` added | Credits follow from L-T-P (institute rule, checked); 500/600-level courses are electives only for 3rd/final year |
| `prerequisites.alt_group` added | Official text mixes AND/OR ("Either CSL304 or DSL501 and MAL403"): edges in one group are alternatives, groups are AND-ed |
| New `course_overlaps` (course, other, percent) | The >25%-overlap rule decides eligibility; the PDF gives the percentages |
| `rules.comparator`, `unit` added | Makes `numeric_limit` machine-checkable (≤ 21 credits/semester vs ≥ 51.5 PC credits) |
| `resources.licence_url`, `duration_basis` added | Evidence for the licence; durations are rough estimates and say how they were estimated |
| `modules.parent_type` added | Modules belong to courses (split from the official syllabus) or to resources (NPTEL weekly plan) |
| Provenance adds `source_locator` (page/section), `entry_method`, `raw_file` | A reviewer can open the exact page; distinguishes PDF-extracted, hand-transcribed and curated data |
| Exercise (bonus) not built | Time |

## What was entered by hand (brief asks to say so)
- **Official PDFs**: iitbhilai.ac.in's robots.txt disallows automated fetching of these pages, so they were downloaded manually in a browser — not scraped.
- **DSAI curriculum table / semester plan** → `programme_courses.csv`, transcribed as printed (multi-column grid). Course details themselves are *extracted* from the PDF.
- **Rules** → `rules.csv`, quoted verbatim with section numbers.
- **Resources** → read from each NPTEL syllabus PDF / OCW / book page via web tools and entered by hand (no bulk scraping).
- **Skill taxonomy and course/resource→skill links** are my judgement from the syllabus text (`source_type = manual`).

## AI-use disclosure
Built with an AI assistant (Claude) for drafting code, reading source pages and drafting docs. All data comes from the cited official/open sources; every number in the reports comes from running the pipeline. I reviewed the outputs, including catching mistakes (e.g. CSL100 teaches C, not Python, so its skill link was corrected).

## Repository layout
```
run_pipeline.py          one command        pipeline/   ingest, extract, parse, validate, chunk, export
data/raw/                untouched inputs   data/processed/   seed data + chunks.jsonl
tests/                   unit tests + sample and broken fixtures
SOURCES.md  DATA_QUALITY.md  IDEAS.md      scripts/make_sources_md.py
```
