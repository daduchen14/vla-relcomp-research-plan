#!/usr/bin/env python3
"""Create an H2 evidence tree and render project-owned configs."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_COMMIT = "babe582ebffc82b979b77964a7e56417d02f63a4"
SUBDIRS = ("system", "commands", "configs", "logs", "results", "videos", "registry", "hashes", "gates", "patches", "tmp")


def safe_root(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    forbidden = {Path("/"), Path.home().resolve()}
    if resolved in forbidden or len(resolved.parts) < 3:
        raise ValueError(f"unsafe {label}: {resolved}")
    return resolved


def git_output(repo: Path, *args: str) -> str | None:
    if not (repo / ".git").exists():
        return None
    completed = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


def atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def init_run(run_root: Path, upstream: Path, schema: Path) -> None:
    run_root = safe_root(run_root, "run root")
    upstream = upstream.expanduser().resolve()
    if upstream == run_root or upstream in run_root.parents or run_root in upstream.parents:
        raise ValueError("run root and upstream must be separate trees")
    run_root.mkdir(parents=True, exist_ok=True)
    for name in SUBDIRS:
        (run_root / name).mkdir(exist_ok=True)
    manifest_path = run_root / "run_manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        if existing.get("expected_upstream_commit") != EXPECTED_COMMIT:
            raise ValueError("existing run has a different upstream lock")
    else:
        atomic_json(manifest_path, {
            "evidence_label": "linux_nvidia_pending",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "run_root": str(run_root),
            "upstream": str(upstream),
            "expected_upstream_commit": EXPECTED_COMMIT,
            "observed_upstream_commit": git_output(upstream, "rev-parse", "HEAD"),
            "claim_boundary": "No episode is implied by directory initialization.",
        })
    state_path = run_root / "checkpoint_state.json"
    if not state_path.exists():
        atomic_json(state_path, {f"C{i}": {"status": "pending", "evidence": []} for i in range(8)})
    registry_path = run_root / "registry" / "episode_registry.csv"
    if not registry_path.exists():
        rows = list(csv.reader(schema.open(newline="")))
        if len(rows) != 1:
            raise ValueError("registry schema must contain exactly one header row")
        with registry_path.open("w", newline="") as handle:
            csv.writer(handle).writerow(rows[0])
    print(run_root)


def render_configs(run_root: Path, upstream: Path, asset_root: Path, templates: Path, level: int, trials: int) -> None:
    run_root = safe_root(run_root, "run root")
    upstream = upstream.expanduser().resolve()
    asset_root = safe_root(asset_root, "asset root")
    templates = templates.expanduser().resolve()
    if not (0 <= level <= 2) or not (1 <= trials <= 10):
        raise ValueError("level must be 0..2 and trials must be 1..10")
    destination = run_root / "configs"
    destination.mkdir(parents=True, exist_ok=True)
    replacements = {
        "__H2_RUN_ROOT__": str(run_root),
        "__H2_UPSTREAM__": str(upstream),
        "__H2_ASSET_ROOT__": str(asset_root),
    }
    for source in sorted(templates.glob("*.yaml")):
        text = source.read_text()
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = text.replace("task_level: 0", f"task_level: {level}")
        text = text.replace("num_trials_per_task: 1", f"num_trials_per_task: {trials}")
        if trials > 1:
            text = text.replace('init_state_selection_mode: "first"', 'init_state_selection_mode: "episode_idx"')
        if "__H2_" in text:
            raise ValueError(f"unresolved placeholder in {source}")
        output = destination / source.name.replace("_l0", f"_l{level}_t{trials}")
        if output.exists():
            raise ValueError(f"refusing to overwrite an existing rendered config: {output}")
        temporary = output.with_suffix(".tmp")
        temporary.write_text(text)
        temporary.replace(output)
        print(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--run-root", type=Path, required=True)
    init_parser.add_argument("--upstream", type=Path, required=True)
    init_parser.add_argument("--schema", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "episode_registry_schema.csv")
    render = subparsers.add_parser("render-configs")
    render.add_argument("--run-root", type=Path, required=True)
    render.add_argument("--upstream", type=Path, required=True)
    render.add_argument("--asset-root", type=Path, required=True)
    render.add_argument("--templates", type=Path, required=True)
    render.add_argument("--level", type=int, default=0)
    render.add_argument("--trials", type=int, default=1)
    args = parser.parse_args()
    if args.command == "init":
        init_run(args.run_root, args.upstream, args.schema)
    else:
        render_configs(args.run_root, args.upstream, args.asset_root, args.templates, args.level, args.trials)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
