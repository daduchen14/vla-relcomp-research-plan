#!/usr/bin/env python3
"""Fail-closed paired statistics for a manifest-bound C7 registry."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from h2_pair_oracle_audit import audit_registry, load, validate_manifest


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [center - radius, center + radius]


def exact_mcnemar(recovery: int, damage: int) -> dict[str, Any]:
    discordant = recovery + damage
    if discordant == 0:
        return {"discordant": 0, "two_sided_exact_p": 1.0}
    smaller = min(recovery, damage)
    tail = sum(math.comb(discordant, value) for value in range(smaller + 1)) / (2**discordant)
    return {"discordant": discordant, "two_sided_exact_p": min(1.0, 2 * tail)}


def summarize(transitions: list[tuple[int, int]]) -> dict[str, Any]:
    cells = {"failure_failure": 0, "failure_success": 0, "success_failure": 0, "success_success": 0}
    for before, after in transitions:
        key = {
            (0, 0): "failure_failure", (0, 1): "failure_success",
            (1, 0): "success_failure", (1, 1): "success_success",
        }[(before, after)]
        cells[key] += 1
    baseline_failures = cells["failure_failure"] + cells["failure_success"]
    baseline_successes = cells["success_failure"] + cells["success_success"]
    recovery = cells["failure_success"]
    damage = cells["success_failure"]
    return {
        "matched": len(transitions), "cells": cells,
        "recovery": {
            "numerator": recovery, "denominator": baseline_failures,
            "rate": recovery / baseline_failures if baseline_failures else None,
            "wilson95": wilson(recovery, baseline_failures),
        },
        "damage": {
            "numerator": damage, "denominator": baseline_successes,
            "rate": damage / baseline_successes if baseline_successes else None,
            "wilson95": wilson(damage, baseline_successes),
        },
        "mcnemar": exact_mcnemar(recovery, damage),
    }


def analyze(manifest_path: Path, registry_path: Path) -> dict[str, Any]:
    manifest_report = validate_manifest(manifest_path, require_ready=True)
    registry_report = audit_registry(manifest_path, registry_path)
    errors = [*manifest_report["errors"], *registry_report["errors"]]
    if errors:
        raise ValueError("manifest/registry audit failed: " + " | ".join(errors))
    _, manifest_rows = load(manifest_path)
    with registry_path.open(newline="") as handle:
        registry_rows = list(csv.DictReader(handle))
    allowed = {(row["pair_id"], row["condition"]): row for row in manifest_rows}
    observed = {(row["pair_id"], row["condition"], row["intervention"]): row for row in registry_rows}
    transitions: list[tuple[dict[str, str], int, int]] = []
    for key, manifest in sorted(allowed.items()):
        baseline = observed[(*key, "none")]
        oracle = observed[(*key, "language_oracle")]
        transitions.append((manifest, int(baseline["success"]), int(oracle["success"])))
    strata: dict[str, dict[str, Any]] = {}
    for field in ("task_id", "seed", "init_state_index"):
        grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for manifest, before, after in transitions:
            grouped[manifest[field]].append((before, after))
        strata[field] = {value: summarize(values) for value, values in sorted(grouped.items(), key=lambda item: int(item[0]))}
    return {
        "status": "passed", "manifest": str(manifest_path.resolve()), "registry": str(registry_path.resolve()),
        "overall": summarize([(before, after) for _, before, after in transitions]), "strata": strata,
        "claim_boundary": "Descriptive privileged-oracle diagnostics; no causal minimality, reachability, Gate, or final-method claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        payload = analyze(args.manifest.resolve(), args.registry.resolve())
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text)
        print(text, end="")
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
