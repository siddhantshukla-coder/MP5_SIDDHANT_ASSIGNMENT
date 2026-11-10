
from __future__ import annotations

import hashlib
import re

MAX_WORDS = 180


def split_text(text: str, max_words: int = MAX_WORDS) -> list[str]:
    pieces = [p.strip() for p in re.split(r"(?<=[.;])\s+", text or "") if p.strip()]
    out, cur = [], []
    for p in pieces:
        words = p.split()
        while len(words) > max_words:             # a single huge sentence: hard split
            out.append(" ".join(words[:max_words]))
            words = words[max_words:]
        if cur and len(cur) + len(words) > max_words:
            out.append(" ".join(cur))
            cur = []
        cur += words
    if cur:
        out.append(" ".join(cur))
    return out


def _prov(r):
    return {k: r.get(k) for k in ("source_url", "retrieved_on", "source_type", "source_locator")}


def _mk(parent_id, parent_type, chunk_type, n, header, body, meta, r):
    text = f"{header}\n{body}".strip()
    return {"chunk_id": f"{parent_id}#{chunk_type}-{n}", "parent_id": parent_id, "parent_type": parent_type,
            "chunk_type": chunk_type, "text": text, "n_words": len(text.split()),
            "text_sha1": hashlib.sha1(text.encode()).hexdigest()[:12], "metadata": {**meta, **_prov(r)}}


def run(data: dict) -> list[dict]:
    chunks = []
    skills_of = {}
    for cs in data["course_skills"]:
        skills_of.setdefault(cs["course"], []).append(cs["skill"])
    for rs in data["resource_skills"]:
        skills_of.setdefault(rs["resource"], []).append(rs["skill"])
    reqs = {}
    for e in data["prerequisites"]:
        reqs.setdefault(e["course"], []).append(e["requires"])

    for c in data["courses"]:
        meta = {"course_code": c["code"], "title": c["title"], "category": c["category"],
                "course_type": c["course_type"], "semesters": c["semester_numbers"], "term": c["term"],
                "credits": c["credits"], "mode": c["mode"], "level": c["level"], "dept": c["dept"],
                "requires": sorted(set(reqs.get(c["code"], []))), "skills": skills_of.get(c["code"], [])}
        head = f"{c['code']} {c['title']} | {c['credits']} credits ({c['ltp']}) | {c['category']} | semester {','.join(map(str, c['semester_numbers']))}"
        overview = (f"Prerequisites: {c['prerequisite_text'] or 'None'}. Overlap: {c['overlap_text'] or 'NA'}. "
                    f"Mode: {c['mode']}.")
        chunks.append(_mk(c["code"], "course", "course_overview", 1, head, overview, meta, c))
        for i, part in enumerate(split_text(c["syllabus"]), start=1):
            chunks.append(_mk(c["code"], "course", "syllabus", i, f"{c['code']} {c['title']} | syllabus", part, meta, c))

    for r in data["rules"]:
        meta = {"rule_id": r["id"], "rule_category": r["category"], "applies_to": r["applies_to"],
                "numeric_limit": r["numeric_limit"], "unit": r["unit"]}
        for i, part in enumerate(split_text(r["text"]), start=1):
            chunks.append(_mk(r["id"], "rule", "rule", i, f"Academic rule {r['id']} ({r['category']}) | applies to {r['applies_to']}", part, meta, r))

    mods = {}
    for m in data["modules"]:
        if m["parent_type"] == "resource":
            mods.setdefault(m["parent_id"], []).append(m)
    for r in data["resources"]:
        meta = {"resource_id": r["id"], "provider": r["provider"], "licence": r["licence"], "format": r["format"],
                "duration_hours": r["duration_hours"], "url": r["url"], "skills": skills_of.get(r["id"], [])}
        head = f"{r['title']} | {r['provider']} | {r['format']} | ~{r['duration_hours']} h | licence {r['licence']}"
        for i, part in enumerate(split_text(r["description"]), start=1):
            chunks.append(_mk(r["id"], "resource", "resource_description", i, head, part, meta, r))
        weeks = sorted(mods.get(r["id"], []), key=lambda m: m["order"] or 0)
        if weeks:
            body = " ".join(f"{m['title']}: {m['summary']}." for m in weeks)
            for i, part in enumerate(split_text(body), start=1):
                chunks.append(_mk(r["id"], "resource", "resource_modules", i, f"{r['title']} | weekly outline", part, meta, r))
    print(f"[chunk] {len(chunks)} chunks (max {MAX_WORDS} words + header)")
    return chunks
