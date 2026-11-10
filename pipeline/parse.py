
from __future__ import annotations

import re
from pathlib import Path

from .common import (CATEGORY_TO_TYPE, CODE_TOKEN_RE, MODE_BY_LETTER, norm_code, norm_date, norm_id,
                     norm_number, norm_ref, norm_rule_id, norm_semesters, norm_title, norm_ws,
                     parse_ltpc, read_csv)
from .extract import extract_course_blocks, load_text

NONE_WORDS = {"", "none", "nil", "na", "n/a", "-", "no"}


# ---------------------------------------------------------------- provenance
def _prov(r: dict, *, default_url: str = "", locator: str = "", entry: str = "", raw_file: str = "") -> dict:
    return {
        "source_url": r.get("source_url") or default_url,
        "retrieved_on": norm_date(r.get("retrieved_on")),
        "_retrieved_raw": r.get("retrieved_on", ""),
        "source_type": norm_ws(r.get("source_type")).lower(),
        "source_locator": r.get("source_locator") or locator,
        "entry_method": r.get("entry_method") or entry,
        "raw_file": r.get("raw_file") or raw_file or f"manual/{r.get('_file', '')}",
        "_file": r.get("_file", "-"), "_line": r.get("_line", "-"),
    }


# ---------------------------------------------------------------- manual entities
def _skill(r):
    return {"id": norm_id(r.get("id") or r.get("name")), "name": norm_ws(r.get("name")),
            "level": norm_ws(r.get("level")).lower(), "parent_skill": norm_id(r.get("parent_skill")) or None}


def _course_skill(r):
    return {"course": norm_code(r.get("course")), "skill": norm_id(r.get("skill")),
            "depth": norm_ws(r.get("depth")).lower()}


def _rule(r):
    return {"id": norm_rule_id(r.get("id")), "category": norm_id(r.get("category")),
            "text": norm_ws(r.get("text")), "numeric_limit": norm_number(r.get("numeric_limit")),
            "_limit_raw": r.get("numeric_limit", ""), "unit": norm_ws(r.get("unit")),
            "comparator": norm_ws(r.get("comparator")), "applies_to": norm_ws(r.get("applies_to")),
            "notes": norm_ws(r.get("notes"))}


def _resource(r):
    return {"id": norm_id(r.get("id") or r.get("title")), "title": norm_title(r.get("title")),
            "provider": norm_ws(r.get("provider")), "licence": norm_ws(r.get("licence")),
            "licence_url": norm_ws(r.get("licence_url")), "format": norm_ws(r.get("format")).lower(),
            "duration_hours": norm_number(r.get("duration_hours")), "_duration_raw": r.get("duration_hours", ""),
            "duration_basis": norm_ws(r.get("duration_basis")), "url": norm_ws(r.get("url")),
            "description": norm_ws(r.get("description"))}


def _resource_skill(r):
    return {"resource": norm_id(r.get("resource")), "skill": norm_id(r.get("skill")),
            "level": norm_ws(r.get("level")).lower()}


def _module(r):
    return {"id": norm_id(r.get("id")), "parent_id": norm_ref(r.get("parent_id")),
            "parent_type": norm_ws(r.get("parent_type")).lower() or "resource",
            "order": norm_number(r.get("order")), "_order_raw": r.get("order", ""),
            "title": norm_title(r.get("title")), "summary": norm_ws(r.get("summary"))}


MANUAL = {"skills": _skill, "course_skills": _course_skill, "rules": _rule, "resources": _resource,
          "resource_skills": _resource_skill, "modules": _module}


def _files_for(raw_dir: Path, entity: str) -> list[Path]:
    return sorted(p for p in raw_dir.rglob("*.csv")
                  if (p.stem == entity or p.stem.startswith(entity + "__")) and "sources" not in p.parts)


# ---------------------------------------------------------------- prerequisite / overlap text
def parse_prereq_text(text: str) -> list[list[str]]:
    """'Either CSL304 or CS550/DSL501 and MAL403 or equivalent' -> [['CSL304','CS550','DSL501'], ['MAL403']].
    Groups are AND-ed; codes inside a group are alternatives (OR)."""
    t = norm_ws(text)
    if t.lower().strip(". ") in NONE_WORDS:
        return []
    groups = []
    for part in re.split(r"\s*(?:,|;|\band\b)\s*", t, flags=re.I):
        codes = [norm_code(c) for c in CODE_TOKEN_RE.findall(part)]
        if codes:
            groups.append(list(dict.fromkeys(codes)))
    return groups


