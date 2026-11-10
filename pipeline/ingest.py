
from __future__ import annotations

import json
from pathlib import Path

from .common import sha256, write_json

SKIP = {"MANIFEST.json", "README.md"}


def run(raw_dir: Path) -> dict:
    manifest_path = raw_dir / "MANIFEST.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {}) if manifest_path.exists() else {}
    files, changed = {}, []
    for p in sorted(raw_dir.rglob("*")):
        if p.is_file() and p.name not in SKIP:
            rel = p.relative_to(raw_dir).as_posix()
            files[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
            if rel in old and old[rel]["sha256"] != files[rel]["sha256"]:
                changed.append(rel)
    write_json(manifest_path, {"files": files})
    print(f"[ingest] {len(files)} raw files fingerprinted in {raw_dir}")
    for rel in changed:
        print(f"[ingest] WARNING raw file changed since last run: {rel}")
    return {"files": files, "changed": changed}
