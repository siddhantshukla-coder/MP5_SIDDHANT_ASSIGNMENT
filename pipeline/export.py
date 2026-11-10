
from __future__ import annotations

import json
from pathlib import Path

from .common import PIPELINE_VERSION, SCHEMA, public, sha256, write_csv, write_json


def fill_rates(rows: list[dict], fields: list[str]) -> dict:
    if not rows:
        return {}
    return {f: round(100 * sum(r.get(f) not in (None, "", []) for r in rows) / len(rows), 1) for f in fields}


def run(data: dict, chunks: list[dict], issues: list[dict], out_dir: Path, raw_manifest: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts, fills = {}, {}
    for entity, fields in SCHEMA.items():
        rows = [public(r, fields) for r in data[entity]]
        write_csv(out_dir / f"{entity}.csv", rows, fields)
        write_json(out_dir / f"{entity}.json", rows)
        counts[entity], fills[entity] = len(rows), fill_rates(rows, fields)
    with open(out_dir / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    counts["chunks"] = len(chunks)
    write_json(out_dir / "validation_report.json", issues)
    manifest = {"pipeline_version": PIPELINE_VERSION, "counts": counts, "fill_rate_pct": fills,
                "chunk_types": {t: sum(c["chunk_type"] == t for c in chunks) for t in sorted({c["chunk_type"] for c in chunks})},
                "raw_inputs": raw_manifest.get("files", {}),
                "outputs": {p.name: sha256(p) for p in sorted(out_dir.iterdir())
                            if p.is_file() and p.name != "manifest.json"}}
    write_json(out_dir / "manifest.json", manifest)
    print(f"[export] wrote {len(SCHEMA) * 2 + 3} files to {out_dir}")
    return manifest
