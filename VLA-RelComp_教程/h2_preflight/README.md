# H2 Linux/NVIDIA 参考运行预检包

> 状态：`H2.1 Mac 免费实测 + 锁定源码静态核验`。本包没有执行 VLA-Arena episode、没有加载 checkpoint、没有产生 GPU 性能或 Gate 1–3 结论。

RunPod 首次实跑的唯一推荐配置、30 美元费用闸门、SSH 交接与停止条件见 [`runpod_first_run.md`](runpod_first_run.md)。它是“已选平台、未购买、未运行”的执行页；控制台价格或规格不符时不得静默替换。

私有 GitHub fresh clone、分支/基线校验和教程根自动定位的唯一入口见 [`fresh_clone_quickstart.md`](fresh_clone_quickstart.md)。主教程的冻结画像是零科研基础、但已有 408/C 与少量 Python/Linux/Git；真正零编程基础者先做 `assets/零编程基础前置轨说明.md` 的就绪检查，不扩充原 14 天。

## 一、唯一目标与边界

本包把 D0—D14 的真实参考运行准备到：拿到一台 Linux/NVIDIA 实例后，可按检查点复制执行，且每步有版本、命令、时间、退出码、GPU 快照、日志、结果和哈希可追溯。唯一 suite 仍是 `extrapolation_preposition_combinations`，不训练、不扩第二 suite，不提前设计 D15 以后修复。

锁定项：

- VLA-Arena：`babe582ebffc82b979b77964a7e56417d02f63a4`；
- SmolVLA：`ef87aa3f97a4feaed69c93b9ed2014bba07acf8a`；
- OpenVLA：`779caf6517b5aeb9ed33882812a0c5f03f48c86e`；
- 完整来源、文件大小与大文件 SHA-256 见 `assets/h2_assets.lock`。

## 二、实例规格（工程估计，未运行）

| | 推荐规格 | 备选规格 |
|---|---|---|
| OS/架构 | Ubuntu 22.04 LTS, x86_64 | Ubuntu 20.04+ x86_64 |
| GPU | A100/H100 80 GB | L40S/A6000 48 GB；仅单进程，OpenVLA OOM 即停 |
| CPU/RAM | 16 vCPU / 128 GB | 8 vCPU / 64 GB |
| 本地 NVMe 可用 | 300 GB | 220 GB；不得下载训练数据 |
| 驱动/渲染 | NVIDIA 驱动可被 `nvidia-smi` 识别；EGL | 同左 |

上游声明 Ubuntu 20.04+、Python 3.11、CUDA 11.8+。H2 选 Ubuntu 22.04 是为降低系统库差异；Python 由 `uv` 的隔离项目提供，不更改系统 Python。首次付费只需租一台推荐规格实例；不同时租第二台。

预估下载量：代码 Git pack 约 0.41 GB（当前完整工作树约 1.3 GB），SmolVLA 评测权重 0.91 GB，OpenVLA 约 15.08 GB（仅条件触发），uv/PyTorch/CUDA 依赖约 10–30 GB；不下载 32.47 GB 训练数据。预估 GPU 占用：Smol-only 准备与 pilot 先预留 4–8 GPU·h；若 Gate 2 规则触发 OpenVLA，总预留 8–16 GPU·h。这些数字必须在第一个真实 episode 后用实测墙钟重算。

## 三、目录与一次性变量

以大容量挂载目录为根，不要把 cache 放到系统盘。下列 `/mnt` 是通用示例；RunPod 必须按 `runpod_first_run.md` 改为 `/workspace/vla-relcomp-h2`：

```bash
export H2_ROOT=/mnt/vla-relcomp-h2
export H2_TUTORIAL="$H2_ROOT/tutorial/VLA-RelComp_教程"
export H2_UPSTREAM="$H2_ROOT/upstream/VLA-Arena"
export H2_ASSETS="$H2_ROOT/assets"
export H2_CACHE="$H2_ROOT/cache"
export H2_VENVS="$H2_ROOT/venvs"
export H2_RUN_ID="h2-$(date -u +%Y%m%dT%H%M%SZ)"
export H2_RUN="$H2_ROOT/runs/$H2_RUN_ID"
export HF_HOME="$H2_CACHE/huggingface"
export UV_CACHE_DIR="$H2_CACHE/uv"
export XDG_CACHE_HOME="$H2_CACHE/xdg"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export CUDA_VISIBLE_DEVICES=0
mkdir -p "$H2_ROOT/upstream" "$H2_ASSETS" "$H2_CACHE" "$H2_VENVS" "$H2_ROOT/runs"
```

`H2_TUTORIAL` 可来自私有分支 clone，也可由本机安全上传；不把 GitHub/HF token 写入上述变量、脚本或日志。下载完并通过 receipt/SHA-256 后，`h2_one_episode.py` 会在模型导入前自动设置 `HF_HUB_OFFLINE=1` 与 `TRANSFORMERS_OFFLINE=1`，真实 episode 只从本地已校验目录加载。

## 四、最短可执行路径

