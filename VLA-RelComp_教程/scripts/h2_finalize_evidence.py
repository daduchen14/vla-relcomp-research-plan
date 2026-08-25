#!/usr/bin/env python3
"""Hash an H2 run evidence tree without altering raw evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.expanduser().resolve()
    if root in {Path("/"), Path.home().resolve()} or not (root / "run_manifest.json").is_file():
        raise SystemExit(f"not an initialized H2 run root: {root}")
    registry = root / "registry" / "episode_registry.csv"
    with registry.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    missing_paths: list[str] = []
    for row in rows:
        for key in ("video_path", "log_path", "result_path"):
            value = row.get(key, "")
            if value and not Path(value).is_file():
                missing_paths.append(value)
    hashes_dir = root / "hashes"
    hashes_dir.mkdir(exist_ok=True)
    manifest_path = hashes_dir / "sha256_manifest.json"
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item != manifest_path):
        files.append({"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": digest(path)})
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "run_root": str(root), "files": files,
        "registry_rows": len(rows), "missing_registry_paths": missing_paths,
        "status": "complete" if not missing_paths else "incomplete",
        "claim_boundary": "Hashing verifies file integrity only; it does not validate scientific conclusions.",
    }
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(manifest_path)
    print(json.dumps({"manifest": str(manifest_path), "files": len(files), "registry_rows": len(rows), "missing": len(missing_paths)}, ensure_ascii=False))
    return 0 if not missing_paths else 2


if __name__ == "__main__":
    raise SystemExit(main())
