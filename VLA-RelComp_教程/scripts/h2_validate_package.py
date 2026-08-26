#!/usr/bin/env python3
"""Offline/static validator for the H2 preflight package."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


EXPECTED_COMMIT = "babe582ebffc82b979b77964a7e56417d02f63a4"
REQUIRED = (
    "h2_preflight/README.md", "h2_preflight/runpod_first_run.md", "h2_preflight/checkpoint_matrix.md", "h2_preflight/security_version_audit.md",
    "h2_preflight/evidence_and_resume.md", "h2_preflight/fresh_clone_quickstart.md", "h2_preflight/configs/random_l0.yaml",
    "h2_preflight/configs/smolvla_l0.yaml", "h2_preflight/configs/openvla_l0.yaml",
    "assets/h2_assets.lock", "assets/h2_tooling.lock", "assets/h2_stage_sidecar_schema.csv",
    "scripts/h2_system_probe.py", "scripts/h2_prepare_run.py", "scripts/h2_checkpoint_state.py", "scripts/h2_transfer_to_host.py", "scripts/h2_verify_file.py", "scripts/h2_capture_command.py",
    "scripts/h2_fetch_assets.py", "scripts/h2_one_episode.py", "scripts/h2_finalize_evidence.py",
    "scripts/h2_stage_sidecar.py", "scripts/h2_pair_oracle_audit.py",
    "scripts/h2_pilot.py", "scripts/h2_c7_runner.py", "scripts/analyze_c7.py", "scripts/vla_relcomp.py",
    "scripts/validate_fresh_checkout.py", "assets/h2_hf_metadata_fixture.json", "assets/零编程基础前置轨说明.md",
    "validation/06_H2.5可移植性修复报告.md",
)
FORBIDDEN_PATHS = ("/Users/", "/home/ubuntu", "/root/", "方向筛选/VLA-RelComp_教程", "work/VLA-Arena-upstream")
SECRET_VALUE = re.compile(r"(?:hf_|ghp_)[A-Za-z0-9\-]{12,}|github_pat_[A-Za-z0-9_\-]{12,}")
RELEASE_TAG = "vla-relcomp-h2.5.1"
PRIVATE_CLONE_COMMAND = f"git clone --branch {RELEASE_TAG} --single-branch https://github.com/daduchen14/vla-relcomp-research-plan.git"
EMBEDDED_HTTPS_CREDENTIAL = re.compile(r"https://[^/\s:@]+(?::[^@\s/]*)?@github\.com", re.IGNORECASE)


def command(argv: list[str], expect: int = 0) -> dict[str, object]:
    completed = subprocess.run(
        argv, text=True, capture_output=True, check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != expect:
        raise AssertionError(f"command returned {completed.returncode}, expected {expect}: {argv}\n{completed.stdout}\n{completed.stderr}")
    return {"argv": argv, "returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def release_fixture(tutorial: Path, parent: Path) -> tuple[Path, Path]:
    repo = parent / "release-fixture"
    repo.mkdir()
    copied_tutorial = repo / "VLA-RelComp_教程"
    shutil.copytree(tutorial, copied_tutorial, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    command(["git", "-C", str(repo), "init"])
    command(["git", "-C", str(repo), "switch", "-c", "h2-linux-nvidia-preflight"])
    command(["git", "-C", str(repo), "config", "user.name", "VLA-RelComp Fixture"])
    command(["git", "-C", str(repo), "config", "user.email", "fixture@example.invalid"])
    command(["git", "-C", str(repo), "add", "--", "VLA-RelComp_教程"])
    command(["git", "-C", str(repo), "commit", "-m", "fixture: audited release"])
    command(["git", "-C", str(repo), "tag", RELEASE_TAG])
    return repo, copied_tutorial


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

    repository_docs = [root.parent / "README.md", root.parent / "26_教程任务交接说明.md"]
    missing_repository_docs = [path.name for path in repository_docs if not path.is_file()]
    if missing_repository_docs:
        raise AssertionError(f"missing active repository docs: {missing_repository_docs}")
    scan_files = repository_docs + sorted(root.rglob("*.md"))
    scan_files.extend(
        path for path in sorted((root / "scripts").glob("*.py"))
        if path.name not in {"h2_validate_package.py", "validate_fresh_checkout.py"}
    )
    scan_files.extend(sorted((root / "h2_preflight" / "configs").glob("*.yaml")))
    violations = []
    for path in scan_files:
        text = path.read_text()
        for forbidden in FORBIDDEN_PATHS:
            if forbidden in text:
                violations.append(f"{path.relative_to(root.parent)}:{forbidden}")
        if SECRET_VALUE.search(text):
            violations.append(f"{path.relative_to(root.parent)}:credential-like-value")
    if violations:
        raise AssertionError(f"security scan violations: {violations}")
    checks.append({"check": "active_repository_and_tutorial_docs_paths_and_credentials", "status": "passed", "files": len(scan_files)})

    fresh_clone_text = (root / "h2_preflight/fresh_clone_quickstart.md").read_text()
    if PRIVATE_CLONE_COMMAND not in fresh_clone_text:
        raise AssertionError("fresh-clone guide is missing the HTTPS fixed-release-tag command")
    if EMBEDDED_HTTPS_CREDENTIAL.search(fresh_clone_text):
        raise AssertionError("fresh-clone guide embeds credentials in a GitHub HTTPS URL")
    if "SSH 是可选替代，不是默认入口" not in fresh_clone_text:
        raise AssertionError("fresh-clone guide does not mark SSH as optional")
    checks.append({
        "check": "private_fresh_clone_transport", "status": "passed",
        "default": "https_fixed_release_tag_single_branch", "release_tag": RELEASE_TAG,
        "credentials": "external_manager_no_embedded_secret",
        "ssh": "optional_only_after_public_key_check", "evidence_label": "static_document_contract_no_network",
    })

    help_scripts = (
        "validate_upstream.py", "h2_prepare_run.py", "h2_checkpoint_state.py", "h2_system_probe.py",
        "h2_one_episode.py", "h2_pilot.py", "h2_c7_runner.py", "h2_pair_oracle_audit.py",
        "analyze_c7.py", "vla_relcomp.py",
    )
    for script in help_scripts:
        command([sys.executable, str(root / "scripts" / script), "--help"])
    command([sys.executable, str(root / "scripts" / "validate_upstream.py"), str(upstream)])
    checks.append({
        "check": "documented_cli_help_and_arguments", "status": "passed", "scripts": list(help_scripts),
        "validate_upstream_positional_args": 1, "evidence_label": "read_only_no_episode",
    })

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

    tooling_rows = [line.split("|") for line in (root / "assets/h2_tooling.lock").read_text().splitlines() if line and not line.startswith("#")]
    expected_tooling = [["uv-installer", "0.10.8", "https://astral.sh/uv/0.10.8/install.sh", "68278", "eae5e1dae89cd0b74d357f549ccd6faa94b2ad6c1d89d78972a625655a4556ae"]]
    if tooling_rows != expected_tooling:
        raise AssertionError("H2 tooling lock changed")
    checks.append({"check": "tooling_lock", "status": "passed", "tools": ["uv-installer@0.10.8"]})

    head = command(["git", "-C", str(upstream), "rev-parse", "HEAD"])["stdout"]
    if head != EXPECTED_COMMIT:
        raise AssertionError(f"upstream mismatch: {head}")
    checks.append({"check": "upstream_commit", "status": "passed", "commit": head})
    expected_returns = {
        "random": "vla_arena/models/random/evaluator.py",
        "smolvla": "vla_arena/models/smolvla/evaluator.py",
        "openvla": "vla_arena/models/openvla/evaluator.py",
    }
    for model, relative in expected_returns.items():
        tree = ast.parse((upstream / relative).read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_episode")
        tuple_returns = [node for node in ast.walk(function) if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple)]
        if not tuple_returns or any(len(node.value.elts) != 3 for node in tuple_returns):
            raise AssertionError(f"{model} run_episode no longer has an all-3-tuple return contract")
    checks.append({"check": "locked_evaluator_return_contracts", "status": "passed", "models": sorted(expected_returns)})

    with tempfile.TemporaryDirectory(prefix="vla-h2-static-") as temporary:
        temp = Path(temporary)
        run_root = temp / "runs" / "fixture_h2_static"
        assets = temp / "assets"
        templates = root / "h2_preflight" / "configs"
        command([sys.executable, str(root / "scripts/h2_prepare_run.py"), "init", "--run-root", str(run_root), "--upstream", str(upstream)])
        state_path = run_root / "checkpoint_state.json"
        c0_evidence = run_root / "system" / "state-fixture.json"
        c0_evidence.write_text("{}\n")
        c0_digest = hashlib.sha256(c0_evidence.read_bytes()).hexdigest()
        command([sys.executable, str(root / "scripts/h2_verify_file.py"), "--root", str(run_root), "--path", str(c0_evidence), "--bytes", str(c0_evidence.stat().st_size), "--sha256", c0_digest])
        command([sys.executable, str(root / "scripts/h2_verify_file.py"), "--root", str(run_root), "--path", str(c0_evidence), "--bytes", str(c0_evidence.stat().st_size + 1), "--sha256", c0_digest], expect=2)
        command([sys.executable, str(root / "scripts/h2_verify_file.py"), "--root", str(run_root / "system"), "--path", str(root / "README.md"), "--bytes", "0", "--sha256", "0" * 64], expect=2)
        checks.append({"check": "locked_file_verifier_fixture", "status": "passed", "accepted": ["exact bytes and sha256"], "rejected": ["size mismatch", "path escape"], "evidence_label": "fixture_only"})
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C0", "--status", "running", "--evidence", "system/state-fixture.json"])
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C0", "--status", "passed", "--evidence", "system/state-fixture.json", "--note", "fixture success conditions checked"])
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C0", "--status", "running"], expect=2)
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C2", "--status", "running"], expect=2)
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C1", "--status", "passed", "--evidence", "system/state-fixture.json", "--note", "illegal direct pass"], expect=2)
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C1", "--status", "running", "--evidence", "commands/c1-planned"])
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C1", "--status", "failed", "--evidence", "system/state-fixture.json", "--note", "fixture failure", "--failure-class", "dependency", "--elapsed-minutes", "1.5", "--retry-run", "retry-01"], expect=2)
        (run_root / "commands" / "c1-planned").mkdir()
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C1", "--status", "failed", "--evidence", "system/state-fixture.json", "--note", "fixture failure", "--failure-class", "dependency", "--elapsed-minutes", "1.5", "--retry-run", "retry-01"])
        command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(state_path), "--checkpoint", "C1", "--status", "running"], expect=2)
        state_fixture = json.loads(state_path.read_text())
        if state_fixture["C0"]["status"] != "passed" or state_fixture["C1"]["status"] != "failed" or len(state_fixture["C1"]["history"]) != 2:
            raise AssertionError("checkpoint state transitions were not persisted")
        checks.append({"check": "checkpoint_state_machine_fixture", "status": "passed", "accepted": ["C0 pending->running->passed", "C1 pending->running->failed"], "rejected": ["terminal restart", "predecessor bypass", "pending direct pass", "terminal with missing planned evidence"], "evidence_label": "fixture_only"})
        release_repo, release_tutorial = release_fixture(root, temp)
        setup_plan = command([
            sys.executable, str(release_tutorial / "scripts/vla_relcomp.py"), "setup", "--dry-run",
            "--repo-root", str(release_repo), "--tutorial-root", str(release_tutorial), "--upstream", str(upstream),
        ])
        if "dry_run_no_commands_executed" not in str(setup_plan["stdout"]):
            raise AssertionError("unified setup unexpectedly executed or changed its boundary")
        release_doctor = command([
            sys.executable, str(release_tutorial / "scripts/vla_relcomp.py"), "doctor",
            "--repo-root", str(release_repo), "--tutorial-root", str(release_tutorial), "--upstream", str(upstream),
        ])
        if '"head_matches_release_tag": true' not in str(release_doctor["stdout"]):
            raise AssertionError("doctor did not confirm the exact release tag")
        drift = release_repo / "post-release-drift.txt"
        drift.write_text("unreviewed fixture commit\n")
        command(["git", "-C", str(release_repo), "add", "--", drift.name])
        command(["git", "-C", str(release_repo), "commit", "-m", "fixture: post-release drift"])
        command([
            sys.executable, str(release_tutorial / "scripts/vla_relcomp.py"), "setup", "--dry-run",
            "--repo-root", str(release_repo), "--tutorial-root", str(release_tutorial), "--upstream", str(upstream),
        ], expect=2)
        command([
            sys.executable, str(release_tutorial / "scripts/vla_relcomp.py"), "doctor",
            "--repo-root", str(release_repo), "--tutorial-root", str(release_tutorial), "--upstream", str(upstream),
        ], expect=2)
        status_report = command([sys.executable, str(root / "scripts/vla_relcomp.py"), "status", "--run-root", str(run_root)])
        resume_report = command([sys.executable, str(root / "scripts/vla_relcomp.py"), "resume", "--run-root", str(run_root)])
        if '"next_checkpoint": "C1"' not in str(status_report["stdout"]) or "create_new_retry_run" not in str(resume_report["stdout"]):
            raise AssertionError("unified status/resume did not preserve terminal failure semantics")
        checks.append({
            "check": "unified_setup_status_resume_fixture", "status": "passed",
            "accepted": ["setup_plan_only_at_exact_release_tag", "doctor_exact_release_tag", "read_only_status", "terminal_failure_resume_guidance"],
            "rejected": ["setup_after_post_tag_commit", "doctor_after_post_tag_commit"],
            "evidence_label": "fixture_only_no_command_execution",
        })
        transfer = command([sys.executable, str(root / "scripts/h2_transfer_to_host.py"), "--host", "vla-relcomp-h2", "--package-id", "fixture-package", "--tutorial-root", str(root)])
        transfer_payload = json.loads(str(transfer["stdout"]))
        if transfer_payload["status"] != "dry_run_no_remote_write" or transfer_payload["remote_destination"] != "/workspace/vla-relcomp-h2/tutorial/fixture-package/VLA-RelComp_教程":
            raise AssertionError("transfer dry-run plan changed")
        command([sys.executable, str(root / "scripts/h2_transfer_to_host.py"), "--host", "-oProxyCommand=bad", "--package-id", "fixture-package", "--tutorial-root", str(root)], expect=2)
        command([sys.executable, str(root / "scripts/h2_transfer_to_host.py"), "--host", "vla-relcomp-h2", "--package-id", "fixture-package", "--tutorial-root", str(root), "--execute"], expect=2)
        checks.append({"check": "ssh_transfer_handoff_fixture", "status": "passed", "accepted": ["new versioned destination dry-run"], "rejected": ["unsafe host option", "execute without acknowledgement"], "evidence_label": "fixture_only_no_ssh"})
        command([sys.executable, str(root / "scripts/h2_prepare_run.py"), "render-configs", "--run-root", str(run_root), "--upstream", str(upstream), "--asset-root", str(assets), "--templates", str(templates)])
        rendered = sorted((run_root / "configs").glob("*.yaml"))
        if len(rendered) != 3 or any("__H2_" in path.read_text() for path in rendered):
            raise AssertionError("config render did not produce three resolved YAML files")
        checks.append({"check": "init_and_render_fixture", "status": "passed", "configs": [path.name for path in rendered], "evidence_label": "fixture_only"})
        smoke_plan = command([
            sys.executable, str(root / "scripts/vla_relcomp.py"), "smoke", "--kind", "random",
            "--config", str(run_root / "configs/random_l0_t1.yaml"), "--upstream", str(upstream),
            "--run-root", str(run_root), "--tutorial-root", str(root),
        ], expect=2)
        if '"status": "blocked"' not in str(smoke_plan["stdout"]) or "C1 must be passed" not in str(smoke_plan["stdout"]):
            raise AssertionError("unified smoke did not fail closed on checkpoint prerequisites")
        navigation_run = temp / "runs" / "fixture_navigation_ready"
        command([sys.executable, str(root / "scripts/h2_prepare_run.py"), "init", "--run-root", str(navigation_run), "--upstream", str(upstream)])
        navigation_evidence = navigation_run / "system" / "navigation-fixture.json"
        navigation_evidence.write_text("{}\n")
        navigation_state = navigation_run / "checkpoint_state.json"
        for checkpoint in ("C0", "C1"):
            command([sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(navigation_state), "--checkpoint", checkpoint, "--status", "running"])
            command([
                sys.executable, str(root / "scripts/h2_checkpoint_state.py"), "--state", str(navigation_state),
                "--checkpoint", checkpoint, "--status", "passed", "--evidence", "system/navigation-fixture.json",
                "--note", f"{checkpoint} synthetic navigation prerequisite",
            ])
        command([
            sys.executable, str(root / "scripts/h2_prepare_run.py"), "render-configs", "--run-root", str(navigation_run),
            "--upstream", str(upstream), "--asset-root", str(assets), "--templates", str(templates),
        ])
        ready_smoke = command([
            sys.executable, str(root / "scripts/vla_relcomp.py"), "smoke", "--kind", "random",
            "--config", str(navigation_run / "configs/random_l0_t1.yaml"), "--upstream", str(upstream),
            "--run-root", str(navigation_run), "--tutorial-root", str(root),
        ])
        if '"status": "ready_to_request_execution"' not in str(ready_smoke["stdout"]) or "command_not_executed" not in str(ready_smoke["stdout"]):
            raise AssertionError("unified smoke did not print a ready, non-executed command plan")
        checks.append({
            "check": "unified_smoke_prerequisite_fixture", "status": "passed",
            "accepted": ["C2 argv printed after C1 fixture passed"], "rejected": ["C2 plan while C1 failed"],
            "evidence_label": "static_plan_only_no_episode",
        })

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

        expected_asset_plans = {"smolvla": (3, 906721036), "openvla": (20, 15085154899)}
        for asset in ("smolvla", "openvla"):
            report = command([
                sys.executable, str(root / "scripts/h2_fetch_assets.py"), "--lock", str(root / "assets/h2_assets.lock"),
                "--asset", asset, "--asset-root", str(assets), "--metadata-fixture", str(root / "assets/h2_hf_metadata_fixture.json"),
            ])
            if "dry_run_no_download" not in str(report["stdout"]):
                raise AssertionError(f"asset dry-run boundary missing for {asset}")
            asset_payload = json.loads(str(report["stdout"]))
            expected_files, expected_bytes = expected_asset_plans[asset]
            if (asset_payload["files_selected"], asset_payload["actual_metadata_bytes"]) != (expected_files, expected_bytes):
                raise AssertionError(f"{asset} actual metadata selection changed")
        checks.append({"check": "asset_plans", "status": "passed", "plans": {name: {"files": values[0], "logical_bytes": values[1]} for name, values in expected_asset_plans.items()}, "evidence_label": "official_metadata_fixture_dry_run_no_download"})

        from h2_fetch_assets import ASSET_MAP, build_download_plan, official_metadata, read_lock
        lock = read_lock(root / "assets/h2_assets.lock")
        smol_revision = next(str(row["revision"]) for row in lock if row["repo"] == ASSET_MAP["smolvla"])
        smol_metadata = official_metadata("smolvla", ASSET_MAP["smolvla"], smol_revision, root / "assets/h2_hf_metadata_fixture.json")
        bad_metadata = {**smol_metadata, "files": list(smol_metadata["files"]) + [{"path": "pretrained_model/unlocked.bin", "size": 1}]}
        try:
            build_download_plan("smolvla", lock, bad_metadata)
            raise AssertionError("unlocked snapshot file was accepted")
        except ValueError as exc:
            if "selection and lock differ" not in str(exc):
                raise
        checks.append({"check": "asset_metadata_allowlist_fail_closed_fixture", "status": "passed", "evidence_label": "official_metadata_fixture_no_download"})

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

        from h2_one_episode import ActionAudit, EpisodeErrorCapture
        from h2_pilot import action_evidence_errors, pilot_outcome, write_episode_video
        pilot_video = temp / "pilot_fixture.mp4"
        def fixture_writer(frames, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture-video")
            return len(frames)
        path_value, video_error, count = write_episode_video([1], pilot_video, fixture_writer)
        if video_error or count != 1 or path_value != str(pilot_video):
            raise AssertionError("pilot video evidence success fixture failed")
        if not write_episode_video([], temp / "empty.mp4", lambda frames, path: 0)[1]:
            raise AssertionError("empty frames were accepted")
        def broken_writer(frames, path):
            raise OSError("fixture encoder failure")
        if "video_write_failed" not in write_episode_video([1], temp / "broken.mp4", broken_writer)[1]:
            raise AssertionError("video writer failure was accepted")
        code, failures = pilot_outcome(1, [{"episode_id": "fixture", "exception": "action_audit_failed:calls=0"}], [], "")
        if code == 0 or not failures:
            raise AssertionError("pilot action/evidence failure remained fail-open")
        partial_audit = ActionAudit(); partial_audit.calls = 2; partial_audit.last_dims = {7}; partial_audit.all_finite = True
        captured = EpisodeErrorCapture()
        wrapped_log = captured.wrap(lambda message: None)
        captured.begin(); wrapped_log("Episode error: fixture after partial rollout"); captured.end()
        swallowed = action_evidence_errors(partial_audit, captured.errors)
        if not swallowed or pilot_outcome(1, [{"episode_id": "partial", "exception": swallowed[0]}], [], "")[0] == 0:
            raise AssertionError("swallowed evaluator exception after partial actions/frames remained fail-open")
        for script_name in ("h2_one_episode.py", "h2_pilot.py", "h2_c7_runner.py"):
            if "EpisodeErrorCapture" not in (root / "scripts" / script_name).read_text():
                raise AssertionError(f"{script_name} does not share swallowed-error capture")
        c7_source = (root / "scripts/h2_c7_runner.py").read_text()
        smol_source = (upstream / "vla_arena/models/smolvla/evaluator.py").read_text()
        open_source = (upstream / "vla_arena/models/openvla/experiments/robot/robot_utils.py").read_text()
        if "getattr(policy, \"reset\"" not in c7_source or "policy.reset()" not in smol_source or "action_queue" in open_source or "deque" in open_source:
            raise AssertionError("C7 policy reset/stateless OpenVLA contract changed")
        checks.append({"check": "episode_evidence_and_fail_closed_fixtures", "status": "passed", "paths": ["C3", "pilot", "C7"], "cases": ["video_written", "empty_frames", "encoder_failure", "action_calls_zero", "swallowed_exception_after_partial_rollout", "policy_state_reset"], "evidence_label": "synthetic_fixture_and_locked_source_no_episode"})

        pair_fixture = temp / "pair_fixture.csv"
        pair_fixture.write_text(
            "pair_family,pair_id,condition,model_id,model_revision,suite,level,task_id,seed,init_state_index,changed_factor,target_object,reference_object,relation,instruction,language_oracle_instruction,goal_verified,reachable_verified,leakage_check,status,notes\n"
            "family1,p1-s7,a,VLA-Arena/smolvla-vla-arena,ef87aa3f97a4feaed69c93b9ed2014bba07acf8a,extrapolation_preposition_combinations,0,0,7,0,reference,target,ref_a,on,inst a,target=target; action=place; relation=on; reference=ref_a,1,1,1,ready,fixture\n"
            "family1,p1-s7,b,VLA-Arena/smolvla-vla-arena,ef87aa3f97a4feaed69c93b9ed2014bba07acf8a,extrapolation_preposition_combinations,0,1,7,0,reference,target,ref_b,on,inst b,target=target; action=place; relation=on; reference=ref_b,1,1,1,ready,fixture\n"
            "family1,p1-s11,a,VLA-Arena/smolvla-vla-arena,ef87aa3f97a4feaed69c93b9ed2014bba07acf8a,extrapolation_preposition_combinations,0,0,11,0,reference,target,ref_a,on,inst a,target=target; action=place; relation=on; reference=ref_a,1,1,1,ready,fixture\n"
            "family1,p1-s11,b,VLA-Arena/smolvla-vla-arena,ef87aa3f97a4feaed69c93b9ed2014bba07acf8a,extrapolation_preposition_combinations,0,1,11,0,reference,target,ref_b,on,inst b,target=target; action=place; relation=on; reference=ref_b,1,1,1,ready,fixture\n"
        )
        pair_registry = run_root / "registry" / "c7_episode_registry.csv"
        fields = next(csv.reader((root / "assets/episode_registry_schema.csv").open()))
        videos = run_root / "videos" / "c7-fixture"
        results = run_root / "results" / "c7-fixture"
        c7_log = run_root / "logs" / "c7-fixture.log"
        c7_log.write_text("synthetic fixture log; no episode\n")
        rows = []
        for pair_id, seed in (("p1-s7", "7"), ("p1-s11", "11")):
          for condition, task_id, reference, instruction, before, after in (("a", "0", "ref_a", "inst a", "0", "1"), ("b", "1", "ref_b", "inst b", "1", "1")):
            for intervention, success in (("none", before), ("language_oracle", after)):
                video = videos / f"{pair_id}-{condition}-{intervention}.mp4"
                result = results / f"{pair_id}-{condition}-{intervention}.json"
                video.parent.mkdir(parents=True, exist_ok=True); result.parent.mkdir(parents=True, exist_ok=True)
                video.write_bytes(b"fixture-video"); result.write_text("{}\n")
                row = {field: "" for field in fields}
                row.update({"run_id": "fixture", "episode_id": f"{pair_id}-{condition}-{intervention}", "model_id": "VLA-Arena/smolvla-vla-arena", "model_revision": "ef87aa3f97a4feaed69c93b9ed2014bba07acf8a", "suite": "extrapolation_preposition_combinations", "level": "0", "task_id": task_id, "seed": seed, "init_state_index": "0", "pair_family": "family1", "pair_id": pair_id, "condition": condition, "changed_factor": "reference", "instruction_original": instruction, "instruction_variant": instruction if intervention == "none" else f"target=target; action=place; relation=on; reference={reference}", "intervention": intervention, "target_object": "target", "reference_object": reference, "relation": "on", "success": success, "video_path": str(video), "log_path": str(c7_log), "result_path": str(result)})
                rows.append(row)
        with pair_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        pair_report = command([
            sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture),
            "--registry", str(pair_registry), "--require-ready",
        ])
        if '"status": "passed"' not in str(pair_report["stdout"]):
            raise AssertionError("pair manifest fixture failed")
        pair_payload = json.loads(str(pair_report["stdout"]))
        if pair_payload["registry"]["matched"] != 4 or pair_payload["registry"]["recovery"] != 2 or pair_payload["registry"]["manifest_allowed_rows"] != 8:
            raise AssertionError("oracle registry fixture counts changed")
        from h2_pair_oracle_audit import parse_language_oracle
        if parse_language_oracle("target=target; action=place; relation=on; reference=ref_a")["reference"] != "ref_a":
            raise AssertionError("locked four-field language oracle was rejected")
        try:
            parse_language_oracle("target=target; source=drawer; action=place; relation=on; reference=ref_a")
            raise AssertionError("unregistered language-oracle source field was accepted")
        except ValueError:
            pass
        statistics = command([
            sys.executable, str(root / "scripts/analyze_c7.py"), "--manifest", str(pair_fixture),
            "--registry", str(pair_registry),
        ])
        statistics_payload = json.loads(str(statistics["stdout"]))
        overall = statistics_payload["overall"]
        if (
            overall["matched"] != 4 or overall["cells"] != {
                "failure_failure": 0, "failure_success": 2, "success_failure": 0, "success_success": 2,
            }
            or overall["recovery"]["rate"] != 1.0 or overall["damage"]["rate"] != 0.0
            or overall["mcnemar"]["two_sided_exact_p"] != 0.5
            or set(statistics_payload["strata"]) != {"task_id", "seed", "init_state_index"}
        ):
            raise AssertionError("C7 paired statistics fixture changed")
        all_success_registry = temp / "all_success_c7_registry.csv"
        all_success_rows = [{**row, "success": "1"} for row in rows]
        with all_success_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(all_success_rows)
        all_success = command([
            sys.executable, str(root / "scripts/analyze_c7.py"), "--manifest", str(pair_fixture),
            "--registry", str(all_success_registry),
        ])
        all_success_payload = json.loads(str(all_success["stdout"]))["overall"]
        if all_success_payload["recovery"] != {"numerator": 0, "denominator": 0, "rate": None, "wilson95": None}:
            raise AssertionError("zero recovery denominator was not reported as null")
        bad_registry = temp / "bad_c7_registry.csv"
        bad_rows = list(rows) + [{**rows[0], "episode_id": "unregistered", "pair_id": "not-in-manifest"}]
        with bad_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(bad_rows)
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture), "--registry", str(bad_registry), "--require-ready"], expect=2)
        missing_registry = temp / "missing_c7_registry.csv"
        with missing_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows[:-1])
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture), "--registry", str(missing_registry), "--require-ready"], expect=2)
        command([sys.executable, str(root / "scripts/analyze_c7.py"), "--manifest", str(pair_fixture), "--registry", str(missing_registry)], expect=2)
        duplicate_registry = temp / "duplicate_c7_registry.csv"
        with duplicate_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows + [{**rows[0], "episode_id": "duplicate"}])
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture), "--registry", str(duplicate_registry), "--require-ready"], expect=2)
        changed_registry = temp / "changed_c7_registry.csv"
        changed_rows = [{**row, "changed_factor": "unregistered-change"} if index == 0 else row for index, row in enumerate(rows)]
        with changed_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(changed_rows)
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture), "--registry", str(changed_registry), "--require-ready"], expect=2)
        exception_registry = temp / "exception_c7_registry.csv"
        exception_rows = [{**row, "exception": "fixture error"} if index == 0 else row for index, row in enumerate(rows)]
        with exception_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(exception_rows)
        command([sys.executable, str(root / "scripts/analyze_c7.py"), "--manifest", str(pair_fixture), "--registry", str(exception_registry)], expect=2)
        traversal_manifest = temp / "traversal_manifest.csv"
        traversal_manifest.write_text(pair_fixture.read_text().replace("family1,p1-s7,a", "../escape,p1-s7,a", 1))
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(traversal_manifest), "--require-ready"], expect=2)
        from dataclasses import dataclass
        from h2_c7_runner import safe_derived_path, with_episode_seed
        @dataclass(frozen=True)
        class SeedFixture:
            seed: int
            marker: str = "unchanged"
        original_seed_cfg = SeedFixture(seed=7)
        seed_11_cfg = with_episode_seed(original_seed_cfg, 11)
        if original_seed_cfg.seed != 7 or seed_11_cfg.seed != 11 or seed_11_cfg.marker != "unchanged":
            raise AssertionError("per-episode immutable seed config fixture failed")
        try:
            safe_derived_path(run_root / "results" / "c7", "..", "escaped.json")
            raise AssertionError("C7 derived path traversal was accepted")
        except ValueError:
            pass
        c7_static = command([sys.executable, str(root / "scripts/h2_c7_runner.py"), "--model", "smolvla", "--config", str(run_root / "configs" / "smolvla_l0_t1.yaml"), "--upstream", str(upstream), "--manifest", str(pair_fixture), "--dry-run"])
        if '"expected_episodes": 8' not in str(c7_static["stdout"]):
            raise AssertionError("C7 runner dry-run did not bind two-seed episodes")
        checks.append({
            "check": "pair_oracle_c7_runner_and_statistics_fixtures", "status": "passed",
            "matched": 4, "recovery": 2, "seeds": [7, 11], "mcnemar_exact_p": 0.5,
            "strata": ["task_id", "seed", "init_state_index"], "zero_denominator": "null",
            "rejected": ["unregistered_row", "missing_row", "duplicate_row", "episode_exception", "changed_factor_mismatch", "language_source_field", "manifest_path_traversal", "derived_path_escape"],
            "evidence_label": "synthetic_fixture_no_pair_or_episode_claim",
        })

        command([sys.executable, str(root / "scripts/h2_system_probe.py"), "--mode", "static", "--disk-root", str(temp), "--output", str(run_root / "system" / "mac_static_probe.json")])
        probe_payload = json.loads((run_root / "system" / "mac_static_probe.json").read_text())
        required_qualification = {"recommended_hardware_80gb_300gb", "backup_hardware_48gb_220gb", "runtime_prerequisites_ready", "recommended_80gb_300gb", "backup_48gb_220gb", "linux_gpu_execution_eligible"}
        if set(probe_payload["qualification"]) != required_qualification or "linux-gpu-host" not in (root / "scripts/h2_system_probe.py").read_text():
            raise AssertionError("two-stage host/runtime probe contract changed")
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
