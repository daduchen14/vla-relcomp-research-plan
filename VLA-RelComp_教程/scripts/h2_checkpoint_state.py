#!/usr/bin/env python3
"""Fail-closed C0-C7 state transitions for an H2 evidence run."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


CHECKPOINTS = tuple(f"C{index}" for index in range(8))
STATUSES = {"pending", "running", "passed", "failed", "skipped"}
TERMINAL = {"passed", "failed", "skipped"}
SECRET_PATTERN = re.compile(
    r"(?i)(?:token|password|passwd|secret|api[-_]?key|authorization)(?:\s*[=:]|\s+)(?:\S+)"
)
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def safe_state_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.name != "checkpoint_state.json":
        raise ValueError("state path must end in checkpoint_state.json")
    if resolved in {Path("/"), Path.home().resolve()} or len(resolved.parts) < 4:
        raise ValueError(f"unsafe state path: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"state file does not exist: {resolved}")
    return resolved


def read_state(path: Path) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read state file: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != set(CHECKPOINTS):
        raise ValueError("state must contain exactly C0 through C7")
    for checkpoint in CHECKPOINTS:
        record = payload[checkpoint]
        if not isinstance(record, dict) or record.get("status") not in STATUSES:
            raise ValueError(f"invalid record for {checkpoint}")
        if not isinstance(record.get("evidence", []), list):
            raise ValueError(f"evidence must be a list for {checkpoint}")
    return payload


def predecessor_ready(state: dict[str, dict[str, object]], checkpoint: str) -> bool:
    index = int(checkpoint[1:])
    if index == 0:
        return True
    if checkpoint == "C6":
        return state["C4"]["status"] == "passed" and state["C5"]["status"] in {"passed", "skipped"}
    return state[f"C{index - 1}"]["status"] == "passed"


def normalize_evidence(run_root: Path, values: list[str], require_exists: bool) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        if not raw or SECRET_PATTERN.search(raw):
            raise ValueError("empty or credential-like evidence path")
        candidate = Path(raw)
        resolved = candidate.resolve() if candidate.is_absolute() else (run_root / candidate).resolve()
        if run_root != resolved and run_root not in resolved.parents:
            raise ValueError(f"evidence escapes run root: {raw}")
        if require_exists and not resolved.exists():
            raise ValueError(f"evidence does not exist: {raw}")
        relative = resolved.relative_to(run_root).as_posix()
        if relative not in normalized:
            normalized.append(relative)
    return normalized


def transition(
    state_path: Path,
    checkpoint: str,
    status: str,
    evidence: list[str],
    note: str | None,
    failure_class: str | None,
    elapsed_minutes: float | None,
    retry_run: str | None,
) -> dict[str, object]:
    state_path = safe_state_path(state_path)
    state = read_state(state_path)
    current = str(state[checkpoint]["status"])
    if current in TERMINAL:
        raise ValueError(f"{checkpoint} is terminal ({current}); create a new retry run instead")
    allowed = {("pending", "running"), ("running", "passed"), ("running", "failed"), ("pending", "skipped")}
    if (current, status) not in allowed:
        raise ValueError(f"illegal transition for {checkpoint}: {current} -> {status}")
    if not predecessor_ready(state, checkpoint):
        raise ValueError(f"predecessor gate is not passed for {checkpoint}")
    if status == "skipped" and checkpoint != "C5":
        raise ValueError("only conditional checkpoint C5 may be skipped")
    if status in TERMINAL and not note:
        raise ValueError("terminal transition requires --note with the checked success/failure reason")
    if note and SECRET_PATTERN.search(note):
        raise ValueError("note appears to contain a credential")
    if status == "failed" and not failure_class:
        raise ValueError("failed transition requires --failure-class")
    if status != "failed" and (failure_class or retry_run):
        raise ValueError("failure metadata is only valid for failed transitions")
    if failure_class and not SAFE_LABEL.fullmatch(failure_class):
        raise ValueError("failure class must be a short safe label")
    if retry_run and not SAFE_LABEL.fullmatch(retry_run):
        raise ValueError("retry run must be a short safe label, not a path")
    if elapsed_minutes is not None and elapsed_minutes < 0:
        raise ValueError("elapsed minutes cannot be negative")

    run_root = state_path.parent
    require_exists = status in TERMINAL
    new_evidence = normalize_evidence(run_root, evidence, require_exists=require_exists)
    if status in TERMINAL and not new_evidence:
        raise ValueError("terminal transition requires at least one existing evidence path")
    previous_evidence = normalize_evidence(
        run_root,
        [str(item) for item in state[checkpoint].get("evidence", [])],
        require_exists=require_exists,
    )
    combined_evidence = list(dict.fromkeys([*previous_evidence, *new_evidence]))
    timestamp = datetime.now(timezone.utc).isoformat()
    history = state[checkpoint].get("history", [])
    if not isinstance(history, list):
        raise ValueError(f"history must be a list for {checkpoint}")
    event: dict[str, object] = {
        "from": current,
        "to": status,
        "timestamp_utc": timestamp,
        "evidence": new_evidence,
    }
    if note:
        event["note"] = note
    if failure_class:
        event["failure_class"] = failure_class
    if elapsed_minutes is not None:
        event["elapsed_minutes"] = elapsed_minutes
    if retry_run:
        event["retry_run"] = retry_run
    history.append(event)

    record: dict[str, object] = {
        "status": status,
        "evidence": combined_evidence,
        "updated_utc": timestamp,
        "history": history,
    }
    if note:
        record["note"] = note
    if failure_class:
        record["failure_class"] = failure_class
    if elapsed_minutes is not None:
        record["elapsed_minutes"] = elapsed_minutes
    if retry_run:
        record["retry_run"] = retry_run
    state[checkpoint] = record

    temporary = state_path.with_suffix(".json.tmp")
    with temporary.open("w") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(state_path)
    return {"checkpoint": checkpoint, "from": current, "to": status, "state": str(state_path), "record": record}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--checkpoint", choices=CHECKPOINTS, required=True)
    parser.add_argument("--status", choices=("running", "passed", "failed", "skipped"), required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--note")
    parser.add_argument("--failure-class")
    parser.add_argument("--elapsed-minutes", type=float)
    parser.add_argument("--retry-run")
    args = parser.parse_args()
    try:
        payload = transition(
            args.state,
            args.checkpoint,
            args.status,
            args.evidence,
            args.note,
            args.failure_class,
            args.elapsed_minutes,
            args.retry_run,
        )
    except ValueError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
