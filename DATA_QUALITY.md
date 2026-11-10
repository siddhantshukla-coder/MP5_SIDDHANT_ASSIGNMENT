# Data quality report (Part D)

Numbers below are from `python run_pipeline.py` on the full DSAI data (see `data/processed/manifest.json`, `validation_report.json`).

## What was collected
| Entity | Count | Fields below 100 % filled |
|---|---|---|
| Courses | **28** (3 IC, 1 PL, 17 PC, 7 PE) | `objectives` 0 % (the official document gives topic syllabi, not objectives); `syllabus`, `prerequisite_text`, `overlap_text` 96.4 % (UGQ301 has no Course Contents entry) |
| Prerequisite edges | 16 (in 15 AND-groups) | — |
| Overlap edges | 10 (4 point inside the catalogue) | — |
| Academic rules | **27**, one quotable rule each | `numeric_limit` / `unit` / `comparator` 77.8 % (6 rules are qualitative, e.g. "prior permission needed") |
| Open resources | **32** (18 NPTEL, 10 MIT OCW, 4 open books) | — |
| Skills / course-skill / resource-skill links | 38 / 43 / 50 | `parent_skill` 78.9 % (the 8 root domains have no parent, by design) |
| Modules | 210 (161 split from official syllabi, 49 NPTEL weeks) | — |
| **Chunks** | **121** (28 course overview, 30 syllabus, 27 rule, 32 resource description, 4 weekly outline); 15–188 words | — |

Every record has `source_url`, `retrieved_on` (2026-11-10) and `source_type` (100 %).

## What the validator checks (26 checks)
**Errors (stop the run):** missing/invalid source URL; invalid retrieved date; bad source_type or entry_method; empty required field; duplicate course code / rule / skill / resource / module id; malformed course code; non-numeric or out-of-range credits; bad enum (category, type, mode, edge kind, depth, skill level); semester outside 1–8; prerequisite naming a course not in the catalogue; self-prerequisite; prerequisite cycle; dangling skill / course / resource links; skill-parent cycle; non-numeric rule limit; resource without licence; non-numeric duration; empty catalogue.
**Warnings:** course missing from Course Contents; curriculum table disagrees with Course Contents (title or L-T-P-C); credits ≠ L + T + P/2 (the institute's own rule); category credit totals ≠ the programme minimum (PL = 4 ✓, PC = 51.5 ✓); documented fix applied; thin record; below the brief's minimums.

## What it caught in the real documents
Without the three decisions in `known_issues.csv`, the full run **fails with 4 errors**:
1. **DSP353 vs DSL353** — the DSAI semester plan prints "DSP353 Information Security 3-0-0-3"; the course table and Course Contents say **DSL353, 2-0-2-3**. Treated as a misprint (alias) → still reported as a warning.
2. **CSP352 prerequisite "IC100"** — no such code anywhere in the Courses of Study (probably CSL100). Edge dropped, text kept.
3. **DSL608 prerequisite "CS550"** — legacy code absent from the 2026 catalogue; DSL501 in the same OR-group keeps the requirement.

Remaining warnings (7): UGQ301 has no syllabus anywhere; DSP301 printed "AI and ML Lab" vs "AI and Machine Learning Lab"; the three decisions above. The broken fixture (`tests/fixtures/broken`) proves the five brief-named failures — missing prerequisite course, cycle, non-numeric credits, duplicate code, no source URL — each stop the run.

## Missing or uncertain
- **Minor eligibility is not in any of the three official documents** (no minor programme or CGPA cut-off). The closest rule stored is BTech Honours entry (end of 5th semester, no CGPA given). Needs the DUGC/academic office's minor regulations.
- The documents disagree on V-type (NPTEL/special-topic) course size: "1–2 credits" (Courses of Study) vs "1–3" (UG Manual). Both 6-credit programme caps agree.
- NPTEL licence: "CC BY-SA" from a secondary source; version not shown on the pages read. Durations are rough estimates (method in `duration_basis`).
- Which DS electives run in a given semester is unknown; PE semesters (5, 7, 8) are the PE slots in the plan.
- Skill links are judgement calls from syllabus text. Syllabus-derived module titles are heuristic (a few are clipped, e.g. "Building Models for").
- Page numbers in `source_locator` for extracted courses are PDF page indices, not printed page numbers.

## How a teammate can verify a sample
1. Pick ~5 rows at random from `data/processed/courses.csv` and `rules.csv`.
2. Open the PDF in `data/raw/sources/` (or the `source_url`) at the `source_locator` page/section; compare code, title, credits, L-T-P, prerequisites (courses) or the quoted text (rules) word for word. After one run, `data/interim/*.txt` holds the exact text the parser saw (it is git-ignored, so run the pipeline first) — `grep -n "DSL251" data/interim/*.txt` jumps to it.
3. For resources, open `url` and the licence evidence in `licence_url`.
4. Check `data/raw/MANIFEST.json` sha256 against the PDFs to confirm the raw files are the ones processed, and re-run the pipeline: `manifest.json` output hashes should match.