### 0. 只读系统探针

```bash
mkdir -p "$H2_RUN/system"
python3 "$H2_TUTORIAL/scripts/h2_system_probe.py" \
  --mode linux-gpu --disk-root "$H2_ROOT" --output "$H2_RUN/system/probe.json"
```

退出 0 才继续。探针不安装包，不启动 CUDA kernel。Ubuntu 系统包若缺失，仅安装 `git curl ffmpeg libegl1 libgl1 libglfw3`；这一步可能需要实例管理员权限，不在本机预先执行。

### 1. 初始化证据树

```bash
python3 "$H2_TUTORIAL/scripts/h2_prepare_run.py" init \
  --run-root "$H2_RUN" --upstream "$H2_UPSTREAM"
```

证据树固定为 `system/ commands/ configs/ logs/ results/ videos/ registry/ hashes/ gates/ patches/ tmp/`。脚本拒绝把 run 目录放进 upstream，避免污染官方副本。

每个检查点都用状态机开始和收尾，不手改 `checkpoint_state.json`。例如 C0：

```bash
python3 "$H2_TUTORIAL/scripts/h2_checkpoint_state.py" \
  --state "$H2_RUN/checkpoint_state.json" --checkpoint C0 --status running \
  --evidence system/probe.json
# 系统探针退出 0 且人工核对成功条件后：
python3 "$H2_TUTORIAL/scripts/h2_checkpoint_state.py" \
  --state "$H2_RUN/checkpoint_state.json" --checkpoint C0 --status passed \
  --evidence system/probe.json --note "C0 success conditions checked"
```

状态机拒绝跳级、`pending→passed`、非 C5 的 `skipped`、不存在或越界的终态证据，以及从 `passed/failed/skipped` 重开。失败必须以 `--failure-class` 结束当前 run，再新建 `retry-01`，不能覆盖原记录。

### 2. 锁定上游

```bash
git clone https://github.com/PKU-Alignment/VLA-Arena.git "$H2_UPSTREAM"
git -C "$H2_UPSTREAM" switch --detach babe582ebffc82b979b77964a7e56417d02f63a4
git -C "$H2_UPSTREAM" status --short
python3 "$H2_TUTORIAL/scripts/validate_upstream.py" \
  "$H2_UPSTREAM"
```

`status --short` 必须为空。不在 upstream 内改 YAML、evaluator 或 BDDL；H2 差异只位于教程 wrapper、渲染后配置和 `patches/`。

### 3. 隔离环境（先 SmolVLA）

```bash
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c1-smolvla-sync" -- \
  uv sync --project "$H2_UPSTREAM/envs/smolvla" --frozen
```

OpenVLA 只在检查点 C5 触发时执行，并改用 `UV_PROJECT_ENVIRONMENT="$H2_VENVS/openvla"`。不使用 `sudo pip`、system `pip`或 conda base。

### 4. 下载与校验必需权重

```bash
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"
uv run --project "$H2_UPSTREAM/envs/smolvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_fetch_assets.py" \
  --lock "$H2_TUTORIAL/assets/h2_assets.lock" \
  --asset smolvla --asset-root "$H2_ASSETS" --acknowledge-download
```

下载前，脚本必须实时调用官方 Hugging Face `model_info(files_metadata=True)`：先按与 `snapshot_download` 完全相同的 allowlist 计算实际选择集和逐文件 logical bytes 总和（不拿可能含去重口径的 repo `usedStorage` 代替），再要求选择集与 lock 精确相等、离线加载必需文件齐全且总量不超过 20 GiB。元数据不可用、出现未锁文件或缺文件都在下载前失败。receipt 保存实际选择集、总字节、allowlist、revision 与逐文件校验；OpenVLA 同理但只在 C5 执行。训练数据标为 `not_required` 且脚本拒绝下载。`h2_hf_metadata_fixture.json` 只供离线测试，带 fixture 时下载器明确拒绝真实下载。

### 5. 渲染运行配置

```bash
python3 "$H2_TUTORIAL/scripts/h2_prepare_run.py" render-configs \
  --run-root "$H2_RUN" --upstream "$H2_UPSTREAM" \
  --asset-root "$H2_ASSETS" --templates "$H2_TUTORIAL/h2_preflight/configs"
```

配置只写到 `$H2_RUN/configs`，模型路径指向已校验的本地 snapshot，W&B/replacements/扰动全关闭。

### 6. 按检查点执行

严格按 `checkpoint_matrix.md` 的 C0→C7 执行，不跳级。单 episode 必须通过项目 wrapper：官方 evaluator 的 `num_trials_per_task: 1` 会跑 5 个 task，不等于单 episode。

```bash
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c3-smolvla-one" -- \
  uv run --project "$H2_UPSTREAM/envs/smolvla" --frozen \
  python "$H2_TUTORIAL/scripts/h2_one_episode.py" \
  --model smolvla --task-id 0 \
  --config "$H2_RUN/configs/smolvla_l0_t1.yaml" \
  --upstream "$H2_UPSTREAM" --run-root "$H2_RUN"
```

