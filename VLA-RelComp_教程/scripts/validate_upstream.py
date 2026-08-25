#!/usr/bin/env python3
"""Offline assertions for the locked VLA-Arena commit and tutorial-critical paths."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


LOCKED = "babe582ebffc82b979b77964a7e56417d02f63a4"
SUITE = "extrapolation_preposition_combinations"
REQUIRED = [
    "vla_arena/vla_arena/benchmark/__init__.py",
    "vla_arena/vla_arena/benchmark/vla_arena_suite_task_map.py",
    "vla_arena/vla_arena/envs/bddl_base_domain.py",
    "vla_arena/vla_arena/utils/eval_init_state.py",
    "vla_arena/models/smolvla/evaluator.py",
    "vla_arena/models/openvla/evaluator.py",
    "vla_arena/configs/evaluation/smolvla.yaml",
    "vla_arena/configs/evaluation/openvla.yaml",
    "vla_arena/configs/evaluation/random.yaml",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream_root", type=Path)
    args = parser.parse_args()
    root = args.upstream_root.resolve()
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert sha == LOCKED, f"expected {LOCKED}, got {sha}"
    for relative in REQUIRED:
        assert (root / relative).is_file(), f"missing {relative}"
    benchmark = (root / REQUIRED[0]).read_text(encoding="utf-8")
    task_map = (root / REQUIRED[1]).read_text(encoding="utf-8")
    env = (root / REQUIRED[2]).read_text(encoding="utf-8")
    assert SUITE in benchmark and SUITE in task_map
    assert "def _check_success" in env and "info['success'] = success" in env
    bddl = root / "vla_arena/vla_arena/bddl_files" / SUITE
    init = root / "vla_arena/vla_arena/init_files" / SUITE
    for level in range(3):
        assert len(list((bddl / f"level_{level}").glob("*.bddl"))) == 5
        assert len(list((init / f"level_{level}").glob("*.pruned_init"))) == 5
    for name in ("smolvla", "openvla", "random"):
        text = (root / f"vla_arena/configs/evaluation/{name}.yaml").read_text(encoding="utf-8")
        for key in ("task_suite_name", "task_level", "num_trials_per_task", "seed"):
            assert key in text, f"{name}.yaml missing {key}"
    print(f"PASS commit={sha}")
    print("PASS critical_paths=9")
    print("PASS bddl_by_level=5,5,5 init_by_level=5,5,5")
    print("PASS suite_registry_and_success_path")


if __name__ == "__main__":
    main()
