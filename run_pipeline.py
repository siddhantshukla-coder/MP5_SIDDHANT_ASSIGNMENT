#!/usr/bin/env python3
"""One command: raw files -> validated, chunked, metadata-rich seed data (stops before embeddings).

    python run_pipeline.py                 # full DSAI run on data/raw -> data/processed
    python run_pipeline.py --sample        # small sample in tests/fixtures/sample
    python run_pipeline.py --raw X --out Y # any other raw folder
    python run_pipeline.py --strict        # treat warnings as errors

Exit code 0 = success, 1 = validation failed (nothing is exported).
No embedding or LLM API is called anywhere in this pipeline.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline import chunk, export, ingest, parse, validate
from pipeline.common import ROOT


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):        # Windows consoles: never crash on a non-ASCII title
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "processed")
    ap.add_argument("--sample", action="store_true", help="run on tests/fixtures/sample")
    ap.add_argument("--strict", action="store_true", help="warnings also fail the run")
    a = ap.parse_args(argv)
    if a.sample:
        a.raw, a.out = ROOT / "tests" / "fixtures" / "sample" / "raw", ROOT / "tests" / "fixtures" / "sample" / "processed"
    if not a.raw.is_dir():
        print(f"ERROR: raw folder not found: {a.raw}")
        return 1
    interim = a.raw.parent / "interim"

    raw_manifest = ingest.run(a.raw)                         # 1. ingest
    data = parse.run(a.raw, interim)                         # 2. parse & normalise
    issues = validate.run(data)                              # 3. validate
    errors = [i for i in issues if i["severity"] == "error" or a.strict]
    if errors:
        print(f"\nFAILED: {len(errors)} problem(s) - fix data/raw (or record a decision in "
              f"manual/known_issues.csv) and re-run. Nothing was exported.")
        return 1
    chunks = chunk.run(data)                                 # 4. chunk
    manifest = export.run(data, chunks, issues, a.out, raw_manifest)   # 5. export
    print("\nOK " + ", ".join(f"{k}={v}" for k, v in manifest["counts"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
