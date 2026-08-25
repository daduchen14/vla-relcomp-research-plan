#!/usr/bin/env python3
"""Offline/static validator for the H2 preflight package."""

from __future__ import annotations

import argparse
import ast
import csv
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
    "scripts/h2_pilot.py", "scripts/h2_c7_runner.py", "assets/h2_hf_metadata_fixture.json",
)
FORBIDDEN_PATHS = ("/Users/nokian97", "/home/ubuntu", "/root/")
SECRET_VALUE = re.compile(r"(?:hf_|ghp_)[A-Za-z0-9\-]{12,}|github_pat_[A-Za-z0-9_\-]{12,}")


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
        bad_registry = temp / "bad_c7_registry.csv"
        bad_rows = list(rows) + [{**rows[0], "episode_id": "unregistered", "pair_id": "not-in-manifest"}]
        with bad_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(bad_rows)
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture), "--registry", str(bad_registry), "--require-ready"], expect=2)
        missing_registry = temp / "missing_c7_registry.csv"
        with missing_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows[:-1])
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture), "--registry", str(missing_registry), "--require-ready"], expect=2)
        duplicate_registry = temp / "duplicate_c7_registry.csv"
        with duplicate_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows + [{**rows[0], "episode_id": "duplicate"}])
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture), "--registry", str(duplicate_registry), "--require-ready"], expect=2)
        changed_registry = temp / "changed_c7_registry.csv"
        changed_rows = [{**row, "changed_factor": "unregistered-change"} if index == 0 else row for index, row in enumerate(rows)]
        with changed_registry.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(changed_rows)
        command([sys.executable, str(root / "scripts/h2_pair_oracle_audit.py"), "--manifest", str(pair_fixture), "--registry", str(changed_registry), "--require-ready"], expect=2)
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
        checks.append({"check": "pair_oracle_and_c7_runner_fixtures", "status": "passed", "matched": 4, "recovery": 2, "seeds": [7, 11], "rejected": ["unregistered_row", "missing_row", "duplicate_row", "changed_factor_mismatch", "manifest_path_traversal", "derived_path_escape"], "evidence_label": "synthetic_fixture_no_pair_or_episode_claim"})

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
