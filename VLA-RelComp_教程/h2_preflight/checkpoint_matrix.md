# C0–C7 严格检查点

> 本表是 D0—D14 参考运行顺序，不是已完成记录。时间/显存均为 `估计—未运行`，第一次真实运行后覆盖到 run 证据，不反写本表伪装原始估计。

| ID | 范围 | 命令入口 | 成功条件 | 失败分类 | 估计墙钟 / VRAM / 新增磁盘 | 停止条件 | 必须证据 |
|---|---|---|---|---|---|---|---|
| C0 | 系统探针 | `h2_system_probe.py --mode linux-gpu` | Ubuntu x86_64；NVIDIA/EGL 可见；推荐可用盘空间；Git/uv/ffmpeg 可见 | `platform` / `driver` / `disk` / `tooling` | 1–3 min / <0.1 GB / <10 MB | 推荐规格不符先不同步依赖；48 GB 备选须标记 | `system/probe.json` |
| C1 | 上游+资产+环境 | `validate_upstream.py`；`uv sync --frozen`；`h2_fetch_assets.py` | 上游 HEAD/工作树、uv lock、模型 revision/大文件 SHA-256 全符 | `source` / `dependency` / `network` / `checksum` / `capacity` | 30–90 min / <1 GB / Smol 约 12–25 GB（含 env/cache） | SHA/revision 不符；任一未知单项 >20 GB；要求 token | command log、`asset_receipt.json`、`git_status.txt` |
| C2 | random/base 无头 smoke | `h2_pilot.py --model random`，1 trial/task | 5/5 episodes 均以 success/timeout 结束；无 action/吞异常/渲染/证据异常；每 registry 行有确定性视频 | `environment` / `render` / `action` / `evaluation_io` | 10–30 min / <2 GB / 0.2–2 GB | 任一 BDDL/init 不能加载；EGL 排错 45 min 仍失败 | C2 config、stdout/stderr、result JSON、逐行 video、registry |
| C3 | SmolVLA 单 episode | `h2_one_episode.py --model smolvla --task-id 0` | 精确 1 episode；checkpoint 完整加载；action finite/7D；env step 推进；以 official success/timeout 结束；证据齐 | `model_load` / `cuda_oom` / `action` / `environment` / `evaluation_io` | 5–20 min / 待测 / 0.1–1 GB | 80 GB 实例 OOM 先查重复进程；单问题 45 min；Gate 1 最多一工作日 | `one_episode_*.json`、command log、model receipt、video、GPU 快照 |
| C4 | SmolVLA 小 pilot | `h2_pilot.py --model smolvla`；L0 先 5 tasks×5 trials=25，通过后 L1/L2 同协议 | registry 唯一键完整且逐行 video 非空；任一 action/video/吞异常审计失败则命令失败；L0 `k/25+CI`、中位墙钟、峰值显存可算 | `infrastructure` / `model` / `evaluation` / `data_quality` / `evidence_io` | L0 1–3 h；75 episodes 3–6 h / 待测 / 2–20 GB | L0 完成前不看 L1/L2；若 L0<8/25 或大面积模型失败，进 C5；不训练 | task-level registry、逐行 videos、Gate 2 草表、三级 configs/logs/results |
| C5 | 必要时 OpenVLA | 先 `h2_one_episode.py --model openvla`，过后同 C4 pilot | 单 episode 过后才扩 pilot；按 Gate 2 冻结规则唯一选择 | 同 C3/C4，另记 `quantization=off` | 下载 15.08 GB；单 episode 10–30 min；pilot 4–8 h / 待测 / 18–40 GB | SmolVLA 已过 Gate 2 则跳过；48 GB OOM 不擅自量化；80 GB 仍 OOM 按 Gate 排错 | OpenVLA receipt/config/log/result/video，Gate 2 表 |
| C6 | BDDL+状态旁路 | `parse_bddl.py`；项目侧只读 logger/patch | 15 BDDL/init 对齐；官方 success 主指标；原始接触/位置/距离可写；`definition_status=uncalibrated` | `state_unavailable` / `identity` / `logger_side_effect` / `threshold_unready` | 1–3 h / 沿用主模型 / 1–5 GB | logger 改 action/observation/physics 立即停；状态最终不可得记 Gate 3 硬风险 | patch hash、trajectory raw fields、5 条视频人工抽查 |
| C7 | 最小 pair/oracle pilot | `h2_c7_runner.py` 从 manifest 运行；2–3 pair family；至少 2 seeds；每 condition 为 none+language oracle | manifest 是唯一允许集；pair_family/pair_id/condition/seed/init 显式绑定；goal/instruction 同步；可达；恢复与damage同报 | `pair_invalid` / `unreachable` / `leakage` / `oracle_damage` / `not_reproducible` / `evidence_io` | 2–4 h / 沿用主模型 / 2–10 GB | 缺/重/未登记/字段漂移即失败；pair 不成立或不可重复依 Gate 3/D1 停；不设计 D15 修复 | pair manifest、oracle spec、C7专用 registry、逐行 video/result、原始计数/CI、Gate 3 |

## 扩展命令的唯一顺序

1. C2 random：使用 `random_l0.yaml`，`num_trials_per_task=1`，总数应为 5。
2. C3 Smol 单 episode：wrapper 固定 `task_id=0` 与一个 init index。
3. C4 Smol L0 25：把渲染配置的 trials 设 5，用官方 CLI 跑 5 tasks。L0 Gate 达标后才以相同预登记顺序跑 L1/L2。
4. C5 仅由 Gate 2 触发：先 OpenVLA 单 episode，再 L0 25，然后决定是否需 L1/L2。
5. C6/C7 仅使用 Gate 2 选定的主诊断模型。

