#!/usr/bin/env python3
"""Validate an episode registry and report counts, Wilson intervals, and oracle transitions."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


REQUIRED = {
    "run_id", "episode_id", "suite", "level", "task_id", "seed", "init_state_index",
    "intervention", "success", "target_contacted", "target_lifted", "reference_approached",
    "relation_satisfied", "exception",
}


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return (float("nan"), float("nan"))
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return center - radius, center + radius


def parse_bool(value: str, field: str) -> int:
    if value not in {"0", "1"}:
        raise ValueError(f"{field} must be 0 or 1, got {value!r}")
    return int(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    args = parser.parse_args()
    with args.registry.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"missing fields: {sorted(missing)}")
        rows = list(reader)
    seen: set[str] = set()
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if row["episode_id"] in seen:
            raise SystemExit(f"duplicate episode_id: {row['episode_id']}")
        seen.add(row["episode_id"])
        success = parse_bool(row["success"], "success")
        for field in ("target_contacted", "target_lifted", "reference_approached", "relation_satisfied"):
            parse_bool(row[field], field)
        if success and row["relation_satisfied"] != "1":
            raise SystemExit(f"success without relation_satisfied: {row['episode_id']}")
        grouped[row["level"]].append(success)
    print(f"validated_rows={len(rows)}")
    for level in sorted(grouped, key=int):
        values = grouped[level]
        count = sum(values)
        low, high = wilson(count, len(values))
        print(f"level={level} success={count}/{len(values)} rate={count/len(values):.3f} wilson95=[{low:.3f},{high:.3f}]")
    print("NOTE: fixture inputs demonstrate analysis shape; they are not VLA-Arena results.")


if __name__ == "__main__":
    main()
