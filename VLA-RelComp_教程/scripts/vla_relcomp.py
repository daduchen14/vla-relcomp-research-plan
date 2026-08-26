#!/usr/bin/env python3
"""Read-only command navigator for the VLA-RelComp tutorial and H2 run."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


BASELINE_COMMIT = "fba7a7fc17c240f2f1d2ce5c245bc00704e6efa9"
UPSTREAM_COMMIT = "babe582ebffc82b979b77964a7e56417d02f63a4"
BRANCH = "h2-linux-nvidia-preflight"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], text=True, capture_output=True, check=False,
    )


def resolve_roots(
    repo_root: Path | None, tutorial_root: Path | None, require_repository: bool = True,
) -> tuple[Path, Path]:
    tutorial = (tutorial_root or Path(__file__).resolve().parents[1]).expanduser().resolve()
    repo = (repo_root or tutorial.parent).expanduser().resolve()
    if not (tutorial / "README.md").is_file() or not (tutorial / "scripts" / "h2_validate_package.py").is_file():
        raise ValueError(f"tutorial markers are missing: {tutorial}")
    if require_repository and not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise ValueError(f"repository marker is missing: {repo}")
    if require_repository and tutorial.parent != repo:
        raise ValueError("tutorial root must be VLA-RelComp_教程 directly below repo root")
    return repo, tutorial


def branch_report(repo: Path) -> dict[str, Any]:
    head = git(repo, "rev-parse", "HEAD")
    branch = git(repo, "branch", "--show-current")
    ancestor = git(repo, "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD")
    dirty = git(repo, "status", "--short")
    return {
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "contains_frozen_baseline": ancestor.returncode == 0,
        "working_tree_clean": dirty.returncode == 0 and not dirty.stdout.strip(),
        "status_short": dirty.stdout.splitlines() if dirty.stdout.strip() else [],
    }


def upstream_report(upstream: Path | None) -> dict[str, Any]:
    if upstream is None:
        return {"path": None, "status": "missing", "commit": None, "working_tree_clean": None}
    resolved = upstream.expanduser().resolve()
    if not (resolved / ".git").exists():
        return {"path": str(resolved), "status": "missing", "commit": None, "working_tree_clean": None}
    head = git(resolved, "rev-parse", "HEAD")
    dirty = git(resolved, "status", "--short")
    observed = head.stdout.strip() if head.returncode == 0 else None
    clean = dirty.returncode == 0 and not dirty.stdout.strip()
    return {
        "path": str(resolved), "status": "ready" if observed == UPSTREAM_COMMIT and clean else "mismatch",
        "commit": observed, "working_tree_clean": clean,
    }


def doctor(args: argparse.Namespace) -> int:
    repo, tutorial = resolve_roots(args.repo_root, args.tutorial_root)
    source = upstream_report(args.upstream)
    repo_state = branch_report(repo)
    errors: list[str] = []
    if repo_state["branch"] != BRANCH:
        errors.append(f"expected branch {BRANCH}")
    if not repo_state["contains_frozen_baseline"]:
        errors.append(f"HEAD must contain frozen baseline {BASELINE_COMMIT}")
    if not repo_state["working_tree_clean"]:
        errors.append("working tree is not clean")
    if source["status"] != "ready":
        errors.append("locked VLA-Arena upstream is missing or mismatched")
    payload = {
        "status": "ready" if not errors else "needs_setup",
        "repo_root": str(repo), "tutorial_root": str(tutorial), "repository": repo_state,
        "upstream": source, "tools": {name: shutil.which(name) for name in ("git", "python3", "uv", "ffmpeg")},
        "errors": errors,
        "claim_boundary": "Read-only doctor; no package install, download, simulator, model, GPU kernel, or Gate decision.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def setup_dry_run(args: argparse.Namespace) -> int:
    if not args.dry_run:
        raise ValueError("setup is intentionally plan-only and requires --dry-run")
    repo, tutorial = resolve_roots(args.repo_root, args.tutorial_root)
    upstream = (args.upstream or repo / "upstream" / "VLA-Arena").expanduser().resolve()
    plan = [
        ["git", "-C", str(repo), "switch", BRANCH],
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
        ["git", "clone", "https://github.com/PKU-Alignment/VLA-Arena.git", str(upstream)],
        ["git", "-C", str(upstream), "switch", "--detach", UPSTREAM_COMMIT],
        ["python3", str(tutorial / "scripts" / "validate_upstream.py"), str(upstream)],
        ["python3", str(tutorial / "scripts" / "vla_relcomp.py"), "doctor", "--repo-root", str(repo), "--upstream", str(upstream)],
    ]
    print(json.dumps({
        "status": "dry_run_no_commands_executed", "repo_root": str(repo), "tutorial_root": str(tutorial),
        "upstream": str(upstream), "commands": plan,
        "claim_boundary": "Prints an argv plan only; it does not clone, install, download, create a run, or contact a remote.",
    }, ensure_ascii=False, indent=2))
    return 0


def load_state(run_root: Path) -> tuple[Path, dict[str, dict[str, Any]]]:
    root = run_root.expanduser().resolve()
    state_path = root / "checkpoint_state.json"
    if not state_path.is_file():
        raise ValueError(f"checkpoint state is missing: {state_path}")
    from h2_checkpoint_state import CHECKPOINTS, read_state
    state = read_state(state_path)
    if tuple(state) != CHECKPOINTS:
        raise ValueError("checkpoint order differs from C0-C7")
    return root, state


def next_checkpoint(state: dict[str, dict[str, Any]]) -> str | None:
    for checkpoint in (f"C{index}" for index in range(8)):
        if state[checkpoint]["status"] != "passed" and not (checkpoint == "C5" and state[checkpoint]["status"] == "skipped"):
            return checkpoint
    return None


def state_payload(run_root: Path, state: dict[str, dict[str, Any]], include_resume: bool) -> dict[str, Any]:
    next_id = next_checkpoint(state)
    result: dict[str, Any] = {
        "run_root": str(run_root), "checkpoints": {name: record["status"] for name, record in state.items()},
        "next_checkpoint": next_id, "all_checkpoints_terminal_success": next_id is None,
        "claim_boundary": "Read-only navigation; it never changes checkpoint_state.json or makes a Gate decision.",
    }
    if include_resume:
        if next_id is None:
            result["next_action"] = "finalize_and_human_review"
        elif state[next_id]["status"] == "failed":
            result["next_action"] = "create_new_retry_run; terminal failures cannot be reopened"
        elif state[next_id]["status"] == "running":
            result["next_action"] = f"inspect existing {next_id} command/evidence before any rerun"
        else:
            result["next_action"] = f"follow checkpoint_matrix.md for {next_id}; begin through h2_checkpoint_state.py"
    return result


def status(args: argparse.Namespace, include_resume: bool) -> int:
    run_root, state = load_state(args.run_root)
    print(json.dumps(state_payload(run_root, state, include_resume), ensure_ascii=False, indent=2))
    return 0


def smoke(args: argparse.Namespace) -> int:
    _, tutorial = resolve_roots(args.repo_root, args.tutorial_root, require_repository=False)
    run_root, state = load_state(args.run_root)
    upstream = args.upstream.expanduser().resolve()
    config = args.config.expanduser().resolve()
    mapping = {
        "random": ("C2", "C1", "random", "h2_pilot.py", ["--model", "random"]),
        "smol-one": ("C3", "C2", "smolvla", "h2_one_episode.py", ["--model", "smolvla", "--task-id", "0"]),
        "openvla-one": ("C5", "C4", "openvla", "h2_one_episode.py", ["--model", "openvla", "--task-id", "0"]),
    }
    checkpoint, predecessor, model, script, model_args = mapping[args.kind]
    errors: list[str] = []
    if state[predecessor]["status"] != "passed":
        errors.append(f"{predecessor} must be passed before planning {checkpoint}")
    if state[checkpoint]["status"] != "pending":
        errors.append(f"{checkpoint} must be pending, observed {state[checkpoint]['status']}")
    if not config.is_file():
        errors.append(f"config is missing: {config}")
    source = upstream_report(upstream)
    if source["status"] != "ready":
        errors.append("locked upstream is missing, dirty, or mismatched")
    static_report: dict[str, Any] | None = None
    if not errors:
        if args.kind == "random":
            from h2_pilot import static_check
            static_report = static_check(model, config, upstream)
        else:
            from h2_one_episode import static_check
            static_report = static_check(model, config, upstream, 0)
    command = [
        "python3", str(tutorial / "scripts" / "h2_capture_command.py"),
        "--evidence-dir", str(run_root / "commands" / f"{checkpoint.lower()}-{args.kind}"), "--",
        "uv", "run", "--project", str(upstream / "envs" / ("smolvla" if model in {"random", "smolvla"} else "openvla")), "--frozen",
        "python", str(tutorial / "scripts" / script), *model_args,
        "--config", str(config), "--upstream", str(upstream), "--run-root", str(run_root),
    ]
    payload = {
        "status": "ready_to_request_execution" if not errors else "blocked",
        "checkpoint": checkpoint, "kind": args.kind, "errors": errors, "static_report": static_report,
        "command_not_executed": command,
        "required_transition": f"Use h2_checkpoint_state.py to set {checkpoint} running before a separately authorized execution.",
        "claim_boundary": "This subcommand performs static prerequisite checks and prints argv only; it never runs an episode.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Read-only VLA-RelComp setup and H2 navigation")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("doctor", "setup"):
        command = commands.add_parser(name)
        command.add_argument("--repo-root", type=Path)
        command.add_argument("--tutorial-root", type=Path)
        command.add_argument("--upstream", type=Path)
        if name == "setup":
            command.add_argument("--dry-run", action="store_true")
    for name in ("status", "resume"):
        command = commands.add_parser(name)
        command.add_argument("--run-root", type=Path, required=True)
    command = commands.add_parser("smoke")
    command.add_argument("--kind", choices=("random", "smol-one", "openvla-one"), required=True)
    command.add_argument("--config", type=Path, required=True)
    command.add_argument("--upstream", type=Path, required=True)
    command.add_argument("--run-root", type=Path, required=True)
    command.add_argument("--repo-root", type=Path)
    command.add_argument("--tutorial-root", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "doctor":
            return doctor(args)
        if args.command == "setup":
            return setup_dry_run(args)
        if args.command == "status":
            return status(args, include_resume=False)
        if args.command == "resume":
            return status(args, include_resume=True)
        return smoke(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
