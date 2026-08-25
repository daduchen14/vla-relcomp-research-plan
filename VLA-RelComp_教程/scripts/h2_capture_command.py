#!/usr/bin/env python3
"""Run one argv-only command and persist an auditable receipt without secrets."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SECRET_PATTERN = re.compile(r"(?i)(token|password|passwd|secret|api[-_]?key|authorization)(=|:)")
ENV_ALLOWLIST = {
    "PATH", "H2_ROOT", "H2_TUTORIAL", "H2_UPSTREAM", "H2_ASSETS", "H2_CACHE", "H2_VENVS", "H2_RUN", "H2_RUN_ID",
    "HF_HOME", "UV_CACHE_DIR", "XDG_CACHE_HOME", "MUJOCO_GL", "PYOPENGL_PLATFORM", "CUDA_VISIBLE_DEVICES",
    "UV_PROJECT_ENVIRONMENT",
    "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
}


def gpu_snapshot() -> dict[str, object] | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    completed = subprocess.run(
        [executable, "--query-gpu=index,name,memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
        text=True, capture_output=True, check=False, timeout=15,
    )
    return {"returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not argv:
        parser.error("a command is required after --")
    if any(SECRET_PATTERN.search(item) for item in argv):
        raise SystemExit("refusing a command line that appears to contain a credential")
    evidence = args.evidence_dir.expanduser().resolve()
    if evidence in {Path("/"), Path.home().resolve()}:
        raise SystemExit(f"unsafe evidence directory: {evidence}")
    evidence.mkdir(parents=True, exist_ok=True)
    receipt_path = evidence / "command.json"
    if receipt_path.exists():
        raise SystemExit(f"receipt already exists; use a new retry directory: {receipt_path}")
    started = datetime.now(timezone.utc)
    before = gpu_snapshot()
    start_clock = time.monotonic()
    stdout_path = evidence / "stdout.txt"
    stderr_path = evidence / "stderr.txt"
    try:
        with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
            completed = subprocess.run(argv, stdout=stdout, stderr=stderr, check=False)
        returncode = completed.returncode
        exception = None
    except OSError as exc:
        returncode = 127
        exception = f"{type(exc).__name__}: {exc}"
        stderr_path.write_text(exception + "\n")
        stdout_path.touch(exist_ok=True)
    ended = datetime.now(timezone.utc)
    receipt = {
        "argv": argv,
        "cwd": os.getcwd(),
        "environment_allowlist": {key: os.environ[key] for key in sorted(ENV_ALLOWLIST) if key in os.environ},
        "started_utc": started.isoformat(),
        "ended_utc": ended.isoformat(),
        "wall_seconds": round(time.monotonic() - start_clock, 6),
        "returncode": returncode,
        "exception": exception,
        "gpu_before": before,
        "gpu_after": gpu_snapshot(),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"receipt": str(receipt_path), "returncode": returncode}, ensure_ascii=False))
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
