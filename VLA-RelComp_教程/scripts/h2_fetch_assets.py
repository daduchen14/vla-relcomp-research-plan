#!/usr/bin/env python3
"""Plan, download and verify only the two allowlisted H2 model assets."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


MAX_ASSET_BYTES = 20 * 1024**3
ASSET_MAP = {
    "smolvla": "VLA-Arena/smolvla-vla-arena",
    "openvla": "VLA-Arena/openvla-7b-finetuned-vla-arena",
}
ALLOW_PATTERNS = {"smolvla": ["pretrained_model/*"], "openvla": None}
OFFLINE_REQUIRED = {
    "smolvla": {"pretrained_model/config.json", "pretrained_model/model.safetensors"},
    "openvla": {
        "config.json", "model.safetensors.index.json", "model-00001-of-00004.safetensors",
        "model-00002-of-00004.safetensors", "model-00003-of-00004.safetensors",
        "model-00004-of-00004.safetensors", "tokenizer.model", "tokenizer_config.json",
        "preprocessor_config.json", "processor_config.json", "configuration_prismatic.py",
        "modeling_prismatic.py", "processing_prismatic.py",
    },
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


def official_metadata(asset: str, repo: str, revision: str, fixture: Path | None) -> dict[str, object]:
    if fixture is not None:
        payload = json.loads(fixture.read_text())
        selected = payload["assets"][asset]
        if selected["repo"] != repo or selected["revision"] != revision:
            raise ValueError("metadata fixture does not match locked repo/revision")
        return {**selected, "metadata_source": str(fixture.resolve()), "metadata_fixture": True}
    from huggingface_hub import HfApi
    info = HfApi().model_info(repo_id=repo, revision=revision, files_metadata=True)
    files = []
    for sibling in info.siblings:
        size = getattr(sibling, "size", None)
        if size is None:
            raise ValueError(f"official metadata lacks size for {sibling.rfilename}")
        lfs = getattr(sibling, "lfs", None)
        sha256 = lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
        files.append({"path": sibling.rfilename, "size": int(size), "sha256": sha256})
    return {
        "repo": repo, "revision": info.sha, "files": files,
        "metadata_source": "HfApi.model_info(files_metadata=True)", "metadata_fixture": False,
    }


def build_download_plan(asset: str, entries: list[dict[str, object]], metadata: dict[str, object]) -> dict[str, object]:
    repo = ASSET_MAP[asset]
    selected_lock = [entry for entry in entries if entry["repo"] == repo]
    if not selected_lock or any(entry["status"] == "not_required" for entry in selected_lock):
        raise ValueError("asset is missing or explicitly not required")
    revisions = {str(entry["revision"]) for entry in selected_lock}
    if len(revisions) != 1 or metadata["revision"] not in revisions:
        raise ValueError("official metadata revision does not equal the single locked revision")
    patterns = ALLOW_PATTERNS[asset]
    remote_files = {
        str(item["path"]): item for item in metadata["files"]
        if patterns is None or any(fnmatch.fnmatch(str(item["path"]), pattern) for pattern in patterns)
    }
    locked_files = {str(entry["path"]): entry for entry in selected_lock}
    if set(remote_files) != set(locked_files):
        raise ValueError(
            f"snapshot selection and lock differ; remote_only={sorted(set(remote_files)-set(locked_files))}; "
            f"lock_only={sorted(set(locked_files)-set(remote_files))}"
        )
    mismatches = [path for path in remote_files if int(remote_files[path]["size"]) != int(locked_files[path]["size"])]
    if mismatches:
        raise ValueError(f"official metadata size differs from lock: {mismatches}")
    hash_mismatches = [
        path for path in remote_files
        if str(locked_files[path]["sha256"]) != "-"
        and remote_files[path].get("sha256") != locked_files[path]["sha256"]
    ]
    if hash_mismatches:
        raise ValueError(f"official metadata sha256 differs from lock: {hash_mismatches}")
    missing_offline = sorted(OFFLINE_REQUIRED[asset] - set(remote_files))
    if missing_offline:
        raise ValueError(f"snapshot is incomplete for offline loading: {missing_offline}")
    actual_bytes = sum(int(item["size"]) for item in remote_files.values())
    if actual_bytes > MAX_ASSET_BYTES:
        raise ValueError(f"official snapshot selection exceeds 20 GiB: {actual_bytes}")
    return {
        "asset": asset, "repo": repo, "revision": next(iter(revisions)),
        "allow_patterns": patterns, "actual_metadata_bytes": actual_bytes,
        "files_selected": len(remote_files), "selected_paths": sorted(remote_files),
        "metadata_source": metadata["metadata_source"], "metadata_fixture": metadata["metadata_fixture"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--asset", choices=tuple(ASSET_MAP), required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--metadata-fixture", type=Path, help="offline validator only; real downloads must query official metadata")
    parser.add_argument("--acknowledge-download", action="store_true")
    args = parser.parse_args()
    entries = read_lock(args.lock)
    repo = ASSET_MAP[args.asset]
    selected = [entry for entry in entries if entry["repo"] == repo]
    if not selected:
        raise SystemExit("asset is absent from lock")
    revision = str(selected[0]["revision"])
    metadata = official_metadata(args.asset, repo, revision, args.metadata_fixture)
    plan = {**build_download_plan(args.asset, entries, metadata), "download": args.acknowledge_download}
    if not args.acknowledge_download:
        print(json.dumps({**plan, "status": "dry_run_no_download"}, ensure_ascii=False, indent=2))
        return 0
    if args.metadata_fixture is not None:
        raise SystemExit("refusing download with fixture metadata; omit --metadata-fixture to query official metadata live")

    from huggingface_hub import snapshot_download

    asset_root = safe_asset_root(args.asset_root)
    target = asset_root / args.asset
    target.mkdir(parents=True, exist_ok=True)
    returned = snapshot_download(repo_id=repo, revision=plan["revision"], local_dir=target, allow_patterns=plan["allow_patterns"])
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
