
from __future__ import annotations

import re

from .common import (CATEGORIES, CODE_RE, COURSE_TYPES, DEPTHS, EDGE_KINDS, ENTRY_METHODS, MODES,
                     SKILL_LEVELS, SOURCE_TYPES, parse_ltpc, title_key)

# check name -> what it verifies (used verbatim in the data-quality report)
CHECKS = {
    "missing_source_url": "Every record has an http(s) source_url",
    "bad_retrieved_on": "Every record has a valid retrieved_on date",
    "bad_source_type": "source_type is official / open-licence / manual",
    "missing_required_field": "Required fields are non-empty",
    "duplicate_id": "No duplicate course code or rule / skill / resource / module id",
    "bad_course_code": "Course codes look like DSL251 (3 letters + 3 digits)",
    "non_numeric_credits": "Course credits are numeric",
    "credits_out_of_range": "Course credits are > 0 and <= 20",
    "bad_enum": "category, course_type, mode, edge kind, depth, skill level use allowed values",
    "bad_semester": "Semester numbers are within 1-8",
    "missing_prerequisite_course": "Both ends of a prerequisite edge exist in the catalogue",
    "self_prerequisite": "A course does not require itself",
    "prerequisite_cycle": "No cycle among hard prerequisites",
    "dangling_reference": "Links (course_skills, resource_skills, modules, skill parents) point at existing records",
    "skill_parent_cycle": "Skill taxonomy has no parent cycle",
    "non_numeric_limit": "A rule's numeric_limit is numeric when given",
    "missing_licence": "Every open resource records a licence",
    "bad_duration": "Resource duration is numeric when given",
    "no_catalogue_entry": "(warning) programme course has a Course Contents entry in the PDF",
    "printed_mismatch": "(warning) curriculum table agrees with Course Contents on title and L-T-P-C",
    "credit_formula": "(warning) credits = L + T + P/2, the institute's own rule",
    "category_total": "(warning) core credits per category add up to the programme minimum",
    "known_issue_applied": "(warning) a documented fix from known_issues.csv was applied",
    "thin_record": "(warning) course has no syllabus/objectives; resource has no description",
    "empty_entity": "courses, rules and resources are not empty (catches a wrong --raw path)",
    "below_brief_minimum": "(warning) >=15 courses and >=30 resources, as the brief requires",
}

KEY = {"courses": "code", "skills": "id", "rules": "id", "resources": "id", "modules": "id"}
PAIR = {"prerequisites": ("course", "requires"), "course_skills": ("course", "skill"),
        "resource_skills": ("resource", "skill")}
REQUIRED = {
    "courses": ["code", "title", "dept", "category", "course_type"],
    "rules": ["id", "category", "text"],
    "resources": ["id", "title", "provider", "url", "format"],
    "skills": ["id", "name", "level"],
    "modules": ["id", "parent_id", "title"],
    "prerequisites": ["course", "requires"],
    "course_skills": ["course", "skill"],
    "resource_skills": ["resource", "skill"],
}
ENTITIES = ["courses", "prerequisites", "course_overlaps", "skills", "course_skills", "rules",
            "resources", "resource_skills", "modules"]


def find_cycle(graph: dict):
    """Iterative DFS; returns one cycle as [a, b, ..., a] or None."""
    color = {}
    for start in sorted(graph):
        if color.get(start):
            continue
        path, iters = [start], [iter(sorted(graph[start]))]
        color[start] = 1
        while path:
            try:
                v = next(iters[-1])
            except StopIteration:
                color[path.pop()] = 2
                iters.pop()
                continue
            c = color.get(v, 0)
            if c == 1:
                return path[path.index(v):] + [v]
            if c == 0:
                color[v] = 1
                path.append(v)
                iters.append(iter(sorted(graph.get(v, []))))
    return None


