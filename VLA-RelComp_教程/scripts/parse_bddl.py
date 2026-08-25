#!/usr/bin/env python3
"""Parse the 15 locked PrepositionCombinations BDDL files into a manifest."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


SUITE = "extrapolation_preposition_combinations"


def section(text: str, name: str) -> str:
    marker = f"(:{name}"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"missing section {marker}")
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError(f"unbalanced section {marker}")


def atoms(block: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block)


def parse_file(path: Path, level: int) -> dict[str, str | int]:
    text = path.read_text(encoding="utf-8")
    language_block = section(text, "language")
    language = language_block[len("(:language") : -1].strip()
    interest = atoms(section(text, "obj_of_interest"))[1:]
    init_block = section(text, "init")
    goal_block = section(text, "goal")
    predicates = re.findall(r"\(([A-Za-z_][A-Za-z0-9_]*)\s+([^()]+)\)", goal_block)
    goal = " & ".join(f"{pred}({','.join(args.split())})" for pred, args in predicates if pred.lower() != "and")
    return {
        "suite": SUITE,
        "level": level,
        "task_id": path.stem,
        "language": language,
        "obj_of_interest": ";".join(interest),
        "goal": goal,
        "init_predicate_count": len(re.findall(r"\([A-Z][A-Za-z_]*\s+", init_block)),
        "bddl_path": str(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.upstream_root / "vla_arena/vla_arena/bddl_files" / SUITE
    rows: list[dict[str, str | int]] = []
    for level in range(3):
        files = sorted((base / f"level_{level}").glob("*.bddl"))
        if len(files) != 5:
            raise SystemExit(f"expected 5 BDDL files at level {level}, found {len(files)}")
        rows.extend(parse_file(path, level) for path in files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} tasks to {args.output}")
    print("levels:", {level: sum(row["level"] == level for row in rows) for level in range(3)})


if __name__ == "__main__":
    main()
