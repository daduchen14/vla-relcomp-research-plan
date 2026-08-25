#!/usr/bin/env python3
"""Validate pair manifests and summarize matched baseline/oracle registry rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "verified"}


def load(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def validate_manifest(path: Path, require_ready: bool) -> dict[str, object]:
    fields, rows = load(path)
    required = {"pair_id", "condition", "seed", "init_state_index", "changed_factor", "goal_verified", "reachable_verified", "leakage_check"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"manifest missing fields: {missing}")
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["pair_id"]].append(row)
    errors: list[str] = []
    if not groups:
        errors.append("manifest has no pair rows")
    for pair_id, pair_rows in groups.items():
        if len(pair_rows) != 2:
            errors.append(f"{pair_id}: expected 2 rows, got {len(pair_rows)}")
            continue
        if len({row["condition"] for row in pair_rows}) != 2:
            errors.append(f"{pair_id}: conditions must be distinct")
        for key in ("seed", "init_state_index", "changed_factor"):
            if len({row[key] for row in pair_rows}) != 1 or not pair_rows[0][key]:
                errors.append(f"{pair_id}: {key} must be one shared non-empty value")
        if require_ready:
            for key in ("goal_verified", "reachable_verified", "leakage_check"):
                if any(row[key].strip().lower() not in TRUE_VALUES for row in pair_rows):
                    errors.append(f"{pair_id}: {key} is not verified")
    return {"pairs": len(groups), "rows": len(rows), "errors": errors, "status": "passed" if not errors else "failed", "proof_boundary": "Structure checks do not prove causal minimality or physical reachability."}


def audit_registry(path: Path) -> dict[str, object]:
    fields, rows = load(path)
    required = {"model_id", "suite", "level", "task_id", "seed", "init_state_index", "intervention", "success", "exception"}
    missing = sorted(required - set(fields))
    if missing:
        raise ValueError(f"registry missing fields: {missing}")
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["exception"] or row["success"] not in {"0", "1"}:
            continue
        key = tuple(row[name] for name in ("model_id", "suite", "level", "task_id", "seed", "init_state_index"))
        groups[key].append(row)
    matched = recovery = damage = unchanged_success = unchanged_failure = 0
    ambiguous = 0
    for group_rows in groups.values():
        baseline = [row for row in group_rows if row["intervention"] == "none"]
        interventions = [row for row in group_rows if row["intervention"] != "none"]
        if len(baseline) != 1 or len(interventions) != 1:
            ambiguous += 1
            continue
        before, after = int(baseline[0]["success"]), int(interventions[0]["success"])
        matched += 1
        recovery += before == 0 and after == 1
        damage += before == 1 and after == 0
        unchanged_success += before == 1 and after == 1
        unchanged_failure += before == 0 and after == 0
    return {
        "matched": matched, "recovery": recovery, "damage": damage, "unchanged_success": unchanged_success,
        "unchanged_failure": unchanged_failure, "ambiguous_or_unmatched_groups": ambiguous,
        "claim_boundary": "Counts are descriptive; Gate 3 still requires preregistration, at least two seeds, and evidence review.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = {"manifest": validate_manifest(args.manifest, args.require_ready)}
    if args.registry:
        payload["registry"] = audit_registry(args.registry)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    return 0 if payload["manifest"]["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
