#!/usr/bin/env python3
"""Run a 5-task pilot through locked evaluators while recording episode rows."""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from h2_one_episode import (
    ActionAudit,
    EpisodeErrorCapture,
    EXPECTED_COMMIT,
    MODEL_IDS,
    MODEL_REVISIONS,
    SOURCE_FILES,
    SUITE,
    append_registry,
    parse_simple_yaml,
    peak_vram_mb,
    reset_peak_vram,
    save_video,
    wrapper_commit,
)


EXPECTED_SIGNATURES = {
    "random": {
        "run_task": ["cfg", "task_suite", "task_id", "task_level", "rng", "total_episodes", "total_successes", "log_file"],
        "run_episode": ["cfg", "env", "task_description", "rng", "initial_state", "log_file"],
    },
    "smolvla": {
        "run_task": ["cfg", "task_suite", "task_id", "task_level", "policy", "replacements_dict", "suite_name", "max_steps", "total_episodes", "total_successes", "log_file"],
        "run_episode": ["cfg", "env", "task_description", "policy", "replacements_dict", "suite_name", "max_steps", "initial_state", "log_file"],
    },
    "openvla": {
        "run_task": ["cfg", "task_suite", "task_id", "task_level", "model", "resize_size", "replacements_dict", "processor", "total_episodes", "total_successes", "log_file"],
        "run_episode": ["cfg", "env", "task_description", "model", "resize_size", "replacements_dict", "processor", "initial_state", "log_file"],
    },
}


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
    if values.get("save_video_mode") != "none":
        raise ValueError("pilot requires save_video_mode: none; wrapper owns one deterministic video per registry row")
    source = upstream / SOURCE_FILES[model]
    tree = ast.parse(source.read_text(), filename=str(source))
    symbols = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    if not {"main", "run_task", "run_episode", "load_initial_states", "setup_logging"}.issubset(symbols):
        raise ValueError("locked pilot evaluator interface changed")
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name, expected in EXPECTED_SIGNATURES[model].items():
        observed = [argument.arg for argument in functions[name].args.args]
        if observed != expected:
            raise ValueError(f"locked {model} {name} signature changed: {observed}")
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


def episode_video_path(run_root: Path, model: str, level: int, task_id: int, init_index: int | None, episode_idx: int) -> Path:
    init_label = "none" if init_index is None else str(init_index)
    return run_root / "videos" / "pilot" / model / f"l{level}" / f"task_{task_id}" / f"init_{init_label}_episode_{episode_idx}.mp4"


