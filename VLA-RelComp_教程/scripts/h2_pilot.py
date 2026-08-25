#!/usr/bin/env python3
"""Run a 5-task pilot through locked evaluators while recording episode rows."""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from h2_one_episode import (
    ActionAudit,
    EXPECTED_COMMIT,
    MODEL_IDS,
    MODEL_REVISIONS,
    SOURCE_FILES,
    SUITE,
    append_registry,
    parse_simple_yaml,
    peak_vram_mb,
    reset_peak_vram,
    wrapper_commit,
)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)


def static_check(model: str, config: Path, upstream: Path) -> dict[str, object]:
    values = parse_simple_yaml(config)
    head = git(upstream, "rev-parse", "HEAD")
    if head.returncode or head.stdout.strip() != EXPECTED_COMMIT:
        raise ValueError("upstream commit mismatch")
    if git(upstream, "diff", "--quiet").returncode or git(upstream, "diff", "--cached", "--quiet").returncode:
        raise ValueError("upstream has tracked modifications")
    if values.get("task_suite_name") != SUITE:
        raise ValueError("pilot suite mismatch")
    trials = int(values.get("num_trials_per_task", "0"))
    if not 1 <= trials <= 5:
        raise ValueError("pilot trials must be 1..5")
    if trials > 1 and values.get("init_state_selection_mode") != "episode_idx":
        raise ValueError("multi-trial pilot must use deterministic episode_idx init selection")
    source = upstream / SOURCE_FILES[model]
    tree = ast.parse(source.read_text(), filename=str(source))
    symbols = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    if not {"main", "run_task", "run_episode", "load_initial_states", "setup_logging"}.issubset(symbols):
        raise ValueError("locked pilot evaluator interface changed")
    return {
        "status": "static_check_passed_no_episode", "model": model, "suite": SUITE,
        "level": int(values["task_level"]), "trials_per_task": trials, "expected_episodes": 5 * trials,
        "commit": head.stdout.strip(), "config": str(config.resolve()),
    }


def verify_receipt(model: str, values: dict[str, str]) -> None:
    if model == "random":
        return
    model_path = Path(values["policy_path" if model == "smolvla" else "pretrained_checkpoint"]).resolve()
    asset_root = model_path.parents[1] if model == "smolvla" else model_path.parent
    receipt_path = asset_root / "receipts" / f"{model}.json"
    if not receipt_path.is_file():
        raise FileNotFoundError(f"verified asset receipt is missing: {receipt_path}")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("status") != "downloaded_and_verified" or receipt.get("revision") != MODEL_REVISIONS[model]:
        raise ValueError(f"asset receipt revision mismatch: {receipt_path}")