def parse_overlap_text(text: str) -> list[tuple[str, float | int | None]]:
    t = norm_ws(text)
    if t.lower().strip(". ") in NONE_WORDS:
        return []
    out = []
    for m in re.finditer(r"([A-Z]{2,3}\d{3}|[A-Za-z][A-Za-z .&-]*?)\s*\(\s*([\d.]+)\s*%\s*\)", t):
        name = m.group(1).strip()
        other = norm_code(name) if CODE_TOKEN_RE.fullmatch(name) else norm_ws(name)
        out.append((other, norm_number(m.group(2))))
    return out


def syllabus_modules(code: str, syllabus: str) -> list[dict]:
    """Split an official syllabus into ordered topic modules ('Module 1 ...' or ';'-separated)."""
    if not syllabus:
        return []
    if re.search(r"\bModule \d+", syllabus):
        parts = [p for p in re.split(r"(?=\bModule \d+)", syllabus) if p.strip()]
    else:
        parts = [p for p in re.split(r";\s*", syllabus) if len(p.strip()) > 3]
    mods = []
    for i, p in enumerate(parts, start=1):
        p = p.strip().rstrip(".;")
        head, _, rest = p.partition(":")
        if rest and len(head) <= 80:
            title, summary = head.strip(), rest.strip()
        else:
            title, summary = " ".join(p.split()[:8]), p
        mods.append({"id": f"{code.lower()}-m{i:02d}", "parent_id": code, "parent_type": "course",
                     "order": i, "_order_raw": str(i), "title": norm_title(title), "summary": summary})
    return mods


# ---------------------------------------------------------------- courses from PDF + curriculum
def _source_docs(raw_dir: Path) -> dict[str, dict]:
    path = raw_dir / "sources" / "sources.csv"
    if not path.exists():
        return {}
    return {r["file"]: r for r in read_csv(path)}


def _known_issues(raw_dir: Path) -> list[dict]:
    rows = []
    for p in _files_for(raw_dir, "known_issues"):
        rows += read_csv(p)
    for r in rows:
        r["code"], r["target"], r["context_course"] = (norm_code(r.get("code")), norm_code(r.get("target")),
                                                        norm_code(r.get("context_course")))
        r["action"] = norm_ws(r.get("action")).lower()
    return rows


