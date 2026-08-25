#!/usr/bin/env python3
"""Read-only env.step sidecar for uncalibrated raw state diagnostics."""

from __future__ import annotations

import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FIELDS = [
    "run_id", "episode_id", "step", "timestamp_utc", "target_object", "reference_object", "contact_raw",
    "target_z_raw", "support_z_raw", "target_reference_distance_raw", "official_goal_success", "done",
    "definition_status", "definition_version", "contact_threshold", "lift_threshold", "distance_threshold",
    "source_path", "notes",
]


def _position(base: Any, name: str) -> list[float] | None:
    body_id = getattr(base, "obj_body_id", {}).get(name)
    if body_id is None:
        return None
    value = base.sim.data.body_xpos[body_id]
    return [float(item) for item in value]


class ReadOnlyStageSidecar:
    """Wrap env.step, append raw values, and return the original step tuple unchanged."""

    def __init__(self, env: Any, output: Path, run_id: str, episode_id: str, target: str, reference: str) -> None:
        self.env = env
        self.output = output.expanduser().resolve()
        self.run_id = run_id
        self.episode_id = episode_id
        self.target = target
        self.reference = reference
        self.step_index = 0
        self.original_step = env.step
        self.base = getattr(env, "env", env)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        if not self.output.exists():
            with self.output.open("w", newline="") as handle:
                csv.DictWriter(handle, fieldnames=FIELDS).writeheader()

    def install(self) -> None:
        self.env.step = self.step

    def uninstall(self) -> None:
        self.env.step = self.original_step

    def step(self, action: Any) -> Any:
        returned = self.original_step(action)
        if not isinstance(returned, tuple) or len(returned) != 4:
            raise RuntimeError("env.step no longer returns (obs, reward, done, info)")
        _, _, done, info = returned
        target_pos = _position(self.base, self.target)
        reference_pos = _position(self.base, self.reference)
        distance = None
        if target_pos is not None and reference_pos is not None:
            distance = math.dist(target_pos, reference_pos)
        target_body = self.base.get_object(self.target) if hasattr(self.base, "get_object") else None
        contact = None
        if target_body is not None and hasattr(self.base, "check_gripper_contact"):
            contact = bool(self.base.check_gripper_contact(target_body))
        official = info.get("success") if isinstance(info, dict) else None
        row = {
            "run_id": self.run_id, "episode_id": self.episode_id, "step": self.step_index,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "target_object": self.target,
            "reference_object": self.reference, "contact_raw": "" if contact is None else int(contact),
            "target_z_raw": "" if target_pos is None else target_pos[2], "support_z_raw": "",
            "target_reference_distance_raw": "" if distance is None else distance,
            "official_goal_success": "" if official is None else int(bool(official)), "done": int(bool(done)),
            "definition_status": "uncalibrated", "definition_version": "unfrozen",
            "contact_threshold": "", "lift_threshold": "", "distance_threshold": "",
            "source_path": "env.step read-only wrapper", "notes": "raw diagnostic only; official success remains primary",
        }
        with self.output.open("a", newline="") as handle:
            csv.DictWriter(handle, fieldnames=FIELDS).writerow(row)
        self.step_index += 1
        return returned
