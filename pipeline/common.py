from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_VERSION = "1.0.0"

# ---- controlled vocabularies -------------------------------------------------
SOURCE_TYPES = {"official", "open-licence", "manual"}
ENTRY_METHODS = {"pdf-extract", "manual-transcription", "manual-curation"}
CATEGORIES = {"IC", "PL", "PC", "PE", "OE", "LA"}           # IIT Bhilai course categories
CATEGORY_TO_TYPE = {"IC": "core", "PL": "core", "PC": "core", "PE": "elective", "OE": "open", "LA": "open"}
COURSE_TYPES = {"core", "elective", "open"}
MODES = {"theory", "lab", "theory+lab", "project", "online", "discussion", "other"}
EDGE_KINDS = {"hard", "recommended"}
DEPTHS = {"intro", "working", "advanced"}          # course_skill.depth, resource_skill.level
SKILL_LEVELS = {"domain", "topic", "skill"}        # position of a node in the skill taxonomy
RULE_CATEGORIES = {"credit-requirement", "credit-load", "prerequisite", "overlap", "course-level",
                   "mooc-credit", "grading", "academic-standing", "honours-minor", "registration",
                   "branch-change"}

# provenance carried by every record
PROV = ["source_url", "retrieved_on", "source_type", "source_locator", "entry_method", "raw_file"]

# ---- final (processed) schema: column order of every output CSV/JSON ---------
SCHEMA = {
    "courses": ["code", "title", "dept", "discipline", "credits", "ltp", "semester_numbers", "term",
                "category", "course_type", "mode", "level", "objectives", "syllabus",
                "prerequisite_text", "overlap_text"] + PROV,
    "prerequisites": ["course", "requires", "kind", "alt_group"] + PROV,
    "course_overlaps": ["course", "other", "percent", "other_in_catalogue"] + PROV,
    "skills": ["id", "name", "level", "parent_skill"] + PROV,
    "course_skills": ["course", "skill", "depth"] + PROV,
    "rules": ["id", "category", "text", "numeric_limit", "unit", "comparator", "applies_to",
              "notes"] + PROV,
    "resources": ["id", "title", "provider", "licence", "licence_url", "format", "duration_hours",
                  "duration_basis", "url", "description"] + PROV,
    "resource_skills": ["resource", "skill", "level"] + PROV,
    "modules": ["id", "parent_id", "parent_type", "order", "title", "summary"] + PROV,
}

CODE_RE = re.compile(r"^[A-Z]{2,4}\d{3}[A-Z]?$")
CODE_TOKEN_RE = re.compile(r"\b([A-Z]{2,3}\d{3})\b")


# ---- IO ----------------------------------------------------------------------
def read_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):  # line 1 is the header
            clean = {(k or "").strip(): (v or "").strip()
                     for k, v in r.items() if k is not None and isinstance(v, (str, type(None)))}
            if any(clean.values()):
                clean["_file"], clean["_line"] = path.name, i
                rows.append(clean)
    return rows


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return ";".join(str(x) for x in v)
    return v


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in rows:
            w.writerow([_cell(r.get(k)) for k in fields])


def write_json(path: Path, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def public(row: dict, fields: list[str]) -> dict:
    """Drop private _fields and order keys by the schema."""
    return {k: row.get(k) for k in fields}


# ---- normalisers (parse stage) -----------------------------------------------
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
MODE_BY_LETTER = {"L": "theory", "P": "lab", "Q": "project", "T": "project", "D": "discussion",
                  "V": "online", "N": "other"}
TITLE_FIXES = {r"\bAl\b": "AI", r"\s*&\s*": " and "}     # PDF artefacts / spelling variants


def norm_ws(s) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def norm_code(s) -> str:
    """'ds 201', 'DS-201', 'DS_201' -> 'DS201'."""
    return re.sub(r"[\s\-_.]+", "", (s or "").upper())


def norm_id(s) -> str:
    """Slug for skill / resource / module ids: 'Linear Algebra' -> 'linear-algebra'."""
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def norm_rule_id(s) -> str:
    return re.sub(r"[\s_]+", "-", (s or "").upper().strip())


def norm_ref(s) -> str:
    """A reference that may be a course code or a slug id."""
    c = norm_code(s)
    return c if CODE_RE.match(c) else norm_id(s)


def norm_title(s) -> str:
    t = norm_ws(s)
    for pat, rep in TITLE_FIXES.items():
        t = re.sub(pat, rep, t)
    return t.title() if t.isupper() and len(t) > 3 else t


def title_key(s) -> str:
    """Loose comparison key: case/punctuation/'of'-'for' insensitive."""
    t = norm_title(s).lower().replace("bigdata", "big data")
    t = re.sub(r"\b(of|for|the|and)\b", " ", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def norm_number(s):
    try:
        v = float(str(s).strip())
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return int(v) if v.is_integer() else v


def parse_ltpc(s):
    """'3-1-0-4' or '3-1-0' -> (L, T, P, C or None); None if unparsable."""
    parts = [norm_number(x) for x in re.split(r"\s*-\s*", (s or "").strip()) if x != ""]
    if len(parts) not in (3, 4) or any(p is None for p in parts):
        return None
    return tuple(parts) if len(parts) == 4 else (*parts, None)


def norm_semesters(s):
    """'Semester III', '3rd', 'S3', '3;5', 'Monsoon 5' -> ([3], term-or-None)."""
    text = (s or "").strip()
    term = next((t.capitalize() for t in ("monsoon", "winter", "summer") if t in text.lower()), None)
    nums = []
    for tok in re.findall(r"[A-Za-z]+|\d+", text):
        if tok.isdigit():
            nums.append(int(tok))
        elif tok.upper() in ROMAN:
            nums.append(ROMAN[tok.upper()])
    nums = sorted(set(nums))
    if term is None and nums:  # IIT Bhilai: odd semesters run Monsoon, even run Winter
        parity = {n % 2 for n in nums}
        term = ("Monsoon" if parity == {1} else "Winter") if len(parity) == 1 else "Monsoon/Winter"
    return nums, term


def norm_choice(s, mapping):
    key = norm_ws(s).lower()
    return mapping.get(key, key)


def norm_date(s):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime((s or "").strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None
