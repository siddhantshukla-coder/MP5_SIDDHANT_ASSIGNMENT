# Ideas note (Part E)

## How I'd use this data
 Embed `chunks.jsonl` into a vector store, and load the processed CSVs into a small relational/graph store. The buddy then answers in two steps: **structured reasoning first** (prerequisite graph, credit rules, overlaps, skill links — exact and checkable), then **retrieval** over chunks to explain and cite. Every answer quotes a rule or syllabus chunk with its `source_url` and page, so a student can verify it. Metadata filters (category, semester, credits, licence, skills) narrow retrieval before similarity search.

## Three questions the buddy could answer well if completely made, solely using this data
1. **"Can I take DSL608 Reinforcement Learning next semester? I've done CSL304 and MAL403."** — the prerequisite edges give `(CSL304 or DSL501) and MAL403` → yes; it also checks the 500/600-level rule (3rd/final year only) and quotes both from the Courses of Study.
2. **"I've already credited DSL201 — should I pick DSL502 as an elective?"** — `course_overlaps` says DSL502 overlaps DSL201 by 60 %, and rule OVERLAP-MAX-25 forbids credit for >25 % overlap → not eligible, with both sources cited.
3. **"I want to work in NLP — what should I take, and what free material fills the gaps?"** — skill links map the goal to DSL504 → DSL605 (prerequisite chain), plus NPTEL NLP (week-by-week outline), MIT 6.864 and d2l; it can add that up to 6 MOOC credits may count as PE/OE with DUGC permission (UG Manual 3.2.1).

## Questions it could not answer if completely made, solely using this data (yet)
- **"What CGPA do I need for a minor in DSAI?"** — no minor regulation exists in the collected documents; the buddy should say so, not guess.
- **"Which electives are offered next Winter, and who teaches them?"** — semester offerings and timetables aren't in these documents.
- **"Will NPTEL course X count for my credit?"** — approval is per course and per semester by the DUGC; the data has the rules but not the approved list.
- Anything personal ("am I on track to graduate?") needs the student's own transcript, which this KB deliberately doesn't hold.