任一检查点失败时，保留原目录并新建 `retry-01`；不覆盖旧结果，不把重试后的成功隐藏前次异常。

## 可复制命令

### C2 random/base smoke（5 episodes）

random evaluator 使用 C1 已同步的 SmolVLA 隔离环境；这只是避开锁定提交中不完整的 `envs/base` 项目，不加载 SmolVLA 权重。

```bash
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c2-random" -- \
  uv run --project "$H2_UPSTREAM/envs/smolvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_pilot.py" --model random \
  --config "$H2_RUN/configs/random_l0_t1.yaml" \
  --upstream "$H2_UPSTREAM" --run-root "$H2_RUN"
```

### C3 SmolVLA 单 episode

```bash
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c3-smolvla-one" -- \
  uv run --project "$H2_UPSTREAM/envs/smolvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_one_episode.py" \
  --model smolvla --task-id 0 --config "$H2_RUN/configs/smolvla_l0_t1.yaml" \
  --upstream "$H2_UPSTREAM" --run-root "$H2_RUN"
```

### C4 SmolVLA L0 25；通过后才渲染 L1/L2

```bash
python3 "$H2_TUTORIAL/scripts/h2_prepare_run.py" render-configs \
  --run-root "$H2_RUN" --upstream "$H2_UPSTREAM" --asset-root "$H2_ASSETS" \
  --templates "$H2_TUTORIAL/h2_preflight/configs" --level 0 --trials 5
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c4-smolvla-l0-t5" -- \
  uv run --project "$H2_UPSTREAM/envs/smolvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_pilot.py" --model smolvla \
  --config "$H2_RUN/configs/smolvla_l0_t5.yaml" \
  --upstream "$H2_UPSTREAM" --run-root "$H2_RUN"
```

L0 Gate 达标后，分别以 `--level 1 --trials 5` 和 `--level 2 --trials 5` 渲染新文件，命令收据目录也分开。

### C5 条件触发 OpenVLA

```bash
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/openvla"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c5-openvla-sync" -- \
  uv sync --project "$H2_UPSTREAM/envs/openvla" --frozen
uv run --project "$H2_UPSTREAM/envs/openvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_fetch_assets.py" \
  --lock "$H2_TUTORIAL/assets/h2_assets.lock" --asset openvla \
  --asset-root "$H2_ASSETS" --acknowledge-download
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c5-openvla-one" -- \
  uv run --project "$H2_UPSTREAM/envs/openvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_one_episode.py" \
  --model openvla --task-id 0 --config "$H2_RUN/configs/openvla_l0_t1.yaml" \
  --upstream "$H2_UPSTREAM" --run-root "$H2_RUN"
```

单 episode 过后，按 C4 同样渲染 `openvla_l0_t5.yaml`，再以 `h2_pilot.py --model openvla` 运行；不改量化开关。`h2_pilot.py` 只在锁定 evaluator 外层记录逐 episode 墙钟、action 有限性、init index 和 official success，模型在整个 pilot 中只加载一次。

### C6 只读 raw-state sidecar

锁定 L0 `task_id=0` 的 BDDL goal 是 `On(tomato_3, porcelain_bowl_3)`，因此下面精确记录 `tomato_3` 和 `porcelain_bowl_3`。该 BDDL 的 `obj_of_interest` 是 `tomato_2`，与 goal target 不同；阶段诊断必须以 goal 实例为准，这一差异已静态核验，不可用 `obj_of_interest` 猜目标。

```bash
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"  # 或 Gate 2 选定的 openvla venv
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c6-sidecar-one" -- \
  uv run --project "$H2_UPSTREAM/envs/smolvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_one_episode.py" \
  --model smolvla --task-id 0 --config "$H2_RUN/configs/smolvla_l0_t1.yaml" \
  --upstream "$H2_UPSTREAM" --run-root "$H2_RUN" \
  --stage-sidecar "$H2_RUN/registry/stage_sidecar.csv" \
  --target-object tomato_3 --reference-object porcelain_bowl_3 --episode-tag c6-sidecar
```

先只保存 raw contact/z/distance/official success，三个 threshold 必须为空。开关 sidecar 的同 seed/init 对照通过后才扩大。

### C7 pair/oracle 预检、运行与结果审计

```bash
python3 "$H2_TUTORIAL/scripts/h2_pair_oracle_audit.py" \
  --manifest "$H2_RUN/registry/pair_manifest.csv" --require-ready \
  --output "$H2_RUN/results/c7_pair_precheck.json"
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c7-language-oracle" -- \
  uv run --project "$H2_UPSTREAM/envs/smolvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_c7_runner.py" --model smolvla \
  --config "$H2_RUN/configs/smolvla_l0_t1.yaml" --upstream "$H2_UPSTREAM" \
  --manifest "$H2_RUN/registry/pair_manifest.csv" --run-root "$H2_RUN"
python3 "$H2_TUTORIAL/scripts/h2_pair_oracle_audit.py" \
  --manifest "$H2_RUN/registry/pair_manifest.csv" \
  --registry "$H2_RUN/registry/c7_episode_registry.csv" --require-ready \
  --output "$H2_RUN/results/c7_pair_oracle_audit.json"
```

第一条要求同一 `pair_family` 至少两个 seed，每个 `pair_id` 两个 condition；runner 为每个 condition 生成 none+language_oracle；最后一条以 manifest 为唯一允许集，拒绝未登记、缺行、重复或冻结字段不一致，只计 matched recovery/damage，不自动下 Gate 3 结论。视觉 oracle 未实现，不能写成可运行。
