#!/usr/bin/env python3
"""Upload an immutable H2 tutorial package through an existing SSH alias."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REMOTE_BASE = "/workspace/vla-relcomp-h2/tutorial"
EXCLUDES = ("__pycache__/", "*.pyc", ".DS_Store")


def safe_tutorial_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved in {Path("/"), Path.home().resolve()} or len(resolved.parts) < 4:
        raise ValueError(f"unsafe tutorial root: {resolved}")
    required = (resolved / "README.md", resolved / "scripts" / "h2_validate_package.py")
    if not all(item.is_file() for item in required):
        raise ValueError("tutorial root is missing H2 package markers")
    return resolved


def safe_label(value: str, name: str) -> str:
    if not SAFE_LABEL.fullmatch(value):
        raise ValueError(f"{name} must be a short SSH-safe label")
    return value


def local_inventory(root: Path) -> tuple[int, int]:
    count = 0
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if path.name == ".DS_Store" or path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        count += 1
        total += path.stat().st_size
    return count, total


def command_plan(host: str, root: Path, package_id: str) -> tuple[str, list[list[str]]]:
    destination = f"{REMOTE_BASE}/{package_id}/VLA-RelComp_教程"
    parent = f"{REMOTE_BASE}/{package_id}"
    excludes = [item for pattern in EXCLUDES for item in ("--exclude", pattern)]
    upload = ["rsync", "-a", "--safe-links", *excludes, f"{root}/", f"{host}:{destination}/"]
    verify = ["rsync", "-aicn", "--delete", "--safe-links", *excludes, f"{root}/", f"{host}:{destination}/"]
    return destination, [
        ["ssh", host, "test", "-e", destination],
        ["ssh", host, "mkdir", "-p", parent],
        upload,
        verify,
    ]


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, check=False)


def execute(plan: list[list[str]]) -> None:
    for executable in ("ssh", "rsync"):
        if not shutil.which(executable):
            raise ValueError(f"missing local executable: {executable}")
    exists = run(plan[0])
    if exists.returncode == 0:
        raise ValueError("remote destination already exists; choose a new package id")
    if exists.returncode != 1:
        raise ValueError(f"cannot inspect remote destination: {exists.stderr.strip()}")
    make_parent = run(plan[1])
    if make_parent.returncode != 0:
        raise ValueError(f"cannot create remote package parent: {make_parent.stderr.strip()}")
    upload = run(plan[2])
    if upload.returncode != 0:
        raise ValueError(f"rsync upload failed: {upload.stderr.strip()}")
    verify = run(plan[3])
    if verify.returncode != 0:
        raise ValueError(f"rsync checksum verification failed: {verify.stderr.strip()}")
    if verify.stdout.strip():
        raise ValueError(f"remote package differs after upload: {verify.stdout.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="Existing SSH config alias, not a password or raw option")
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--tutorial-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--acknowledge-remote-write", action="store_true")
    args = parser.parse_args()
    try:
        host = safe_label(args.host, "host")
        package_id = safe_label(args.package_id, "package id")
        root = safe_tutorial_root(args.tutorial_root)
        destination, plan = command_plan(host, root, package_id)
        count, total = local_inventory(root)
        if args.execute:
            if not args.acknowledge_remote_write:
                raise ValueError("--execute requires --acknowledge-remote-write")
            execute(plan)
            status = "uploaded_and_checksum_verified"
        else:
            status = "dry_run_no_remote_write"
        payload = {
            "status": status,
            "host_alias": host,
            "package_id": package_id,
            "tutorial_root": str(root),
            "remote_destination": destination,
            "local_files": count,
            "local_bytes": total,
            "commands": plan,
            "claim_boundary": "Dry-run does not contact SSH. Execute writes only a new versioned destination and refuses overwrite.",
        }
    except ValueError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
