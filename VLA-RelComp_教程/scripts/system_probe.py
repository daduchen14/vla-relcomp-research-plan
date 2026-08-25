#!/usr/bin/env python3
"""Free local environment probe; never prints secrets or full environment variables."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def safe_version(command: list[str]) -> str | None:
    executable = shutil.which(command[0])
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, *command[1:]], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return "present-but-version-check-failed"
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0] if text else f"exit={result.returncode}"


def main() -> None:
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "tools": {
            "git": safe_version(["git", "--version"]),
            "uv": safe_version(["uv", "--version"]),
            "nvidia_smi": safe_version(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]),
        },
        "interpretation": {
            "nvidia_smi_missing": "Expected on a Mac; not evidence that the approved Linux/NVIDIA plan is infeasible.",
            "scope": "This probe validates tutorial tooling only, not VLA-Arena simulation or model inference.",
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
