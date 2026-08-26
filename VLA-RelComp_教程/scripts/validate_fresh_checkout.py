#!/usr/bin/env python3
"""Run free tutorial checks from an isolated copy without author-machine paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FORBIDDEN = (
    "/Users/nokian97", "方向筛选/VLA-RelComp_教程", "work/VLA-Arena-upstream",
)


def run(argv: list[str], cwd: Path, expect: int = 0) -> dict[str, object]:
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(argv, cwd=cwd, env=environment, text=True, capture_output=True, check=False)
    if completed.returncode != expect:
        raise AssertionError(
            f"command returned {completed.returncode}, expected {expect}: {argv}\n{completed.stdout}\n{completed.stderr}"
        )
    return {"argv": argv, "returncode": completed.returncode, "stdout": completed.stdout.strip()}


def inventory(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def scan_portability(tutorial: Path) -> None:
    candidates = [tutorial / "README.md", tutorial / "00_课程使用说明与学习地图.md"]
    candidates.extend(sorted(tutorial.glob("day*/README.md")))
    candidates.extend(sorted((tutorial / "h2_preflight").glob("*.md")))
    candidates.extend(
        path for path in sorted((tutorial / "scripts").glob("*.py"))
        if path.name not in {"validate_fresh_checkout.py", "h2_validate_package.py"}
    )
    violations: list[str] = []
    for path in candidates:
        text = path.read_text()
        for forbidden in FORBIDDEN:
            if forbidden in text:
                violations.append(f"{path.relative_to(tutorial)}:{forbidden}")
    if violations:
        raise AssertionError(f"non-portable paths remain: {violations}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    source_repo = args.repo_root.resolve()
    upstream = args.upstream.resolve()
    if not (source_repo / ".git").exists() or not (upstream / ".git").exists():
        raise SystemExit("repo root and locked upstream must be Git checkouts")
    with tempfile.TemporaryDirectory(prefix="vla-relcomp-fresh-") as temporary:
        root = Path(temporary) / "fresh-checkout"
        shutil.copytree(
            source_repo, root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".DS_Store"),
        )
        (root / ".git").mkdir()
        tutorial = root / "VLA-RelComp_教程"
        scan_portability(tutorial)
        before = inventory(tutorial)
        python = sys.executable
        checks = []
        help_scripts = (
            "validate_upstream.py", "h2_prepare_run.py", "h2_checkpoint_state.py", "h2_system_probe.py",
            "h2_one_episode.py", "h2_pilot.py", "h2_c7_runner.py", "h2_pair_oracle_audit.py",
            "analyze_c7.py", "vla_relcomp.py",
        )
        for script in help_scripts:
            checks.append(run([python, str(tutorial / "scripts" / script), "--help"], root))
        checks.append(run([python, str(tutorial / "scripts" / "validate_tutorial.py"), str(tutorial)], root))
        checks.append(run([python, str(tutorial / "scripts" / "validate_upstream.py"), str(upstream)], root))
        checks.append(run([python, str(tutorial / "scripts" / "action_chunk_demo.py")], tutorial))
        checks.append(run([python, str(tutorial / "scripts" / "analyze_registry.py"), str(tutorial / "assets" / "sample_episode_registry.csv")], tutorial))
        checks.append(run([python, str(tutorial / "scripts" / "stage_probe_demo.py"), str(tutorial / "assets" / "sample_trajectory.csv")], tutorial))
        checks.append(run([
            python, str(tutorial / "scripts" / "parse_bddl.py"), "--upstream-root", str(upstream),
            "--output", str(Path(temporary) / "task_manifest.csv"),
        ], tutorial))
        checks.append(run([
            python, str(tutorial / "scripts" / "system_probe.py"),
        ], tutorial))
        checks.append(run([
            python, str(tutorial / "scripts" / "h2_validate_package.py"), str(tutorial), str(upstream),
        ], root))
        setup = run([
            python, str(tutorial / "scripts" / "vla_relcomp.py"), "setup", "--dry-run",
            "--repo-root", str(root), "--tutorial-root", str(tutorial), "--upstream", str(root / "upstream" / "VLA-Arena"),
        ], root)
        if "dry_run_no_commands_executed" not in str(setup["stdout"]):
            raise AssertionError("setup dry-run boundary missing")
        after = inventory(tutorial)
        if before != after:
            raise AssertionError("help/read-only tutorial commands changed isolated tutorial files")
        payload = {
            "status": "passed", "isolated_copy": True, "checks": len(checks) + 2,
            "help_scripts": list(help_scripts),
            "claim_boundary": "Free isolated-copy regression; no network, model, simulator, GPU, or Gate claim.",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
