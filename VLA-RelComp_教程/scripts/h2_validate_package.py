#!/usr/bin/env python3
"""Offline/static validator for the H2 preflight package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


EXPECTED_COMMIT = "babe582ebffc82b979b77964a7e56417d02f63a4"
REQUIRED = (
    "h2_preflight/README.md", "h2_preflight/checkpoint_matrix.md", "h2_preflight/security_version_audit.md",
    "h2_preflight/evidence_and_resume.md", "h2_preflight/configs/random_l0.yaml",
    "h2_preflight/configs/smolvla_l0.yaml", "h2_preflight/configs/openvla_l0.yaml",
    "assets/h2_assets.lock", "assets/h2_stage_sidecar_schema.csv",
    "scripts/h2_system_probe.py", "scripts/h2_prepare_run.py", "scripts/h2_capture_command.py",
    "scripts/h2_fetch_assets.py", "scripts/h2_one_episode.py", "scripts/h2_finalize_evidence.py",
    "scripts/h2_stage_sidecar.py", "scripts/h2_pair_oracle_audit.py",
    "scripts/h2_pilot.py",
)
FORBIDDEN_PATHS = ("/Users/nokian97", "/home/ubuntu", "/root/")
SECRET_VALUE = re.compile(r"(?:hf_|ghp_|github_pat_)[A-Za-z0-9_\-]{12,}")


def command(argv: list[str], expect: int = 0) -> dict[str, object]:
    completed = subprocess.run(argv, text=True, capture_output=True, check=False)
    if completed.returncode != expect:
        raise AssertionError(f"command returned {completed.returncode}, expected {expect}: {argv}\n{completed.stdout}\n{completed.stderr}")
    return {"argv": argv, "returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tutorial_root", type=Path)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.tutorial_root.resolve()
    upstream = args.upstream.resolve()
    checks: list[dict[str, object]] = []

    missing = [relative for relative in REQUIRED if not (root / relative).is_file()]
    if missing:
        raise AssertionError(f"missing H2 files: {missing}")
    checks.append({"check": "required_files", "status": "passed", "count": len(REQUIRED)})

    scan_files = [
        root / relative for relative in REQUIRED
        if (root / relative).suffix in {".py", ".md", ".yaml", ".lock"}
        and relative != "scripts/h2_validate_package.py"
    ]
    violations = []
    for path in scan_files:
        text = path.read_text()
        for forbidden in FORBIDDEN_PATHS:
            if forbidden in text:
                violations.append(f"{path.relative_to(root)}:{forbidden}")
        if SECRET_VALUE.search(text):
            violations.append(f"{path.relative_to(root)}:credential-like-value")
    if violations:
        raise AssertionError(f"security scan violations: {violations}")
    checks.append({"check": "paths_and_credentials", "status": "passed"})

    lock_rows = []
    for line in (root / "assets/h2_assets.lock").read_text().splitlines():
        if line and not line.startswith("#"):
            parts = line.split("|")
            if len(parts) != 7:
                raise AssertionError(f"bad asset lock row: {line}")
            lock_rows.append(parts)
    if not any(row[1] == "not_required" and int(row[4]) > 20 * 1024**3 for row in lock_rows):
        raise AssertionError("the >20 GiB dataset boundary is not explicit")
    for repo in {row[2] for row in lock_rows if row[0] == "model"}:
        total = sum(int(row[4]) for row in lock_rows if row[2] == repo)
        if total > 20 * 1024**3:
            raise AssertionError(f"model asset crosses boundary: {repo}")
    checks.append({"check": "asset_lock_and_20gib_gate", "status": "passed", "rows": len(lock_rows)})

    head = command(["git", "-C", str(upstream), "rev-parse", "HEAD"])["stdout"]
    if head != EXPECTED_COMMIT:
        raise AssertionError(f"upstream mismatch: {head}")
    checks.append({"check": "upstream_commit", "status": "passed", "commit": head})

    with tempfile.TemporaryDirectory(prefix="vla-h2-static-") as temporary:
        temp = Path(temporary)
        run_root = temp / "runs" / "fixture_h2_static"
        assets = temp / "assets"
        templates = root / "h2_preflight" / "configs"
        command([sys.executable, str(root / "scripts/h2_prepare_run.py"), "init", "--run-root", str(run_root), "--upstream", str(upstream)])
        command([sys.executable, str(root / "scripts/h2_prepare_run.py"), "render-configs", "--run-root", str(run_root), "--upstream", str(upstream), "--asset-root", str(assets), "--templates", str(templates)])
        rendered = sorted((run_root / "configs").glob("*.yaml"))
        if len(rendered) != 3 or any("__H2_" in path.read_text() for path in rendered):
            raise AssertionError("config render did not produce three resolved YAML files")
        checks.append({"check": "init_and_render_fixture", "status": "passed", "configs": [path.name for path in rendered], "evidence_label": "fixture_only"})

        for model in ("random", "smolvla", "openvla"):
            report = command([
                sys.executable, str(root / "scripts/h2_one_episode.py"), "--model", model, "--task-id", "0",
                "--config", str(run_root / "configs" / f"{model}_l0_t1.yaml"), "--upstream", str(upstream), "--dry-run",
            ])
            if "static_check_passed_no_episode" not in str(report["stdout"]):
                raise AssertionError(f"one-episode dry-run boundary missing for {model}")
        checks.append({"check": "one_episode_interfaces", "status": "passed", "evidence_label": "static_no_import_no_episode"})

        command([
            sys.executable, str(root / "scripts/h2_prepare_run.py"), "render-configs", "--run-root", str(run_root),
            "--upstream", str(upstream), "--asset-root", str(assets), "--templates", str(templates), "--trials", "5",
        ])
        for model in ("random", "smolvla", "openvla"):
            report = command([
                sys.executable, str(root / "scripts/h2_pilot.py"), "--model", model,
                "--config", str(run_root / "configs" / f"{model}_l0_t5.yaml"),
                "--upstream", str(upstream), "--dry-run",
            ])
            if '"expected_episodes": 25' not in str(report["stdout"]):
                raise AssertionError(f"pilot dry-run boundary missing for {model}")
        checks.append({"check": "pilot_interfaces_and_episode_idx", "status": "passed", "expected_episodes_per_model": 25, "evidence_label": "static_no_import_no_episode"})

        for asset in ("smolvla", "openvla"):
            report = command([
                sys.executable, str(root / "scripts/h2_fetch_assets.py"), "--lock", str(root / "assets/h2_assets.lock"),
                "--asset", asset, "--asset-root", str(assets),
            ])
            if "dry_run_no_download" not in str(report["stdout"]):
                raise AssertionError(f"asset dry-run boundary missing for {asset}")
        checks.append({"check": "asset_plans", "status": "passed", "evidence_label": "dry_run_no_download"})

        capture = temp / "capture"
        command([sys.executable, str(root / "scripts/h2_capture_command.py"), "--evidence-dir", str(capture), "--", sys.executable, "-c", "print('fixture_h2_capture')"])
        receipt = json.loads((capture / "command.json").read_text())
        if receipt["returncode"] != 0 or "fixture_h2_capture" not in (capture / "stdout.txt").read_text():
            raise AssertionError("command capture fixture failed")
        checks.append({"check": "command_capture_fixture", "status": "passed", "evidence_label": "fixture_only"})

        sys.path.insert(0, str(root / "scripts"))
        from h2_stage_sidecar import ReadOnlyStageSidecar
        class FakeData:
            body_xpos = [[0.0, 0.0, 0.2], [0.0, 0.3, 0.1]]
        class FakeSim:
            data = FakeData()
        class FakeBody:
            pass
        class FakeBase:
            obj_body_id = {"target": 0, "reference": 1}
            sim = FakeSim()
            def get_object(self, name):
                return FakeBody() if name == "target" else None
            def check_gripper_contact(self, body):
                return True
        class FakeEnv:
            env = FakeBase()
            def step(self, action):
                return ({"obs": 1}, 0.0, False, {"success": False})
        fake_env = FakeEnv()
        sidecar_path = run_root / "registry" / "stage_sidecar.csv"
        sidecar = ReadOnlyStageSidecar(fake_env, sidecar_path, "fixture", "fixture_ep", "target", "reference")
        sidecar.install()
        returned = fake_env.step([0.0] * 7)
        sidecar.uninstall()
        if returned[3]["success"] is not False or "uncalibrated" not in sidecar_path.read_text():
            raise AssertionError("read-only sidecar fixture failed")
        checks.append({"check": "stage_sidecar_fixture", "status": "passed", "evidence_label": "synthetic_fixture_no_simulator"})

        pair_fixture = temp / "pair_fixture.csv"
        pair_fixture.write_text(
            "pair_id,condition,level,task_id,seed,init_state_index,changed_factor,target_object,reference_object,relation,instruction,goal_verified,reachable_verified,leakage_check,status,notes\n"
            "p1,a,0,t0,7,0,reference,target,ref_a,on,inst a,1,1,1,ready,fixture\n"
            "p1,b,0,t1,7,0,reference,target,ref_b,on,inst b,1,1,1,ready,fixture\n"
        )
        pair_report = command([
            sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture),
            "--registry", str(root / "assets/sample_episode_registry.csv"), "--require-ready",
        ])
        if '"status": "passed"' not in str(pair_report["stdout"]):
            raise AssertionError("pair manifest fixture failed")
        pair_payload = json.loads(str(pair_report["stdout"]))
        if pair_payload["registry"]["matched"] != 2 or pair_payload["registry"]["recovery"] != 1:
            raise AssertionError("oracle registry fixture counts changed")
        checks.append({"check": "pair_oracle_fixture", "status": "passed", "matched": 2, "recovery": 1, "damage": 0, "evidence_label": "synthetic_fixture_no_pair_claim"})

        command([sys.executable, str(root / "scripts/h2_system_probe.py"), "--mode", "static", "--disk-root", str(temp), "--output", str(run_root / "system" / "mac_static_probe.json")])
        final = command([sys.executable, str(root / "scripts/h2_finalize_evidence.py"), "--run-root", str(run_root)])
        final_payload = json.loads(str(final["stdout"]))
        checks.append({
            "check": "static_probe_and_finalize_fixture", "status": "passed",
            "evidence_label": "current_mac_probe_plus_fixture", "files": final_payload["files"],
            "registry_rows": final_payload["registry_rows"], "missing": final_payload["missing"],
        })

    payload = {
        "status": "passed", "checks": checks,
        "claim_boundary": "Static/dry-run/fixture validation only. No GPU, MuJoCo episode, checkpoint load, model download, training, or Gate decision occurred.",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