def write_episode_video(frames: Any, path: Path, writer: Callable[[Any, Path], int] = save_video) -> tuple[str, str, int]:
    """Write one deterministic video and fail closed on empty/missing output."""
    if path.exists():
        return "", "video_evidence_failed:path_already_exists", 0
    try:
        frame_count = writer(frames, path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        return "", f"video_write_failed:{type(exc).__name__}:{exc}", 0
    if frame_count <= 0:
        return "", "video_evidence_failed:empty_frames", frame_count
    if not path.is_file() or path.stat().st_size <= 0:
        return "", "video_evidence_failed:missing_or_empty_file", frame_count
    return str(path), "", frame_count


def pilot_outcome(expected: int, records: list[dict[str, object]], registry_errors: list[str], evaluator_error: str) -> tuple[int, list[str]]:
    episode_failures = [f"{record['episode_id']}: {record['exception']}" for record in records if record.get("exception")]
    if evaluator_error:
        return 3, episode_failures
    if len(records) != expected or registry_errors or episode_failures:
        return 4, episode_failures
    return 0, []


def action_evidence_errors(audit: ActionAudit, swallowed_errors: list[str]) -> list[str]:
    errors: list[str] = []
    if audit.calls == 0 or not audit.all_finite or audit.last_dims != {7}:
        errors.append(f"action_audit_failed_or_episode_exception:calls={audit.calls},finite={audit.all_finite},dims={sorted(audit.last_dims)}")
    if swallowed_errors:
        errors.append("evaluator_swallowed_episode_exception:" + " | ".join(swallowed_errors))
    return errors


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
    episode_error_capture = EpisodeErrorCapture()
    original_run_task = module.run_task
    original_run_episode = module.run_episode
    original_load_states = module.load_initial_states
    original_setup_logging = module.setup_logging

    def wrapped_setup_logging(*args: Any, **kwargs: Any) -> Any:
        returned = original_setup_logging(*args, **kwargs)
        if not isinstance(returned, tuple) or len(returned) != 3:
            raise RuntimeError("locked setup_logging return contract changed")
        context["log_path"] = returned[1] or ""
        return returned

    def wrapped_load_states(*args: Any, **kwargs: Any) -> Any:
        returned = original_load_states(*args, **kwargs)
        if not isinstance(returned, tuple) or len(returned) != 2:
            raise RuntimeError("locked load_initial_states return contract changed")
        context["init_count"] = len(returned[0])
        return returned

    def wrapped_run_task(*args: Any, **kwargs: Any) -> Any:
        bound = inspect.signature(original_run_task).bind(*args, **kwargs)
        context["task_id"] = int(bound.arguments["task_id"])
        context["episode_idx"] = 0
        return original_run_task(*args, **kwargs)

    def wrapped_run_episode(*args: Any, **kwargs: Any) -> Any:
        audit.calls = 0
        audit.all_finite = True
        audit.last_dims.clear()
        reset_peak_vram()
        started = datetime.now(timezone.utc)
        clock = time.monotonic()
        episode_error_capture.begin()
        try:
            returned = original_run_episode(*args, **kwargs)
        finally:
            episode_error_capture.end()
        ended = datetime.now(timezone.utc)
        if not isinstance(returned, tuple) or len(returned) != 3:
            raise RuntimeError("locked run_episode return contract changed")
        bound = inspect.signature(original_run_episode).bind(*args, **kwargs)
        task_id = int(context["task_id"])
        episode_idx = int(context["episode_idx"])
        init_count = int(context["init_count"] or 0)
        mode = values["init_state_selection_mode"]
        base = 0 if mode == "first" else episode_idx
        init_index = (base + int(values.get("init_state_offset", "0"))) % init_count if init_count else None
        task_description = str(bound.arguments["task_description"])
        success = bool(returned[0])
        evidence_errors = action_evidence_errors(audit, episode_error_capture.errors)
        episode_id = f"{run_root.name}-{model}-l{values['task_level']}-t{task_id}-i{episode_idx}"
        video_path = episode_video_path(run_root, model, int(values["task_level"]), task_id, init_index, episode_idx)
        saved_video, video_error, frame_count = write_episode_video(returned[1], video_path)
        if video_error:
            evidence_errors.append(video_error)
        records.append({
            "run_id": run_root.name, "episode_id": episode_id, "ended_utc": ended.isoformat(), "wrapper_commit": wrapper_commit(),
            "model_id": MODEL_IDS[model], "model_revision": MODEL_REVISIONS[model], "task_level": int(values["task_level"]),
            "task_id": task_id, "seed": int(values["seed"]), "init_state_index": init_index,
            "task_description": task_description, "official_goal_success": success, "action_calls": audit.calls,
            "wall_seconds": round(time.monotonic() - clock, 6), "peak_vram_mb": peak_vram_mb(), "video_path": saved_video,
            "video_frames": frame_count, "log_path": context["log_path"], "result_path": values["result_json_path"],
            "exception": ";".join(evidence_errors),
        })
        context["episode_idx"] = episode_idx + 1
        return returned

    module.setup_logging = wrapped_setup_logging
    module.log_message = episode_error_capture.wrap(module.log_message)
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
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    registry_errors: list[str] = []
    for record in records:
        try:
            append_registry(run_root, record)
        except Exception as exc:
            registry_errors.append(f"{record['episode_id']}: {type(exc).__name__}: {exc}")
    expected = 5 * int(values["num_trials_per_task"])
    returncode, episode_failures = pilot_outcome(expected, records, registry_errors, error)
    payload = {
        "evidence_label": "linux_nvidia_real_pilot_if_exit_zero", "model": model, "suite": SUITE,
        "level": int(values["task_level"]), "trials_per_task": int(values["num_trials_per_task"]),
        "expected_episodes": expected, "recorded_episodes": len(records), "started_utc": started_all.isoformat(),
        "ended_utc": datetime.now(timezone.utc).isoformat(), "exception": error, "registry_errors": registry_errors,
        "episode_evidence_failures": episode_failures,
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
