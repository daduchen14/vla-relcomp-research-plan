#!/usr/bin/env python3
"""Run manifest-bound baseline + privileged language-oracle C7 episodes."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from h2_one_episode import (
    ActionAudit, EpisodeErrorCapture, MODEL_IDS, MODEL_REVISIONS, SUITE, append_registry,
    parse_simple_yaml, peak_vram_mb, reset_peak_vram, static_check, wrapper_commit,
)
from h2_pair_oracle_audit import INTERVENTIONS, load, validate_manifest
from h2_pilot import static_check as pilot_static_check, verify_receipt, write_episode_video


def safe_derived_path(base: Path, *parts: str) -> Path:
    resolved_base = base.resolve()
    candidate = resolved_base.joinpath(*parts).resolve()
    if candidate == resolved_base or resolved_base not in candidate.parents:
        raise ValueError(f"derived evidence path escapes its root: {candidate}")
    return candidate


def with_episode_seed(cfg: Any, seed: int) -> Any:
    episode_cfg = dataclasses.replace(cfg, seed=seed)
    if int(episode_cfg.seed) != seed or episode_cfg is cfg:
        raise ValueError("failed to create an isolated per-episode seed config")
    return episode_cfg


def ensure_c7_registry(run_root: Path, schema: Path) -> Path:
    path = run_root / "registry" / "c7_episode_registry.csv"
    rows = list(csv.reader(schema.open(newline="")))
    if len(rows) != 1:
        raise ValueError("episode registry schema must contain exactly one header")
    if path.exists():
        with path.open(newline="") as handle:
            observed = next(csv.reader(handle), None)
        if observed != rows[0]:
            raise ValueError("existing C7 registry header differs from the locked schema")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        csv.writer(handle).writerow(rows[0])
    return path


def manifest_static_check(model: str, config: Path, upstream: Path, manifest: Path) -> dict[str, object]:
    base = static_check(model, config, upstream, 0)
    pilot_static_check(model, config, upstream)
    report = validate_manifest(manifest, require_ready=True)
    if report["status"] != "passed":
        raise ValueError(f"C7 manifest is not ready: {report['errors']}")
    _, rows = load(manifest)
    values = parse_simple_yaml(config)
    if model not in {"smolvla", "openvla"}:
        raise ValueError("C7 runner supports only the Gate-2 selected SmolVLA or OpenVLA")
    if values.get("use_replacements") != "false" or values.get("save_video_mode") != "none":
        raise ValueError("C7 requires use_replacements:false and wrapper-owned video mode none")
    expected = (MODEL_IDS[model], MODEL_REVISIONS[model], SUITE, values["task_level"])
    for number, row in enumerate(rows, 2):
        observed = (row["model_id"], row["model_revision"], row["suite"], row["level"])
        if observed != expected:
            raise ValueError(f"manifest row {number} model/suite/level differs from config: {observed} != {expected}")
        task_id = int(row["task_id"])
        if not 0 <= task_id <= 4:
            raise ValueError(f"manifest row {number} task_id must be 0..4")
    return {**base, "manifest": str(manifest.resolve()), "pairs": report["pairs"], "expected_episodes": report["expected_registry_rows"], "interventions": list(INTERVENTIONS), "evidence_label": "static_manifest_gate_no_episode"}


def set_episode_seed(model: str, module: Any, seed: int) -> None:
    import numpy as np
    np.random.seed(seed)
    if model == "openvla":
        module.set_seed_everywhere(seed)
    else:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def execute(model: str, config_path: Path, upstream: Path, run_root: Path, manifest_path: Path, schema: Path) -> int:
    import draccus
    from vla_arena.vla_arena import benchmark

    config_values = parse_simple_yaml(config_path)
    verify_receipt(model, config_values)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    run_root = run_root.resolve()
    if run_root in {Path("/"), Path.home().resolve()} or upstream.resolve() in run_root.parents or run_root in upstream.resolve().parents:
        raise ValueError("unsafe or overlapping run root")
    os.chdir(run_root)
    _, manifest_rows = load(manifest_path)
    registry_path = ensure_c7_registry(run_root, schema)
    audit = ActionAudit()
    if model == "smolvla":
        from vla_arena.models.smolvla import evaluator as module
        cfg = draccus.parse(module.Args, config_path=str(config_path), args=[])
        policy = module.initialize_model(cfg)
        policy.select_action = audit.wrap_function(policy.select_action)
        replacements = module.load_replacements_dict(cfg, module.logger)
        processor = resize_size = None
    else:
        from vla_arena.models.openvla import evaluator as module
        cfg = draccus.parse(module.GenerateConfig, config_path=str(config_path), args=[])
        module.validate_config(cfg)
        policy, processor = module.initialize_model(cfg)
        resize_size = module.get_image_resize_size(cfg)
        module.get_action = audit.wrap_function(module.get_action)
        replacements = module.load_replacements_dict(cfg, module.logger)
    log_file, log_path, _ = module.setup_logging(cfg)
    reset_available = callable(getattr(policy, "reset", None))
    if model == "smolvla" and not reset_available:
        raise RuntimeError("SmolVLA policy reset API is missing; refusing stateful paired execution")
    policy_reset_mode = "explicit_reset_each_episode" if reset_available else "locked_openvla_single_action_no_reset_api"
    episode_error_capture = EpisodeErrorCapture()
    module.log_message = episode_error_capture.wrap(module.log_message)
    suite = benchmark.get_benchmark_dict()[SUITE]()
    failures: list[str] = []
    completed = 0
    try:
        for manifest_row in manifest_rows:
            task_id = int(manifest_row["task_id"])
            episode_seed = int(manifest_row["seed"])
            episode_cfg = with_episode_seed(cfg, episode_seed)
            task = suite.get_task_by_level_id(episode_cfg.task_level, task_id)
            official_instruction = task.language[0] if isinstance(task.language, list) else task.language
            if official_instruction != manifest_row["instruction"]:
                failures.append(f"{manifest_row['pair_id']}/{manifest_row['condition']}: manifest instruction differs from locked task")
                continue
            initial_states, _ = module.load_initial_states(episode_cfg, suite, task_id, episode_cfg.task_level, log_file)
            init_index = int(manifest_row["init_state_index"])
            if not 0 <= init_index < len(initial_states):
                failures.append(f"{manifest_row['pair_id']}/{manifest_row['condition']}: init_state_index out of range")
                continue
            initial_state = initial_states[init_index]
            for intervention in INTERVENTIONS:
                episode_instruction = official_instruction if intervention == "none" else manifest_row["language_oracle_instruction"]
                episode_id = f"{run_root.name}-c7-{manifest_row['pair_id']}-{manifest_row['condition']}-{intervention}"
                result_path = safe_derived_path(run_root / "results" / "c7", manifest_row["pair_id"], manifest_row["condition"], f"{intervention}.json")
                video_path = safe_derived_path(run_root / "videos" / "c7", manifest_row["pair_id"], manifest_row["condition"], f"{intervention}.mp4")
                if result_path.exists() or video_path.exists():
                    failures.append(f"{episode_id}: refusing to overwrite existing result/video evidence")
                    continue
                result_path.parent.mkdir(parents=True, exist_ok=True)
                env = None
                audit.calls, audit.all_finite = 0, True
                audit.last_dims.clear()
                episode_error_capture.begin()
                reset_peak_vram()
                started = datetime.now(timezone.utc)
                clock = time.monotonic()
                result: dict[str, object] = {
                    "evidence_label": "linux_nvidia_real_privileged_c7_if_exit_zero", "run_id": run_root.name,
                    "episode_id": episode_id, "wrapper_commit": wrapper_commit(), "model_id": MODEL_IDS[model],
                    "model_revision": MODEL_REVISIONS[model], "task_level": episode_cfg.task_level, "task_id": task_id,
                    "seed": episode_seed, "init_state_index": init_index, "pair_family": manifest_row["pair_family"], "pair_id": manifest_row["pair_id"],
                    "condition": manifest_row["condition"], "changed_factor": manifest_row["changed_factor"],
                    "task_description": official_instruction, "instruction_variant": episode_instruction,
                    "intervention": intervention, "target_object": manifest_row["target_object"],
                    "reference_object": manifest_row["reference_object"], "relation": manifest_row["relation"],
                    "started_utc": started.isoformat(), "official_goal_success": None, "video_path": "",
                    "log_path": log_path or "", "result_path": str(result_path),
                    "privileged_diagnostic": True, "final_method_eligible": False,
                    "policy_reset_mode": policy_reset_mode,
                }
                try:
                    set_episode_seed(model, module, episode_seed)
                    reset_method = getattr(policy, "reset", None)
                    if callable(reset_method):
                        reset_method()
                    if model == "smolvla":
                        env, _ = module._get_vla_arena_env(task, module.VLA_ARENA_ENV_RESOLUTION, episode_cfg.seed, episode_cfg.add_noise, episode_cfg.randomize_color, episode_cfg.adjust_light, episode_cfg.camera_offset)
                        max_steps = 600 if SUITE == "long_horizon" and episode_cfg.task_level >= 1 else 300
                        returned = module.run_episode(episode_cfg, env, episode_instruction, policy, replacements, SUITE, max_steps, initial_state, log_file)
                    else:
                        env, _ = module.get_vla_arena_env(task, episode_cfg.model_family, resolution=episode_cfg.env_img_res, add_noise=episode_cfg.add_noise, camera_offset=episode_cfg.camera_offset, adjust_light=episode_cfg.adjust_light, randomize_color=episode_cfg.randomize_color)
                        returned = module.run_episode(episode_cfg, env, episode_instruction, policy, resize_size, replacements, processor, initial_state, log_file)
                    if not isinstance(returned, tuple) or len(returned) != 3:
                        raise RuntimeError("locked run_episode return contract changed")
                    episode_error_capture.end()
                    if episode_error_capture.errors:
                        raise RuntimeError("evaluator swallowed episode exception: " + " | ".join(episode_error_capture.errors))
                    success, frames, cost = returned
                    saved_video, video_error, frame_count = write_episode_video(frames, video_path)
                    if video_error:
                        raise RuntimeError(video_error)
                    if audit.calls == 0 or not audit.all_finite or audit.last_dims != {7}:
                        raise RuntimeError(f"action audit failed: calls={audit.calls}, finite={audit.all_finite}, dims={sorted(audit.last_dims)}")
                    result.update({"official_goal_success": bool(success), "cost": cost, "action_calls": audit.calls, "video_frames": frame_count, "video_path": saved_video, "exception": ""})
                except Exception as exc:
                    episode_error_capture.end()
                    result.update({"exception": f"{type(exc).__name__}: {exc}", "action_calls": audit.calls})
                    failures.append(f"{episode_id}: {result['exception']}")
                finally:
                    if env is not None:
                        try:
                            env.close()
                        except Exception:
                            pass
                    result["ended_utc"] = datetime.now(timezone.utc).isoformat()
                    result["wall_seconds"] = round(time.monotonic() - clock, 6)
                    result["peak_vram_mb"] = peak_vram_mb()
                    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
                    try:
                        append_registry(run_root, result, registry_path)
                    except Exception as exc:
                        failures.append(f"{episode_id}: registry:{type(exc).__name__}:{exc}")
                    completed += 1
    finally:
        if log_file is not None:
            log_file.close()
    summary_path = run_root / "results" / "c7" / "c7_runner_summary.json"
    payload = {
        "evidence_label": "linux_nvidia_real_privileged_c7_if_exit_zero", "expected_episodes": len(manifest_rows) * 2,
        "completed_rows": completed, "failures": failures, "registry": str(registry_path),
        "privileged_diagnostic": True, "final_method_eligible": False,
        "visual_oracle": "not_implemented_not_runnable", "policy_reset_mode": policy_reset_mode,
        "returncode": 0 if not failures and completed == len(manifest_rows) * 2 else 4,
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": str(summary_path), "returncode": payload["returncode"]}, ensure_ascii=False))
    return int(payload["returncode"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("smolvla", "openvla"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--schema", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "episode_registry_schema.csv")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = manifest_static_check(args.model, args.config.resolve(), args.upstream.resolve(), args.manifest.resolve())
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.run_root is None:
        parser.error("--run-root is required unless --dry-run is used")
    return execute(args.model, args.config.resolve(), args.upstream.resolve(), args.run_root, args.manifest.resolve(), args.schema.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