def execute(model: str, config: Path, upstream: Path, run_root: Path) -> int:
    values = parse_simple_yaml(config)
    verify_receipt(model, values)
    if model != "random":
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    run_root = run_root.resolve()
    if run_root in {Path("/"), Path.home().resolve()} or upstream.resolve() in run_root.parents or run_root in upstream.resolve().parents:
        raise ValueError("unsafe or overlapping run root")
    os.chdir(run_root)
    if model == "random":
        from vla_arena.models.random import evaluator as module
    elif model == "smolvla":
        from vla_arena.models.smolvla import evaluator as module
    else:
        from vla_arena.models.openvla import evaluator as module

    context: dict[str, Any] = {"task_id": None, "episode_idx": 0, "init_count": None, "log_path": ""}
    records: list[dict[str, object]] = []
    audit = ActionAudit()
    original_run_task = module.run_task
    original_run_episode = module.run_episode
    original_load_states = module.load_initial_states
    original_setup_logging = module.setup_logging

    def wrapped_setup_logging(*args: Any, **kwargs: Any) -> Any:
        returned = original_setup_logging(*args, **kwargs)
        context["log_path"] = returned[1] or ""
        return returned

    def wrapped_load_states(*args: Any, **kwargs: Any) -> Any:
        returned = original_load_states(*args, **kwargs)
        context["init_count"] = len(returned[0])
        return returned

    def wrapped_run_task(*args: Any, **kwargs: Any) -> Any:
        context["task_id"] = int(args[2])
        context["episode_idx"] = 0
        return original_run_task(*args, **kwargs)

    def wrapped_run_episode(*args: Any, **kwargs: Any) -> Any:
        audit.calls = 0
        audit.all_finite = True
        audit.last_dims.clear()
        reset_peak_vram()
        started = datetime.now(timezone.utc)
        clock = time.monotonic()
        returned = original_run_episode(*args, **kwargs)
        ended = datetime.now(timezone.utc)
        task_id = int(context["task_id"])
        episode_idx = int(context["episode_idx"])
        init_count = int(context["init_count"] or 0)
        mode = values["init_state_selection_mode"]
        base = 0 if mode == "first" else episode_idx
        init_index = (base + int(values.get("init_state_offset", "0"))) % init_count if init_count else None
        task_description = str(args[2])
        success = bool(returned[0])
        exception = ""
        if audit.calls == 0 or not audit.all_finite or audit.last_dims != {7}:
            exception = f"action_audit_failed_or_episode_exception:calls={audit.calls},finite={audit.all_finite},dims={sorted(audit.last_dims)}"
        episode_id = f"{run_root.name}-{model}-l{values['task_level']}-t{task_id}-i{episode_idx}"
        records.append({
            "run_id": run_root.name, "episode_id": episode_id, "ended_utc": ended.isoformat(), "wrapper_commit": wrapper_commit(),
            "model_id": MODEL_IDS[model], "model_revision": MODEL_REVISIONS[model], "task_level": int(values["task_level"]),
            "task_id": task_id, "seed": int(values["seed"]), "init_state_index": init_index,
            "task_description": task_description, "official_goal_success": success, "action_calls": audit.calls,
            "wall_seconds": round(time.monotonic() - clock, 6), "peak_vram_mb": peak_vram_mb(), "video_path": "",
            "log_path": context["log_path"], "result_path": values["result_json_path"], "exception": exception,
        })
        context["episode_idx"] = episode_idx + 1
        return returned

    module.setup_logging = wrapped_setup_logging
    module.load_initial_states = wrapped_load_states
    module.run_task = wrapped_run_task
    module.run_episode = wrapped_run_episode
    if model in {"random", "openvla"}:
        module.get_action = audit.wrap_function(module.get_action)
    else:
        original_initialize = module.initialize_model
        def wrapped_initialize(*args: Any, **kwargs: Any) -> Any:
            policy = original_initialize(*args, **kwargs)
            policy.select_action = audit.wrap_function(policy.select_action)
            return policy
        module.initialize_model = wrapped_initialize

    summary_path = run_root / "results" / f"pilot_wrapper_{model}_l{values['task_level']}_t{values['num_trials_per_task']}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    started_all = datetime.now(timezone.utc)
    error = ""
    try:
        module.main(cfg=config)
        returncode = 0
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        returncode = 3
    registry_errors: list[str] = []
    for record in records:
        try:
            append_registry(run_root, record)
        except Exception as exc:
            registry_errors.append(f"{record['episode_id']}: {type(exc).__name__}: {exc}")
    expected = 5 * int(values["num_trials_per_task"])
    if len(records) != expected or registry_errors:
        returncode = 4
    payload = {
        "evidence_label": "linux_nvidia_real_pilot_if_exit_zero", "model": model, "suite": SUITE,
        "level": int(values["task_level"]), "trials_per_task": int(values["num_trials_per_task"]),
        "expected_episodes": expected, "recorded_episodes": len(records), "started_utc": started_all.isoformat(),
        "ended_utc": datetime.now(timezone.utc).isoformat(), "exception": error, "registry_errors": registry_errors,
        "result_json_path": values["result_json_path"], "log_path": context["log_path"], "returncode": returncode,
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": str(summary_path), "returncode": returncode, "episodes": len(records)}, ensure_ascii=False))
    return returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("random", "smolvla", "openvla"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = static_check(args.model, args.config.resolve(), args.upstream.resolve())
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.run_root is None:
        parser.error("--run-root is required unless --dry-run is used")
    return execute(args.model, args.config.resolve(), args.upstream.resolve(), args.run_root)


if __name__ == "__main__":
    raise SystemExit(main())