`h2_one_episode.py`、`h2_pilot.py` 与 `h2_c7_runner.py` 共用同一 fail-closed 口径：除 finite 7D action 和非空视频外，还捕获锁定 evaluator 记录后吞掉的 `Episode error:`；任一信号出现均写入 exception 并非零退出。pilot 由 wrapper 为每个 registry 行写一个确定性 MP4，官方 `save_video_mode` 固定为 `none`，避免重复视频和无法逐行连接。

### 6.1 C7 最短可执行路径

先从 `assets/pair_manifest_template.csv` 生成 `$H2_RUN/registry/pair_manifest.csv`。`pair_family` 表示同一反事实设计，`pair_id` 表示其中一个 seed 的执行单元；每个 `pair_id` 恰有两个 condition，同一 family 至少两个不同 seed。每行显式给出受限语法 `target=...; action=place; relation=...; reference=...`，并完成 goal、可达与泄漏核验。

```bash
python3 "$H2_TUTORIAL/scripts/h2_pair_oracle_audit.py" \
  --manifest "$H2_RUN/registry/pair_manifest.csv" --require-ready
export UV_PROJECT_ENVIRONMENT="$H2_VENVS/smolvla"  # 或 Gate 2 选定的 openvla
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
python3 "$H2_TUTORIAL/scripts/analyze_c7.py" \
  --manifest "$H2_RUN/registry/pair_manifest.csv" \
  --registry "$H2_RUN/registry/c7_episode_registry.csv" \
  --output "$H2_RUN/results/c7_pair_statistics.json"
```

runner 只加载一次模型，但为 manifest 每行构造独立 config 副本，使全局 RNG、环境 seed 和 registry seed 一致；每个 condition 依次运行 `none` 与 `language_oracle`，重建环境并显式清理可用的 policy state。语言 oracle 是 `privileged_diagnostic=true`、`final_method_eligible=false`；`analyze_c7.py` 只在 manifest-bound registry 通过后输出四格、recovery/damage、Wilson CI、精确 McNemar 和 task/seed/init 分层。视觉 oracle 统一标为“规范已有、执行未实现、不可运行”，没有伪命令。

### 6.2 只读统一入口

`scripts/vla_relcomp.py` 是现有 wrapper 的薄导航层，不重写 evaluator：

```bash
python3 "$H2_TUTORIAL/scripts/vla_relcomp.py" status --run-root "$H2_RUN"
python3 "$H2_TUTORIAL/scripts/vla_relcomp.py" resume --run-root "$H2_RUN"
python3 "$H2_TUTORIAL/scripts/vla_relcomp.py" smoke --kind random \
  --upstream "$H2_UPSTREAM" --run-root "$H2_RUN" \
  --config "$H2_RUN/configs/random_l0_t1.yaml"
```

Fresh clone 中的 `doctor` 和 `setup --dry-run` 用法见 `fresh_clone_quickstart.md`。`doctor/status/resume` 只读；`setup --dry-run` 只打印计划；`smoke` 只检查前置状态、锁定源码/配置并打印 argv，不执行 episode。真实命令仍必须在另行授权后，先通过 `h2_checkpoint_state.py` 将当前检查点设为 `running`。统一入口不自动作 Gate 判断。

### 7. 断点恢复、完成与清理

- 恢复：对照 `$H2_RUN/checkpoint_state.json`，只重跑最后一个非 `passed` 检查点；不删失败日志。
- 完成：运行 `h2_finalize_evidence.py`，生成 SHA-256 manifest，检查 registry 路径存在。
- 清理：首选关停/销毁云实例。仅在已备份 `runs/$H2_RUN_ID` 后删除可再下载的 `cache/`、`venvs/`和 `assets/models/`；不递归删除 `$H2_ROOT`、`runs/`或 upstream。

## 五、证据口径

- `当前实测`：H2 脚本语法、干跑、目录初始化、配置渲染、fixture 和安全扫描在 Mac 通过。
- `静态核验`：上游 commit、CLI、evaluator 接口、模型 revision/文件大小已核。
- `估计—未运行`：所有 GPU 小时、显存、episode 墙钟、下载用时和磁盘增量。
- `等待授权`：真实实例登录/付费、实例上的模型下载与任何凭据使用。

不得把 `--dry-run`、fixture、Mac 探针或静态 AST 检查写成 GPU 结果。

## 六、逐 episode 视频保留策略

- C2/C4 pilot 与 C7 每个登记 episode 只保存一个 256×256、30 fps 的确定性 MP4；registry 必须指向该真实非空文件。
- 同一 run 内目标视频已存在时拒绝覆盖；重试新建 `retry-01` run，保留失败证据。
- 在 Gate 人工复核和 `sha256_manifest.json` 封存完成前保留全部视频。备份后可删除可再生成的 cache/venv/model，但不删除 registry 所引用的视频。
- 这是以可审计性换磁盘；C4 75 episodes 仍包含在 2–20 GB 估计内，首次实跑后以真实字节数修订。
