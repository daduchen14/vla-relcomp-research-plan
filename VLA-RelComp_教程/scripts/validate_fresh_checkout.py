#!/usr/bin/env python3
"""Run free tutorial checks from an isolated copy without author-machine paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FORBIDDEN = (
    "/Users/nokian97", "方向筛选/VLA-RelComp_教程", "work/VLA-Arena-upstream",
)
RELEASE_TAG = "vla-relcomp-h2.5.1"
PRIVATE_CLONE_COMMAND = f"git clone --branch {RELEASE_TAG} --single-branch https://github.com/daduchen14/vla-relcomp-research-plan.git"
UPSTREAM_COMMIT = "babe582ebffc82b979b77964a7e56417d02f63a4"


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
    candidates = [
        tutorial.parent / "README.md", tutorial.parent / "26_教程任务交接说明.md",
        tutorial / "README.md", tutorial / "00_课程使用说明与学习地图.md",
    ]
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
                violations.append(f"{path.relative_to(tutorial.parent)}:{forbidden}")
    if violations:
        raise AssertionError(f"non-portable paths remain: {violations}")
    guide = (tutorial / "h2_preflight" / "fresh_clone_quickstart.md").read_text()
    if PRIVATE_CLONE_COMMAND not in guide:
        raise AssertionError("fresh-clone guide is missing the HTTPS fixed-release-tag command")
    if re.search(r"https://[^/\s:@]+(?::[^@\s/]*)?@github\.com", guide, re.IGNORECASE):
        raise AssertionError("fresh-clone guide embeds credentials in a GitHub HTTPS URL")
    if "SSH 是可选替代，不是默认入口" not in guide:
        raise AssertionError("fresh-clone guide does not mark SSH as optional")


def validate_external_default(
    source_repo: Path, source_tutorial: Path, upstream: Path, temporary: Path, python: str,
) -> list[dict[str, object]]:
    parent = temporary / "portable-parent"
    parent.mkdir()
    project = parent / "vla-relcomp-research-plan"
    run(["git", "clone", "--shared", "--branch", "h2-linux-nvidia-preflight", "--single-branch", str(source_repo), str(project)], temporary)
    shutil.copytree(
        source_tutorial, project / "VLA-RelComp_教程", dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )
    dirty = run(["git", "-C", str(project), "status", "--porcelain"], temporary)
    if str(dirty["stdout"]):
        run(["git", "-C", str(project), "config", "user.name", "VLA-RelComp Fixture"], temporary)
        run(["git", "-C", str(project), "config", "user.email", "fixture@example.invalid"], temporary)
        run(["git", "-C", str(project), "add", "--", "VLA-RelComp_教程"], temporary)
        run(["git", "-C", str(project), "commit", "-m", "fixture: current portability tree"], temporary)
    run(["git", "-C", str(project), "tag", "-f", RELEASE_TAG], temporary)
    tutorial = project / "VLA-RelComp_教程"
    setup = run([
        python, str(tutorial / "scripts" / "vla_relcomp.py"), "setup", "--dry-run", "--repo-root", str(project),
    ], project)
    setup_payload = json.loads(str(setup["stdout"]))
    expected_upstream = (project.parent / "VLA-Arena-upstream").resolve()
    observed_upstream = Path(setup_payload["upstream"])
    if observed_upstream != expected_upstream or project in observed_upstream.parents:
        raise AssertionError("setup default upstream is not the repository-external sibling")
    if run(["git", "-C", str(project), "status", "--porcelain"], temporary)["stdout"]:
        raise AssertionError("setup dry-run dirtied the project checkout")
    run(["git", "clone", "--shared", "--no-checkout", str(upstream), str(expected_upstream)], temporary)
    run(["git", "-C", str(expected_upstream), "switch", "--detach", UPSTREAM_COMMIT], temporary)
    doctor = run([
        python, str(tutorial / "scripts" / "vla_relcomp.py"), "doctor", "--repo-root", str(project),
        "--upstream", str(expected_upstream),
    ], project)
    doctor_payload = json.loads(str(doctor["stdout"]))
    if doctor_payload["status"] != "ready" or not doctor_payload["repository"]["working_tree_clean"]:
        raise AssertionError("external sibling upstream did not preserve a clean, doctor-ready project")
    return [setup, doctor]


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
        external_default_checks = validate_external_default(source_repo, source_repo / "VLA-RelComp_教程", upstream, Path(temporary), python)
        after = inventory(tutorial)
        if before != after:
            raise AssertionError("help/read-only tutorial commands changed isolated tutorial files")
        payload = {
            "status": "passed", "isolated_copy": True, "checks": len(checks) + 2 + len(external_default_checks),
            "help_scripts": list(help_scripts),
            "default_upstream": "repository_external_sibling_doctor_ready",
            "claim_boundary": "Free isolated-copy and local-Git regression; no network, model, simulator, GPU, or Gate claim.",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
