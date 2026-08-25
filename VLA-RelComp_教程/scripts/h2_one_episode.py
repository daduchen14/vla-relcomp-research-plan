#!/usr/bin/env python3
"""Run exactly one locked VLA-Arena episode without modifying upstream files."""

from __future__ import annotations

import argparse
import ast
import csv
import inspect
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPECTED_COMMIT = "babe582ebffc82b979b77964a7e56417d02f63a4"
SUITE = "extrapolation_preposition_combinations"
MODEL_REVISIONS = {
    "random": "none",
    "smolvla": "ef87aa3f97a4feaed69c93b9ed2014bba07acf8a",
    "openvla": "779caf6517b5aeb9ed33882812a0c5f03f48c86e",
}
MODEL_IDS = {
    "random": "random",
    "smolvla": "VLA-Arena/smolvla-vla-arena",
    "openvla": "VLA-Arena/openvla-7b-finetuned-vla-arena",
}
SOURCE_FILES = {
    "random": "vla_arena/models/random/evaluator.py",
    "smolvla": "vla_arena/models/smolvla/evaluator.py",
    "openvla": "vla_arena/models/openvla/evaluator.py",
}
REQUIRED_SYMBOLS = {
    "random": {"EvaluatorConfig", "initialize_model", "load_initial_states", "make_env", "run_episode", "get_action"},
    "smolvla": {"Args", "initialize_model", "load_initial_states", "_get_vla_arena_env", "run_episode", "load_replacements_dict"},
    "openvla": {"GenerateConfig", "validate_config", "initialize_model", "load_initial_states", "get_vla_arena_env", "run_episode", "get_action"},
}


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)


