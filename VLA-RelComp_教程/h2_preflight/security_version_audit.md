# H2 依赖、版本与安全审计

## 结论

当前为 `静态核验`：H2 路径可以做到不污染系统 Python、不写死作者路径、不记录 token、不修改官方 upstream。真实 Linux/NVIDIA 安装尚未运行，因此依赖能否完整解析仍是 C1 的待测项。

## 锁与冲突面

| 环境 | 项目文件 | 锁定的关键差异 | 纪律 |
|---|---|---|---|
| SmolVLA | `envs/smolvla/pyproject.toml` + `uv.lock` | Python 3.11，Torch 2.7.1，Transformers 4.51.3，Draccus 0.10.0，LeRobot git `76b55e...` | 单独 venv，`uv sync --frozen` |
| OpenVLA | `envs/openvla/pyproject.toml` + `uv.lock` | Python 3.11，Torch 2.2.0，Transformers 4.40.1，Draccus 0.8.0 | 单独 venv，不与 Smol 混用 |
| random/base | 锁定提交的 `envs/base` 只有 `uv.lock`，没有 `pyproject.toml` | README 里 `--project envs/base` 在该提交不是完整项目 | C2 沿用已同步的 Smol venv 运行 random evaluator，不自创第二份依赖解析 |

模型环境不得共用：Torch/Transformers/Draccus 主版与次版差异是实质冲突。量化在首轮全部关闭，不用 4/8 bit 规避未核的 OOM。

## 锁定上游中的两个执行差异

1. `num_trials_per_task: 1` 会迭代 5 个 task，不是单 episode。H2 的 `h2_one_episode.py` 直接调用锁定 evaluator 的初始化、环境和 `run_episode` 函数，同时先核 commit 和函数签名。
2. SmolVLA 模型仓库的可加载文件位于 `pretrained_model/`；项目配置渲染后指向该子目录，并固定 HF revision，而不依赖会移动的 Hub `main`。
3. 官方 evaluator 只输出汇总 JSON；H2 `h2_pilot.py` 不改官方 success/action/env，只包装 `run_task/run_episode`收集逐 episode registry。多 trial 配置用确定性 `episode_idx` 初态选择，避免 `first` 重复同一 init。

两项都是 wrapper/配置层规避，不改 upstream tracked file。若上游接口与锁定断言不符，wrapper 必须 fail closed，不猜测继续。

## 凭据和日志

- 所有公开资产不需 HF token；若服务突然要求登录，在 C1 停止。
- `h2_capture_command.py` 只记录白名单环境变量，拒绝命令行中的 `token/password/secret/api_key`。
- 不打印完整 environment，不复制 `~/.cache/huggingface/token`、SSH key、Git credential helper 内容。
- W&B 固定关闭。外部上传不是 H2 证据必需条件。

## 文件与删除安全

- upstream 必须 detached 到锁定 commit，`git status --short` 必须为空；配置和 patch 只在 run 目录。
- 所有写入根必须是显式 `H2_RUN/H2_ASSETS/H2_CACHE/H2_VENVS`；脚本拒绝 `/`、home 目录和 upstream 子目录。
- 断点恢复依据 state/receipt，不覆盖旧 run。
- 自动清理脚本不删除数据；只给出明确的可再下载目录列表，由实例操作者在证据备份后处理。

## 未解决但不构成 D1 反证

- Linux 上 uv lock 的实际安装和 CUDA wheel/驱动兼容尚未运行；
- EGL 窗口创建、ffmpeg 视频写出尚未运行；
- wrapper 的真实模型导入/推理尚未运行。

这些都是 C0–C3 的正常待测工程项。只有在正确 80 GB Linux/NVIDIA 环境按止损排查后仍无法运行，才进入 Gate/D1 证据评审。