def build_courses(raw_dir: Path, interim_dir: Path, docs: dict, issues: list[dict]) -> dict:
    prog_files = _files_for(raw_dir, "programme_courses")
    disc = {norm_code(r["prefix"]): r for p in _files_for(raw_dir, "disciplines") for r in read_csv(p)}
    # 1. extract every course block from every catalogue document
    blocks, block_doc = {}, {}
    for fname, doc in docs.items():
        if norm_ws(doc.get("role")).lower() != "course-catalogue":
            continue
        path = raw_dir / "sources" / fname
        if not path.exists():
            continue
        text, how = load_text(path, interim_dir)
        found = extract_course_blocks(text)
        print(f"[parse] {fname}: {len(found)} course blocks extracted ({how})")
        for code, b in found.items():
            blocks.setdefault(code, b)
            block_doc.setdefault(code, doc)
    alias = {(i["code"]): i for i in issues if i["action"] == "alias"}
    ignore = {(i["context_course"], i["code"]): i for i in issues if i["action"] == "ignore_ref"}

    courses, prereqs, overlaps, modules, applied = [], [], [], [], []
    for p in prog_files:
        for r in read_csv(p):
            printed = norm_code(r.get("code_as_printed"))
            code = printed
            row_notes = []
            if printed in alias:
                code = alias[printed]["target"]
                applied.append({**alias[printed], "where": f"{r['_file']}:{r['_line']}"})
                row_notes.append(f"alias {printed}->{code}: {alias[printed].get('reason', '')}")
            b = blocks.get(code)
            doc = block_doc.get(code, {})
            ltpc = parse_ltpc(r.get("ltpc_as_printed"))
            sems, term = norm_semesters(r.get("semester"))
            cat = norm_ws(r.get("category")).upper()
            credits_raw = b["credits_raw"] if b else (str(ltpc[3]) if ltpc and ltpc[3] is not None else r.get("ltpc_as_printed", ""))
            ltp = b["ltp"] if b else ("-".join(str(x) for x in ltpc[:3]) if ltpc else "")
            letter = code[2] if len(code) > 2 else ""
            mode = MODE_BY_LETTER.get(letter, "other")
            lt = parse_ltpc(ltp)
            if letter == "L" and lt and lt[2]:
                mode = "theory+lab"
            dinfo = disc.get(code[:2], {})
            if b:
                locator = (f"Courses of Study (Oct 2026), Course Contents PDF p.{b['page']}; "
                           f"category/semester: {r.get('source_locator') or 'BTech DSAI curriculum'}")
                prov = _prov(r, default_url=doc.get("source_url", ""), locator=locator, entry="pdf-extract",
                             raw_file=f"sources/{doc.get('file', '')}")
                prov["source_url"] = doc.get("source_url") or r.get("source_url", "")
                prov["retrieved_on"] = norm_date(doc.get("retrieved_on")) or prov["retrieved_on"]
                prov["source_type"] = norm_ws(doc.get("source_type")).lower() or prov["source_type"]
                prov["source_locator"], prov["entry_method"] = locator, "pdf-extract"
            else:
                prov = _prov(r, entry="manual-transcription")
                row_notes.append("no Course Contents block in the PDF; fields from curriculum table only")
            course = {
                "code": code, "title": norm_title(b["title"] if b else r.get("title_as_printed")),
                "dept": dinfo.get("department", ""), "discipline": dinfo.get("discipline", ""),
                "credits": norm_number(credits_raw), "_credits_raw": credits_raw, "ltp": ltp,
                "semester_numbers": sems, "term": term, "category": cat,
                "course_type": CATEGORY_TO_TYPE.get(cat, cat.lower()), "mode": mode,
                "level": (int(code[3]) * 100) if len(code) > 3 and code[3].isdigit() else None,
                "objectives": norm_ws(r.get("objectives")), "syllabus": b["syllabus"] if b else "",
                "prerequisite_text": norm_ws(b["prerequisite_text"]) if b else "",
                "overlap_text": norm_ws(b["overlap_text"]) if b else "",
                "_printed_code": printed, "_printed_title": r.get("title_as_printed", ""),
                "_printed_ltpc": ltpc, "_printed_ltpc_raw": r.get("ltpc_as_printed", ""),
                "_has_block": bool(b), "_notes": row_notes, **prov,
            }
            courses.append(course)
            if not b:
                continue
            edge_prov = {k: v for k, v in prov.items()}
            for gi, group in enumerate(parse_prereq_text(b["prerequisite_text"]), start=1):
                for req in group:
                    if (code, req) in ignore:
                        applied.append({**ignore[(code, req)], "where": f"{code} prerequisite text"})
                        continue
                    req = alias[req]["target"] if req in alias else req
                    prereqs.append({"course": code, "requires": req, "kind": "hard",
                                    "alt_group": f"{code}-g{gi}", **edge_prov})
            for other, pct in parse_overlap_text(b["overlap_text"]):
                overlaps.append({"course": code, "other": other, "percent": pct, **edge_prov})
            for m in syllabus_modules(code, b["syllabus"]):
                modules.append({**m, **edge_prov})
    codes = {c["code"] for c in courses}
    for o in overlaps:
        o["other_in_catalogue"] = o["other"] in codes
    return {"courses": courses, "prerequisites": prereqs, "course_overlaps": overlaps,
            "_course_modules": modules, "_applied_issues": applied, "_institute_index": set(blocks)}


def run(raw_dir: Path, interim_dir: Path) -> dict:
    docs = _source_docs(raw_dir)
    issues = _known_issues(raw_dir)
    data = build_courses(raw_dir, interim_dir, docs, issues)
    for entity, fn in MANUAL.items():
        rows = []
        for p in _files_for(raw_dir, entity):
            for r in read_csv(p):
                url_default = r.get("url", "") if entity == "resources" else ""
                rows.append({**fn(r), **_prov(r, default_url=url_default)})
        data[entity] = rows
    data["modules"] = data["_course_modules"] + data["modules"]
    for entity in ("courses", "prerequisites", "course_overlaps", "skills", "course_skills", "rules",
                   "resources", "resource_skills", "modules"):
        print(f"[parse] {entity:<16} {len(data[entity]):>4} rows")
    return data
