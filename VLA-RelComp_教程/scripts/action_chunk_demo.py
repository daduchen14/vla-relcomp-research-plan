#!/usr/bin/env python3
"""Pure-Python observation -> action-chunk teaching fixture."""

from __future__ import annotations

import json
import math


def fake_policy(observation: dict[str, object], chunk_size: int = 4) -> list[list[float]]:
    """Return four 7-D actions; this is a didactic rule, not a trained VLA."""
    target = observation["target_xyz"]
    ee = observation["robot_state"][0:3]
    delta = [(float(target[i]) - float(ee[i])) / chunk_size for i in range(3)]
    one_action = [*delta, 0.0, 0.0, 0.0, -1.0]
    return [one_action[:] for _ in range(chunk_size)]


def main() -> None:
    observation = {
        "images": {"agentview": "fixture_rgb[256,256,3]", "wrist": "fixture_rgb[256,256,3]"},
        "robot_state": [0.10, -0.20, 0.30, 0.0, 0.0, 0.0, -1.0],
        "instruction": "Pick the tomato and place it on the bowl.",
        "target_xyz": [0.18, -0.12, 0.34],
    }
    chunk = fake_policy(observation)
    assert len(chunk) == 4 and all(len(action) == 7 for action in chunk)
    assert all(math.isfinite(value) for action in chunk for value in action)
    print(json.dumps({"observation": observation, "action_chunk_shape": [4, 7], "action_chunk": chunk}, indent=2))
    print("NOTE: synthetic teaching fixture; no VLA checkpoint or simulator was run.")


if __name__ == "__main__":
    main()
