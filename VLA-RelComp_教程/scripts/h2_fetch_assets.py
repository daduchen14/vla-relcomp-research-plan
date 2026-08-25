#!/usr/bin/env python3
"""Plan, download and verify only the two allowlisted H2 model assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


MAX_ASSET_BYTES = 20 * 1024**3
ASSET_MAP = {
    "smolvla": "VLA-Arena/smolvla-vla-arena",
    "openvla": "VLA-Arena/openvla-7b-finetuned-vla-arena",
}


def read_lock(path: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("|")
        if len(parts) != 7:
            raise ValueError(f"bad lock row {number}")
        kind, status, repo, revision, size, file_path, sha256 = parts
        entries.append({"kind": kind, "status": status, "repo": repo, "revision": revision, "size": int(size), "path": file_path, "sha256": sha256})
    return entries


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_asset_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved in {Path("/"), Path.home().resolve()} or len(resolved.parts) < 3:
        raise ValueError(f"unsafe asset root: {resolved}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--asset", choices=tuple(ASSET_MAP), required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--acknowledge-download", action="store_true")
    args = parser.parse_args()
    entries = read_lock(args.lock)
    repo = ASSET_MAP[args.asset]
    selected = [entry for entry in entries if entry["repo"] == repo]
    if not selected or any(entry["status"] == "not_required" for entry in selected):
        raise SystemExit("asset is missing or explicitly not required")
    revisions = {entry["revision"] for entry in selected}
    if len(revisions) != 1:
        raise SystemExit("asset lock has multiple revisions")
    expected_bytes = sum(int(entry["size"]) for entry in selected)
    if expected_bytes > MAX_ASSET_BYTES:
        raise SystemExit("locked asset exceeds the 20 GiB authorization boundary")
    plan = {"asset": args.asset, "repo": repo, "revision": next(iter(revisions)), "locked_bytes": expected_bytes, "files_checked": len(selected), "download": args.acknowledge_download}
    if not args.acknowledge_download:
        print(json.dumps({**plan, "status": "dry_run_no_download"}, ensure_ascii=False, indent=2))
        return 0

    from huggingface_hub import snapshot_download

    asset_root = safe_asset_root(args.asset_root)
    target = asset_root / args.asset
    target.mkdir(parents=True, exist_ok=True)
    allow_patterns = ["pretrained_model/*"] if args.asset == "smolvla" else None
    returned = snapshot_download(repo_id=repo, revision=plan["revision"], local_dir=target, allow_patterns=allow_patterns)
    verified: list[dict[str, object]] = []
    for entry in selected:
        file_path = target / str(entry["path"])
        if not file_path.is_file():
            raise SystemExit(f"missing locked file: {file_path}")
        actual_size = file_path.stat().st_size
        if actual_size != entry["size"]:
            raise SystemExit(f"size mismatch: {file_path}: {actual_size} != {entry['size']}")
        expected_sha = str(entry["sha256"])
        actual_sha = sha256_file(file_path) if expected_sha != "-" else None
        if actual_sha is not None and actual_sha != expected_sha:
            raise SystemExit(f"sha256 mismatch: {file_path}")
        verified.append({"path": str(file_path), "size": actual_size, "sha256": actual_sha})
    receipt_dir = asset_root / "receipts"
    receipt_dir.mkdir(exist_ok=True)
    receipt = {**plan, "status": "downloaded_and_verified", "returned_snapshot": str(returned), "verified_utc": datetime.now(timezone.utc).isoformat(), "verified": verified}
    receipt_path = receipt_dir / f"{args.asset}.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"receipt": str(receipt_path), "status": receipt["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
