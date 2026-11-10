# data/raw — inputs, never edited by the pipeline

- `sources/` — the official IIT Bhilai PDFs exactly as downloaded (renamed only), plus `sources.csv` giving each file's URL, retrieval date, type and how it was obtained.
- `manual/` — hand-entered CSVs, each row with its own `source_url`, `retrieved_on`, `source_type`, `source_locator`:
  - `programme_courses.csv` — the DSAI curriculum/semester plan, transcribed as printed (the PDF lays it out as a multi-column grid that doesn't extract cleanly).
  - `known_issues.csv` — explicit decisions about problems found in the official documents (alias / ignore a reference), each with a reason.
  - `rules.csv` — academic rules quoted verbatim, one rule per row.
  - `resources.csv`, `resource_skills.csv`, `modules.csv` — open learning resources, their skills, and NPTEL weekly outlines.
  - `skills.csv`, `course_skills.csv`, `disciplines.csv` — skill taxonomy, course-to-skill links, discipline lookup.

`ingest` fingerprints every file here into `MANIFEST.json`; a changed file is flagged on the next run.
