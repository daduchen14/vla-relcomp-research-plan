#!/usr/bin/env python3
"""Detect four behavior stages from a synthetic trajectory CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def first_true(rows: list[dict[str, str]], predicate) -> int | None:
    for row in rows:
        if predicate(row):
            return int(row["step"])
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trajectory", type=Path)
    args = parser.parse_args()
    with args.trajectory.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    report = {
        "target_contact_step": first_true(rows, lambda r: r["gripper_target_contact"] == "1"),
        "target_lift_step": first_true(rows, lambda r: float(r["target_height"]) >= 0.10),
        "reference_approach_step": first_true(rows, lambda r: float(r["reference_distance"]) <= 0.25),
        "relation_satisfied_step": first_true(rows, lambda r: r["relation_satisfied"] == "1"),
        "source": "synthetic fixture—not simulator state",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