def validate(data: dict) -> list[dict]:
    issues: list[dict] = []

    def add(check, entity, r, msg, severity="error"):
        if r is None:
            rid, where = "-", "-"
        elif entity in KEY:
            rid, where = r.get(KEY[entity]) or "?", f"{r.get('_file')}:{r.get('_line')}"
        else:
            a, b = PAIR.get(entity, ("course", "other"))
            rid, where = f"{r.get(a)}->{r.get(b)}", f"{r.get('_file')}:{r.get('_line')}"
        issues.append({"check": check, "severity": severity, "entity": entity, "id": rid,
                       "where": where, "message": msg})

    courses = {r["code"] for r in data["courses"] if r.get("code")}
    skills = {r["id"] for r in data["skills"] if r.get("id")}
    resources = {r["id"] for r in data["resources"] if r.get("id")}

    # --- provenance on every record ---------------------------------------
    for entity in ENTITIES:
        for r in data[entity]:
            if not re.match(r"^https?://\S+$", r.get("source_url") or ""):
                add("missing_source_url", entity, r, "record has no valid source URL")
            if not r.get("retrieved_on"):
                add("bad_retrieved_on", entity, r, f"retrieved_on '{r.get('_retrieved_raw')}' is not a valid date")
            if r.get("source_type") not in SOURCE_TYPES:
                add("bad_source_type", entity, r, f"source_type '{r.get('source_type')}' not in {sorted(SOURCE_TYPES)}")
            if r.get("entry_method") not in ENTRY_METHODS:
                add("bad_enum", entity, r, f"entry_method '{r.get('entry_method')}' not in {sorted(ENTRY_METHODS)}")

    # --- required fields + duplicates --------------------------------------
    for entity, fields in REQUIRED.items():
        for r in data[entity]:
            for f in fields:
                if r.get(f) in (None, "", []):
                    add("missing_required_field", entity, r, f"'{f}' is empty")
    for entity, key in KEY.items():
        seen = {}
        for r in data[entity]:
            k = r.get(key)
            if k and k in seen:
                add("duplicate_id", entity, r, f"duplicate {key} '{k}' (first seen at {seen[k]})")
            elif k:
                seen[k] = f"{r.get('_file')}:{r.get('_line')}"
    for entity, (a, b) in PAIR.items():
        seen = set()
        for r in data[entity]:
            k = (r.get(a), r.get(b))
            if k in seen:
                add("duplicate_id", entity, r, f"duplicate link {k[0]} -> {k[1]}", "warning")
            seen.add(k)

    # --- courses -----------------------------------------------------------
    for r in data["courses"]:
        if r.get("code") and not CODE_RE.match(r["code"]):
            add("bad_course_code", "courses", r, f"code '{r['code']}' does not match LLLNNN")
        if r["credits"] is None:
            add("non_numeric_credits", "courses", r, f"credits '{r.get('_credits_raw')}' is not numeric")
        elif not 0 < r["credits"] <= 20:
            add("credits_out_of_range", "courses", r, f"credits {r['credits']} out of range")
        if r.get("category") and r["category"] not in CATEGORIES:
            add("bad_enum", "courses", r, f"category '{r['category']}' not in {sorted(CATEGORIES)}")
        if r.get("course_type") and r["course_type"] not in COURSE_TYPES:
            add("bad_enum", "courses", r, f"course_type '{r['course_type']}' not in {sorted(COURSE_TYPES)}")
        if r.get("mode") not in MODES:
            add("bad_enum", "courses", r, f"mode '{r.get('mode')}' not in {sorted(MODES)}")
        if not r["semester_numbers"] or any(not 1 <= s <= 8 for s in r["semester_numbers"]):
            add("bad_semester", "courses", r, f"semester numbers {r['semester_numbers']} missing or outside 1-8")
        if not r.get("_has_block", True):
            add("no_catalogue_entry", "courses", r, "no Course Contents block in the PDF; syllabus unknown", "warning")
        # curriculum table vs course contents
        printed = r.get("_printed_ltpc")
        lt = parse_ltpc(r.get("ltp"))
        if r.get("_has_block") and printed and lt:
            if tuple(printed[:3]) != tuple(lt[:3]) or (printed[3] is not None and printed[3] != r["credits"]):
                add("printed_mismatch", "courses", r,
                    f"curriculum table prints {r.get('_printed_ltpc_raw')} but Course Contents says "
                    f"{r['ltp']} / {r['credits']} credits", "warning")
        if r.get("_has_block") and r.get("_printed_title") and title_key(r["_printed_title"]) != title_key(r["title"]):
            add("printed_mismatch", "courses", r,
                f"title printed as '{r['_printed_title']}' in curriculum, '{r['title']}' in Course Contents", "warning")
        if lt and r["credits"] is not None and abs(lt[0] + lt[1] + lt[2] / 2 - r["credits"]) > 1e-9:
            add("credit_formula", "courses", r,
                f"L-T-P {r['ltp']} implies {lt[0] + lt[1] + lt[2] / 2:g} credits, document says {r['credits']}", "warning")
        if not r["syllabus"] and not r["objectives"]:
            add("thin_record", "courses", r, "no syllabus and no objectives", "warning")

    # --- prerequisite graph ------------------------------------------------
    hard = {}
    for r in data["prerequisites"]:
        c, q = r.get("course"), r.get("requires")
        if r.get("kind") not in EDGE_KINDS:
            add("bad_enum", "prerequisites", r, f"kind '{r.get('kind')}' not in {sorted(EDGE_KINDS)}")
        for end, label in ((c, "course"), (q, "requires")):
            if end and end not in courses:
                hint = " (it exists elsewhere in the institute catalogue)" if end in data.get("_institute_index", ()) else ""
                add("missing_prerequisite_course", "prerequisites", r, f"{label} '{end}' is not in the course catalogue{hint}")
        if c and c == q:
            add("self_prerequisite", "prerequisites", r, f"{c} requires itself")
        elif c and q and r.get("kind") == "hard":
            hard.setdefault(c, []).append(q)
    cyc = find_cycle(hard)
    if cyc:
        row = next((r for r in data["prerequisites"] if r["course"] == cyc[0] and r["requires"] == cyc[1]), None)
        add("prerequisite_cycle", "prerequisites", row, "hard prerequisite cycle: " + " -> ".join(cyc))

    # --- skills & links ----------------------------------------------------
    parents = {}
    for r in data["skills"]:
        if r.get("level") and r["level"] not in SKILL_LEVELS:
            add("bad_enum", "skills", r, f"level '{r['level']}' not in {sorted(SKILL_LEVELS)}")
        p = r.get("parent_skill")
        if p:
            if p not in skills:
                add("dangling_reference", "skills", r, f"parent_skill '{p}' does not exist")
            parents[r["id"]] = [p]
    cyc = find_cycle(parents)
    if cyc:
        add("skill_parent_cycle", "skills", None, "skill parent cycle: " + " -> ".join(cyc))
    for entity, a, pool_a, field in (("course_skills", "course", courses, "depth"),
                                     ("resource_skills", "resource", resources, "level")):
        for r in data[entity]:
            if r.get(a) and r[a] not in pool_a:
                add("dangling_reference", entity, r, f"{a} '{r[a]}' does not exist")
            if r.get("skill") and r["skill"] not in skills:
                add("dangling_reference", entity, r, f"skill '{r['skill']}' does not exist")
            if r.get(field) not in DEPTHS:
                add("bad_enum", entity, r, f"{field} '{r.get(field)}' not in {sorted(DEPTHS)}")

    # --- rules / resources / modules ---------------------------------------
    for r in data["rules"]:
        if r["numeric_limit"] is None and r.get("_limit_raw"):
            add("non_numeric_limit", "rules", r, f"numeric_limit '{r['_limit_raw']}' is not numeric")
    for r in data["resources"]:
        if not r.get("licence"):
            add("missing_licence", "resources", r, "no licence recorded")
        if r["duration_hours"] is None and r.get("_duration_raw"):
            add("bad_duration", "resources", r, f"duration '{r['_duration_raw']}' is not numeric")
        if not r["description"]:
            add("thin_record", "resources", r, "no description to chunk", "warning")
    for r in data["modules"]:
        pool = courses if r.get("parent_type") == "course" else resources
        if r.get("parent_id") and r["parent_id"] not in pool:
            add("dangling_reference", "modules", r, f"parent '{r['parent_id']}' is not a known {r.get('parent_type')}")
        if r["order"] is None:
            add("missing_required_field", "modules", r, f"order '{r.get('_order_raw')}' is not numeric")

    # --- cross-checks against the programme's own rules --------------------
    limits = {r["id"]: r["numeric_limit"] for r in data["rules"]}
    for cat in ("PL", "PC"):        # IC is only partly in scope (see README)
        need = limits.get(f"DSAI-MIN-CREDITS-{cat}")
        have = sum(c["credits"] or 0 for c in data["courses"] if c.get("category") == cat)
        if need is not None and abs(have - need) > 1e-9:
            add("category_total", "courses", None,
                f"{cat} courses in catalogue sum to {have:g} credits; rule DSAI-MIN-CREDITS-{cat} says {need:g}", "warning")
    for a in data.get("_applied_issues", []):
        add("known_issue_applied", "courses", None,
            f"{a['action']} {a['code']}{'->' + a['target'] if a.get('target') else ''} ({a['where']}): {a.get('reason', '')}",
            "warning")

    for entity in ("courses", "rules", "resources"):
        if not data[entity]:
            add("empty_entity", entity, None, f"no {entity} found under the raw folder")
    if len(data["courses"]) < 15:
        add("below_brief_minimum", "courses", None, f"{len(data['courses'])} courses (< 15 required)", "warning")
    if len(data["resources"]) < 30:
        add("below_brief_minimum", "resources", None, f"{len(data['resources'])} resources (< 30 required)", "warning")
    return issues


def run(data: dict) -> list[dict]:
    issues = validate(data)
    errors = [i for i in issues if i["severity"] == "error"]
    print(f"[validate] {len(CHECKS)} checks run -> {len(errors)} error(s), {len(issues) - len(errors)} warning(s)")
    for i in issues:
        tag = "ERROR  " if i["severity"] == "error" else "warning"
        print(f"  {tag} [{i['check']}] {i['entity']}:{i['id']} ({i['where']}) {i['message']}")
    return issues