def parse_simple_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def static_check(model: str, config: Path, upstream: Path, task_id: int) -> dict[str, object]:
    upstream = upstream.expanduser().resolve()
    config = config.expanduser().resolve()
    if not (upstream / ".git").exists():
        raise ValueError(f"not a Git checkout: {upstream}")
    head = git(upstream, "rev-parse", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != EXPECTED_COMMIT:
        raise ValueError(f"upstream HEAD mismatch: {head.stdout.strip() or head.stderr.strip()}")
    for diff_args in (("diff", "--quiet"), ("diff", "--cached", "--quiet")):
        if git(upstream, *diff_args).returncode != 0:
            raise ValueError("upstream has tracked modifications")
    if not 0 <= task_id <= 4:
        raise ValueError("task-id must be 0..4 for the frozen suite")
    values = parse_simple_yaml(config)
    if values.get("task_suite_name") != SUITE:
        raise ValueError("config suite does not match the frozen suite")
    if values.get("num_trials_per_task") != "1":
        raise ValueError("one-episode wrapper requires num_trials_per_task: 1")
    if values.get("task_level") not in {"0", "1", "2"}:
        raise ValueError("task_level must be 0..2")
    if "__H2_" in config.read_text():
        raise ValueError("config still contains a template placeholder")
    source = upstream / SOURCE_FILES[model]
    tree = ast.parse(source.read_text(), filename=str(source))
    names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
    missing = sorted(REQUIRED_SYMBOLS[model] - names)
    if missing:
        raise ValueError(f"locked evaluator interface changed; missing: {missing}")
    return {
        "upstream": str(upstream), "commit": head.stdout.strip(), "config": str(config), "model": model,
        "task_id": task_id, "task_level": int(values["task_level"]), "suite": SUITE,
        "interface_symbols": sorted(REQUIRED_SYMBOLS[model]), "status": "static_check_passed_no_episode",
    }


def array_facts(value: Any) -> tuple[bool, int | None]:
    try:
        if hasattr(value, "detach"):
            value = value.detach().cpu().numpy()
        import numpy as np
        array = np.asarray(value)
        return bool(np.isfinite(array).all()), int(array.shape[-1]) if array.ndim else None
    except Exception:
        return False, None


class ActionAudit:
    def __init__(self) -> None:
        self.calls = 0
        self.all_finite = True
        self.last_dims: set[int] = set()

    def observe(self, value: Any) -> Any:
        finite, last_dim = array_facts(value)
        self.calls += 1
        self.all_finite = self.all_finite and finite
        if last_dim is not None:
            self.last_dims.add(last_dim)
        return value

    def wrap_function(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return self.observe(original(*args, **kwargs))
        return wrapped


def save_video(frames: Any, path: Path) -> int:
    import imageio
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with imageio.get_writer(path, fps=30) as writer:
        for frame in frames:
            writer.append_data(frame)
            count += 1
    if count == 0:
        path.unlink(missing_ok=True)
    return count


def peak_vram_mb() -> float | None:
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_reserved() / 1024**2, 3)
    except Exception:
        pass
    return None


def reset_peak_vram() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def append_registry(run_root: Path, result: dict[str, object]) -> None:
    registry = run_root / "registry" / "episode_registry.csv"
    if not registry.exists():
        raise ValueError("registry header is missing; run h2_prepare_run.py init first")
    with registry.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        existing = {row["episode_id"] for row in reader}
    if not fields:
        raise ValueError("registry header is empty")
    if str(result["episode_id"]) in existing:
        raise ValueError(f"duplicate episode_id: {result['episode_id']}")
    row = {field: "" for field in fields}
    row.update({
        "run_id": result["run_id"], "episode_id": result["episode_id"], "timestamp": result["ended_utc"],
        "repo_commit": EXPECTED_COMMIT, "code_commit": result.get("wrapper_commit") or "uncommitted_h2_preflight",
        "model_id": result["model_id"], "model_revision": result["model_revision"], "suite": SUITE,
        "level": result["task_level"], "task_id": result["task_id"], "seed": result["seed"],
        "init_state_index": result.get("init_state_index", ""), "instruction_original": result.get("task_description", ""),
        "instruction_variant": result.get("task_description", ""), "intervention": "none",
        "relation_satisfied": int(bool(result["official_goal_success"])) if result.get("official_goal_success") is not None else "",
        "success": int(bool(result["official_goal_success"])) if result.get("official_goal_success") is not None else "",
        "steps": result.get("action_calls", ""), "wall_seconds": result.get("wall_seconds", ""),
        "peak_vram_mb": result.get("peak_vram_mb") or "", "video_path": result.get("video_path", ""),
        "log_path": result.get("log_path", ""), "result_path": result.get("result_path", ""),
        "exception": result.get("exception", ""),
        "notes": "official success is primary; behavior thresholds remain uncalibrated; action_calls is not guaranteed to equal env steps",
    })
    with registry.open("a", newline="") as handle:
        csv.DictWriter(handle, fieldnames=fields).writerow(row)


def wrapper_commit() -> str | None:
    repo = Path(__file__).resolve().parents[2]
    result = git(repo, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def execute(
    model: str, config_path: Path, upstream: Path, run_root: Path, task_id: int,
    stage_sidecar: Path | None, target_object: str | None, reference_object: str | None, episode_tag: str,
) -> int:
    import numpy as np
    import draccus
    from vla_arena.vla_arena import benchmark
    from vla_arena.vla_arena.utils.eval_init_state import select_init_state_index

    config_values = parse_simple_yaml(config_path)
    run_root = run_root.expanduser().resolve()
    if run_root in {Path("/"), Path.home().resolve()} or upstream.resolve() in run_root.parents or run_root in upstream.resolve().parents:
        raise ValueError("unsafe or overlapping run root")
    run_root.mkdir(parents=True, exist_ok=True)
    os.chdir(run_root)
    run_id = run_root.name
    episode_id = f"{run_id}-{model}-l{config_values['task_level']}-t{task_id}-i0-{episode_tag}"
    result_path = run_root / "results" / f"one_episode_{model}_task{task_id}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    video_path = run_root / "videos" / "one_episode" / f"{episode_id}.mp4"
    stage = "import"
    log_file = None
    log_path: str | None = None
    env = None
    sidecar = None
    audit = ActionAudit()
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    result: dict[str, object] = {
        "evidence_label": "linux_nvidia_real_episode_if_exit_zero", "run_id": run_id, "episode_id": episode_id,
        "model": model, "model_id": MODEL_IDS[model], "model_revision": MODEL_REVISIONS[model], "suite": SUITE,
        "task_id": task_id, "task_level": int(config_values["task_level"]), "seed": int(config_values.get("seed", "0")),
        "wrapper_commit": wrapper_commit(), "started_utc": started.isoformat(), "official_goal_success": None,
        "diagnostic_definition_status": "uncalibrated", "result_path": str(result_path), "video_path": "", "log_path": "",
    }
    try:
        stage = "asset"
        if model != "random":
            model_path = Path(config_values["policy_path" if model == "smolvla" else "pretrained_checkpoint"]).resolve()
            asset_root = model_path.parents[1] if model == "smolvla" else model_path.parent
            receipt_path = asset_root / "receipts" / f"{model}.json"
            if not receipt_path.is_file():
                raise FileNotFoundError(f"verified asset receipt is missing: {receipt_path}")
            receipt = json.loads(receipt_path.read_text())
            if receipt.get("status") != "downloaded_and_verified" or receipt.get("revision") != MODEL_REVISIONS[model]:
                raise ValueError(f"asset receipt does not match the locked revision: {receipt_path}")
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        reset_peak_vram()
        if model == "random":
            from vla_arena.models.random import evaluator as module
            stage = "config"
            cfg = module._parse_cfg(config_path)
            stage = "model_load"
            rng = module.initialize_model(cfg)
            module.get_action = audit.wrap_function(module.get_action)
            replacements = None
            model_object = rng
            processor = None
        elif model == "smolvla":
            from vla_arena.models.smolvla import evaluator as module
            stage = "config"
            cfg = draccus.parse(module.Args, config_path=str(config_path), args=[])
            stage = "model_load"
            model_object = module.initialize_model(cfg)
            original_select = model_object.select_action
            model_object.select_action = audit.wrap_function(original_select)
            replacements = module.load_replacements_dict(cfg, module.logger)
            processor = None
        else:
            from vla_arena.models.openvla import evaluator as module
            stage = "config"
            cfg = draccus.parse(module.GenerateConfig, config_path=str(config_path), args=[])
            module.validate_config(cfg)
            module.set_seed_everywhere(cfg.seed)
            stage = "model_load"
            model_object, processor = module.initialize_model(cfg)
            resize_size = module.get_image_resize_size(cfg)
            module.get_action = audit.wrap_function(module.get_action)
            replacements = module.load_replacements_dict(cfg, module.logger)

        suite_class = benchmark.get_benchmark_dict()[SUITE]
        suite = suite_class()
        task = suite.get_task_by_level_id(cfg.task_level, task_id)
        task_description = task.language[0] if isinstance(task.language, list) else task.language
        stage = "logging"
        log_file, log_path, _ = module.setup_logging(cfg)
        result["log_path"] = log_path or ""
        stage = "environment"
        initial_states, _ = module.load_initial_states(cfg, suite, task_id, cfg.task_level, log_file)
        rng_for_init = np.random.default_rng(cfg.seed)
        init_index = select_init_state_index(
            num_initial_states=len(initial_states), episode_idx=0, selection_mode=cfg.init_state_selection_mode,
            offset=cfg.init_state_offset, offset_random=cfg.init_state_offset_random, rng=rng_for_init,
        )
        initial_state = initial_states[init_index] if init_index is not None else None
        if model == "random":
            env, task_description = module.make_env(task, cfg)
        elif model == "smolvla":
            env, _ = module._get_vla_arena_env(
                task, module.VLA_ARENA_ENV_RESOLUTION, cfg.seed, cfg.add_noise, cfg.randomize_color,
                cfg.adjust_light, cfg.camera_offset,
            )
        else:
            env, _ = module.get_vla_arena_env(
                task, cfg.model_family, resolution=cfg.env_img_res, add_noise=cfg.add_noise,
                camera_offset=cfg.camera_offset, adjust_light=cfg.adjust_light, randomize_color=cfg.randomize_color,
            )
        if stage_sidecar is not None:
            if not target_object or not reference_object:
                raise ValueError("--stage-sidecar requires --target-object and --reference-object")
            from h2_stage_sidecar import ReadOnlyStageSidecar
            sidecar = ReadOnlyStageSidecar(
                env, stage_sidecar, run_id, episode_id, target_object, reference_object,
            )
            sidecar.install()
        stage = "episode"
        if model == "random":
            success, frames, cost = module.run_episode(cfg, env, task_description, model_object, initial_state, log_file)
        elif model == "smolvla":
            max_steps = 600 if SUITE == "long_horizon" and cfg.task_level >= 1 else 300
            success, frames, cost = module.run_episode(
                cfg, env, task_description, model_object, replacements, SUITE, max_steps, initial_state, log_file,
            )
        else:
            success, frames, cost = module.run_episode(
                cfg, env, task_description, model_object, resize_size, replacements, processor, initial_state, log_file,
            )
        stage = "video"
        frame_count = save_video(frames, video_path)
        if frame_count == 0:
            raise RuntimeError("episode returned no video frames")
        if audit.calls == 0 or not audit.all_finite or audit.last_dims != {7}:
            raise RuntimeError(f"action audit failed: calls={audit.calls}, finite={audit.all_finite}, dims={sorted(audit.last_dims)}")
        result.update({
            "official_goal_success": bool(success), "done_reason": "official_success" if success else "timeout_or_official_failure",
            "cost": cost, "task_description": task_description, "seed": cfg.seed, "init_state_index": init_index,
            "action_calls": audit.calls, "action_all_finite": audit.all_finite, "action_last_dims": sorted(audit.last_dims),
            "video_frames": frame_count, "video_path": str(video_path), "peak_vram_mb": peak_vram_mb(), "exception": "",
        })
        returncode = 0
    except Exception as exc:
        result.update({
            "failure_stage": stage, "failure_class": {
            "model_load": "model_load_or_cuda", "environment": "environment_or_render", "episode": "evaluation_or_action",
                "video": "evaluation_io", "config": "config", "import": "dependency", "asset": "asset_provenance",
            }.get(stage, "wrapper_or_evidence"),
            "exception": f"{type(exc).__name__}: {exc}", "peak_vram_mb": peak_vram_mb(),
            "action_calls": audit.calls, "action_all_finite": audit.all_finite, "action_last_dims": sorted(audit.last_dims),
        })
        returncode = 3
    finally:
        if sidecar is not None:
            try:
                sidecar.uninstall()
            except Exception:
                pass
        if env is not None:
            try:
                env.close()
            except Exception:
                pass
        if log_file is not None:
            try:
                log_file.close()
            except Exception:
                pass
        result["ended_utc"] = datetime.now(timezone.utc).isoformat()
        result["wall_seconds"] = round(time.monotonic() - clock, 6)
        temporary = result_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(result_path)
        try:
            append_registry(run_root, result)
        except Exception as registry_exc:
            result["registry_exception"] = f"{type(registry_exc).__name__}: {registry_exc}"
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            returncode = 4
    print(json.dumps({"result": str(result_path), "returncode": returncode}, ensure_ascii=False))
    return returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("random", "smolvla", "openvla"), required=True)
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--stage-sidecar", type=Path)
    parser.add_argument("--target-object")
    parser.add_argument("--reference-object")
    parser.add_argument("--episode-tag", default="c3", choices=("c3", "c6-sidecar", "retry-01", "retry-02"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = static_check(args.model, args.config, args.upstream, args.task_id)
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.run_root is None:
        parser.error("--run-root is required unless --dry-run is used")
    return execute(
        args.model, args.config.resolve(), args.upstream.resolve(), args.run_root, args.task_id,
        args.stage_sidecar, args.target_object, args.reference_object, args.episode_tag,
    )


if __name__ == "__main__":
    raise SystemExit(main())
