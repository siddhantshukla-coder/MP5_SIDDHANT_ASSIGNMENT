
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PAGE_BREAK = "\f"
HEADER_RE = re.compile(r"^\s*([A-Z]{3}\d{3})\s+(\S.*?)\s*$")
CREDITS_RE = re.compile(r"^\s*([\d.]+)\s+Credits?\s*\(\s*([\d.]+\s*-\s*[\d.]+\s*-\s*[\d.]+)\s*\)", re.I)
PREREQ_RE = re.compile(r"^\s*Pre-?requisite\(?s?\)?\s*:\s*(.*)$", re.I)
OVERLAP_RE = re.compile(r"^\s*Overlap(?:ping)?\s+with\s*:\s*(.*)$", re.I)


def pdf_to_text(pdf: Path, cache_dir: Path) -> tuple[str, str]:
    """Return (text with \\f between pages, extractor name). Cached by source sha-independent name."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / (pdf.stem + ".txt")
    if cache.exists() and cache.stat().st_mtime >= pdf.stat().st_mtime:
        return cache.read_text(encoding="utf-8"), "cache"
    try:
        import pypdf  # noqa: WPS433
        reader = pypdf.PdfReader(str(pdf))
        text = PAGE_BREAK.join((p.extract_text() or "") for p in reader.pages)
        how = f"pypdf {pypdf.__version__}"
    except ImportError:
        exe = shutil.which("pdftotext")
        if not exe:
            raise SystemExit("[parse] ERROR: need `pip install pypdf` (or poppler's pdftotext) to read PDFs")
        text = subprocess.run([exe, "-enc", "UTF-8", str(pdf), "-"], check=True,
                              capture_output=True).stdout.decode("utf-8", "replace")
        how = "pdftotext"
    cache.write_text(text, encoding="utf-8")
    return text, how


def load_text(path: Path, cache_dir: Path) -> tuple[str, str]:
    if path.suffix.lower() == ".pdf":
        return pdf_to_text(path, cache_dir)
    return path.read_text(encoding="utf-8"), "text"


def _clean(line: str) -> str:
    # common PDF artefacts: 'Al' for 'AI' in titles, ligatures, stray spaces
    line = line.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("–", "-").replace("—", "-")
    return re.sub(r"[ \t]+", " ", line).strip()


def extract_course_blocks(text: str, start_marker: str = "Course Contents") -> dict[str, dict]:
    """Find every course block after the *last* table-of-contents mention of start_marker."""
    pages = text.split(PAGE_BREAK)
    lines: list[tuple[int, str]] = []
    for pno, page in enumerate(pages, start=1):
        for ln in page.splitlines():
            lines.append((pno, _clean(ln)))
    # skip the table of contents: start at the marker line that is NOT followed by a page number
    start = 0
    for i, (_, ln) in enumerate(lines):
        if ln.startswith(start_marker) and not re.search(r"\d+\s*$", ln):
            start = i
    blocks: dict[str, dict] = {}
    i = start
    while i < len(lines):
        pno, ln = lines[i]
        m = HEADER_RE.match(ln)
        if not m:
            i += 1
            continue
        # title may wrap; the credits line must follow within 3 non-empty lines
        title_parts, j, cred = [m.group(2)], i + 1, None
        while j < len(lines) and j <= i + 4:
            if not lines[j][1]:
                j += 1
                continue
            cm = CREDITS_RE.match(lines[j][1])
            if cm:
                cred = cm
                break
            if HEADER_RE.match(lines[j][1]) or PREREQ_RE.match(lines[j][1]):
                break
            title_parts.append(lines[j][1])
            j += 1
        if not cred:
            i += 1
            continue
        code = m.group(1)
        block = {"code": code, "title": " ".join(title_parts), "credits_raw": cred.group(1),
                 "ltp": re.sub(r"\s+", "", cred.group(2)), "prerequisite_text": "", "overlap_text": "",
                 "syllabus": "", "page": pno}
        body, k = [], j + 1
        while k < len(lines):
            kl = lines[k][1]
            nxt = HEADER_RE.match(kl)
            if nxt and any(CREDITS_RE.match(lines[x][1]) for x in range(k + 1, min(k + 5, len(lines)))):
                break
            if re.match(r"^Courses offered in the Discipline", kl, re.I):
                break
            pm, om = PREREQ_RE.match(kl), OVERLAP_RE.match(kl)
            if pm and not block["prerequisite_text"]:
                block["prerequisite_text"] = pm.group(1)
            elif om and not block["overlap_text"]:
                block["overlap_text"] = om.group(1)
            elif kl and not re.fullmatch(r"\d{1,3}", kl):        # drop bare page numbers
                body.append(kl)
            k += 1
        block["syllabus"] = re.sub(r"\s+", " ", " ".join(body)).strip()
        if code in blocks:                                     # keep the first, record the duplicate
            blocks[code].setdefault("_duplicates", []).append(pno)
        else:
            blocks[code] = block
        i = k
    return blocks
