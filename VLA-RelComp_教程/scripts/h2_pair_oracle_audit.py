#!/usr/bin/env python3
"""Fail-closed C7 manifest gate and manifest-bound registry audit."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "verified"}
SUITE = "extrapolation_preposition_combinations"
INTERVENTIONS = ("none", "language_oracle")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
MANIFEST_FIELDS = {
    "pair_family", "pair_id", "condition", "model_id", "model_revision", "suite", "level", "task_id", "seed",
    "init_state_index", "changed_factor", "target_object", "reference_object", "relation", "instruction",
    "language_oracle_instruction", "goal_verified", "reachable_verified", "leakage_check",
}
REGISTRY_FIELDS = {
    "pair_family", "pair_id", "condition", "changed_factor", "model_id", "model_revision", "suite", "level", "task_id",
    "seed", "init_state_index", "instruction_original", "instruction_variant", "intervention", "target_object",
    "reference_object", "relation", "success", "video_path", "result_path", "exception",
}


def load(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def parse_language_oracle(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for segment in text.split(";"):
        if "=" not in segment:
            raise ValueError("language oracle must use key=value segments")
        key, value = (item.strip() for item in segment.split("=", 1))
        if not key or not value or key in parts:
            raise ValueError("language oracle has empty or duplicate key")
        parts[key] = value
    if set(parts) != {"target", "action", "relation", "reference"} or parts["action"] != "place":
        raise ValueError("language oracle must be exactly target/action=place/relation/reference")
    return parts


def valid_identifier(value: str) -> bool:
    return bool(SAFE_IDENTIFIER.fullmatch(value)) and value not in {".", ".."}


def validate_manifest(path: Path, require_ready: bool) -> dict[str, object]:
    fields, rows = load(path)
    missing = sorted(MANIFEST_FIELDS - set(fields))
    if missing:
        raise ValueError(f"manifest missing fields: {missing}")
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    families: dict[str, list[dict[str, str]]] = defaultdict(list)
    errors: list[str] = []
    seen_rows: set[tuple[str, str]] = set()
    for number, row in enumerate(rows, 2):
        for name in ("pair_family", "pair_id", "condition"):
            if not valid_identifier(row[name]):
                errors.append(f"row {number}: unsafe {name}; use 1-64 ASCII letters/digits/_/- and no path syntax")
        key = (row["pair_id"], row["condition"])
        if not all(key):
            errors.append(f"row {number}: pair_id/condition must be non-empty")
        elif key in seen_rows:
            errors.append(f"row {number}: duplicate manifest binding {key}")
        seen_rows.add(key)
        groups[row["pair_id"]].append(row)
        families[row["pair_family"]].append(row)
        if not row["pair_family"]:
            errors.append(f"row {number}: pair_family must be non-empty")
        if row["suite"] != SUITE:
            errors.append(f"row {number}: suite must remain {SUITE}")
        for name, lower, upper in (("level", 0, 2), ("task_id", 0, 4), ("seed", 0, 2**63 - 1), ("init_state_index", 0, 2**31 - 1)):
            try:
                value = int(row[name])
                if not lower <= value <= upper:
                    raise ValueError
            except ValueError:
                errors.append(f"row {number}: {name} must be an integer in [{lower}, {upper}]")
        try:
            oracle = parse_language_oracle(row["language_oracle_instruction"])
            expected = {"target": row["target_object"], "relation": row["relation"], "reference": row["reference_object"]}
            for name, value in expected.items():
                if oracle[name] != value:
                    errors.append(f"row {number}: oracle {name} does not match manifest")
        except ValueError as exc:
            errors.append(f"row {number}: {exc}")
        if require_ready:
            for name in ("goal_verified", "reachable_verified", "leakage_check"):
                if row[name].strip().lower() not in TRUE_VALUES:
                    errors.append(f"row {number}: {name} is not verified")
    if not groups:
        errors.append("manifest has no pair rows")
    for pair_id, pair_rows in groups.items():
        if len(pair_rows) != 2:
            errors.append(f"{pair_id}: expected 2 condition rows, got {len(pair_rows)}")
            continue
        if len({row["condition"] for row in pair_rows}) != 2:
            errors.append(f"{pair_id}: conditions must be distinct")
        for name in ("pair_family", "model_id", "model_revision", "suite", "level", "seed", "init_state_index", "changed_factor"):
            values = {row[name] for row in pair_rows}
            if len(values) != 1 or not next(iter(values), ""):
                errors.append(f"{pair_id}: {name} must be one shared non-empty value")
    if require_ready:
        for family, family_rows in families.items():
            pair_ids = {row["pair_id"] for row in family_rows}
            seeds = {row["seed"] for row in family_rows}
            if len(pair_ids) < 2 or len(seeds) < 2:
                errors.append(f"{family}: ready C7 family requires at least two pair_id executions at distinct seeds")
            by_condition: dict[str, list[dict[str, str]]] = defaultdict(list)
            for row in family_rows:
                by_condition[row["condition"]].append(row)
            if len(by_condition) != 2:
                errors.append(f"{family}: all seeds must use the same two condition labels")
            stable_fields = ("model_id", "model_revision", "suite", "level", "task_id", "init_state_index", "changed_factor", "target_object", "reference_object", "relation", "instruction", "language_oracle_instruction")
            for condition, condition_rows in by_condition.items():
                for name in stable_fields:
                    if len({row[name] for row in condition_rows}) != 1:
                        errors.append(f"{family}/{condition}: {name} differs across seeds")
    return {
        "pair_families": len(families), "pairs": len(groups), "rows": len(rows), "errors": errors,
        "status": "passed" if not errors else "failed",
        "expected_registry_rows": len(rows) * len(INTERVENTIONS),
        "proof_boundary": "Structure and explicit bindings do not prove causal minimality or physical reachability.",
    }


def audit_registry(manifest_path: Path, registry_path: Path) -> dict[str, object]:
    _, manifest_rows = load(manifest_path)
    fields, registry_rows = load(registry_path)
    missing = sorted(REGISTRY_FIELDS - set(fields))
    if missing:
        raise ValueError(f"registry missing fields: {missing}")
    allowed = {(row["pair_id"], row["condition"]): row for row in manifest_rows}
    expected = {(pair_id, condition, intervention) for pair_id, condition in allowed for intervention in INTERVENTIONS}
    observed: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    errors: list[str] = []
    for number, row in enumerate(registry_rows, 2):
        key = (row["pair_id"], row["condition"], row["intervention"])
        if key not in expected:
            errors.append(f"row {number}: unregistered binding {key}")
            continue
        observed[key].append(row)
    for key in sorted(expected):
        count = len(observed.get(key, []))
        if count == 0:
            errors.append(f"missing registry row {key}")
        elif count > 1:
            errors.append(f"duplicate registry rows {key}: {count}")
    compare_fields = (
        "pair_family", "pair_id", "condition", "changed_factor", "model_id", "model_revision", "suite", "level", "task_id",
        "seed", "init_state_index", "target_object", "reference_object", "relation",
    )
    matched = recovery = damage = unchanged_success = unchanged_failure = 0
    for key in sorted(expected):
        rows = observed.get(key, [])
        if len(rows) != 1:
            continue
        row = rows[0]
        manifest = allowed[(key[0], key[1])]
        for name in compare_fields:
            expected_value = manifest[name]
            if row[name] != expected_value:
                errors.append(f"{key}: {name}={row[name]!r} differs from manifest {expected_value!r}")
        expected_variant = manifest["instruction"] if key[2] == "none" else manifest["language_oracle_instruction"]
        if row["instruction_original"] != manifest["instruction"] or row["instruction_variant"] != expected_variant:
            errors.append(f"{key}: instruction provenance differs from manifest")
        if row["exception"] or row["success"] not in {"0", "1"}:
            errors.append(f"{key}: episode exception or invalid success")
        for evidence_name in ("video_path", "result_path"):
            evidence = Path(row[evidence_name])
            if not row[evidence_name] or not evidence.is_file() or evidence.stat().st_size <= 0:
                errors.append(f"{key}: missing non-empty {evidence_name}")
    for pair_condition in sorted(allowed):
        baseline = observed.get((*pair_condition, "none"), [])
        oracle = observed.get((*pair_condition, "language_oracle"), [])
        if len(baseline) != 1 or len(oracle) != 1:
            continue
        if any(row["exception"] or row["success"] not in {"0", "1"} for row in (baseline[0], oracle[0])):
            continue
        before, after = int(baseline[0]["success"]), int(oracle[0]["success"])
        matched += 1
        recovery += before == 0 and after == 1
        damage += before == 1 and after == 0
        unchanged_success += before == 1 and after == 1
        unchanged_failure += before == 0 and after == 0
    return {
        "status": "passed" if not errors else "failed", "errors": errors,
        "manifest_allowed_rows": len(expected), "observed_rows": len(registry_rows), "matched": matched,
        "recovery": recovery, "damage": damage, "unchanged_success": unchanged_success,
        "unchanged_failure": unchanged_failure,
        "claim_boundary": "Privileged language-oracle counts are descriptive diagnostics, never a final method result.",
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
        payload["registry"] = audit_registry(args.manifest, args.registry)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    passed = payload["manifest"]["status"] == "passed" and payload.get("registry", {"status": "passed"})["status"] == "passed"
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
