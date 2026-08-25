#!/usr/bin/env python3
"""Read-only H2 host probe. It never imports torch or starts a GPU workload."""

from __future__ import annotations

import argparse
import ctypes.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(argv: list[str]) -> dict[str, object]:
    try:
        completed = subprocess.run(argv, text=True, capture_output=True, timeout=15, check=False)
        return {
            "argv": argv,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": argv, "returncode": None, "stdout": "", "stderr": str(exc)}


def os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return values


def nvidia_probe() -> dict[str, object]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "executable": None, "gpus": [], "raw": None}
    query = run([
        executable,
        "--query-gpu=index,name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ])
    gpus: list[dict[str, object]] = []
    if query["returncode"] == 0:
        for line in str(query["stdout"]).splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) == 4:
                try:
                    memory_mb: int | None = int(parts[2])
                except ValueError:
                    memory_mb = None
                gpus.append({"index": parts[0], "name": parts[1], "memory_total_mb": memory_mb, "driver": parts[3]})
    driver_report = run([executable])
    match = re.search(r"CUDA Version:\s*([0-9]+(?:\.[0-9]+)?)", str(driver_report["stdout"]))
    cuda_version = float(match.group(1)) if match else None
    return {
        "available": query["returncode"] == 0 and bool(gpus),
        "executable": executable,
        "gpus": gpus,
        "cuda_version_reported_by_driver": cuda_version,
        "raw": query,
        "driver_report_returncode": driver_report["returncode"],
    }


def tool_probe(name: str, version_args: list[str]) -> dict[str, object]:
    executable = shutil.which(name)
    if not executable:
        return {"available": False, "executable": None, "version": None}
    result = run([executable, *version_args])
    version = str(result["stdout"] or result["stderr"]).splitlines()
    return {"available": result["returncode"] == 0, "executable": executable, "version": version[0] if version else None}


def write_json(path: Path | None, payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path is None:
        print(text, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text)
    temporary.replace(path)
    print(text, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("static", "linux-gpu"), default="static")
    parser.add_argument("--disk-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    disk_root = args.disk_root.expanduser().resolve()
    disk = shutil.disk_usage(disk_root)
    nvidia = nvidia_probe()
    gpu_memory = [gpu["memory_total_mb"] for gpu in nvidia["gpus"] if isinstance(gpu.get("memory_total_mb"), int)]
    max_vram_mb = max(gpu_memory, default=0)
    release_info = os_release()
    linux = platform.system() == "Linux"
    x86_64 = platform.machine() in {"x86_64", "amd64"}
    try:
        version_parts = release_info.get("VERSION_ID", "0.0").split(".")
        ubuntu_version = float(f"{version_parts[0]}.{version_parts[1]}")
    except (ValueError, IndexError):
        ubuntu_version = 0.0
    ubuntu_supported = release_info.get("ID") == "ubuntu" and ubuntu_version >= 20.04
    egl = ctypes.util.find_library("EGL")
    uv = tool_probe("uv", ["--version"])
    tools = {
        "git": tool_probe("git", ["--version"]),
        "uv": uv,
        "ffmpeg": tool_probe("ffmpeg", ["-version"]),
    }
    cuda_supported = isinstance(nvidia.get("cuda_version_reported_by_driver"), float) and nvidia["cuda_version_reported_by_driver"] >= 11.8
    backup_ok = linux and ubuntu_supported and x86_64 and bool(nvidia["available"]) and cuda_supported and max_vram_mb >= 48_000 and disk.free >= 220 * 10**9 and bool(egl) and all(item["available"] for item in tools.values())
    recommended_ok = backup_ok and max_vram_mb >= 79_000 and disk.free >= 300 * 10**9
    payload: dict[str, object] = {
        "evidence_label": "current_host_read_only_probe",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "os_release": release_info, "ubuntu_20_04_or_newer": ubuntu_supported},
        "python": {"version": platform.python_version(), "executable": sys.executable, "note": "probe interpreter only; VLA environments require uv-managed Python 3.11"},
        "disk": {"root": str(disk_root), "free_bytes": disk.free, "total_bytes": disk.total},
        "nvidia": nvidia,
        "egl": {"library": egl, "mujoco_gl_expected": "egl", "pyopengl_platform_expected": "egl"},
        "tools": tools,
        "qualification": {
            "recommended_80gb_300gb": recommended_ok,
            "backup_48gb_220gb": backup_ok,
            "linux_gpu_execution_eligible": backup_ok,
        },
        "not_tested": ["CUDA kernel", "MuJoCo context creation", "VLA checkpoint load", "episode", "VRAM peak"],
    }
    write_json(args.output, payload)
    if args.mode == "linux-gpu" and not backup_ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
