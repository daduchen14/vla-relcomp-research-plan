# RunPod 第一次真实参考运行：创建与费用闸门

> 状态：`已选平台、未购买、未运行`。本页只把 H2/H2.1 变成可执行的云端交接；不代表 RunPod 可用性、GPU 结果或 C0—C7 已通过。价格核验日期：2026-08-25。

## 一、这次租卡要回答什么

唯一目标是完成 H2 的 C0→C7 真实参考运行，验证环境、模型、仿真、episode、pair/oracle 与证据链能否闭环。租卡不是重新选题，也不以本机性能淘汰研究方向；“云实例跑不通”“研究切口没有信号”“用户暂时没学会”必须分栏记录。

## 二、唯一首选配置

在 RunPod 控制台创建一台 **按需（On-Demand）Pod**：

| 项目 | 必须选择 |
|---|---|
| GPU | `1 × A100 SXM 80 GB` |
| 价格闸门 | 控制台 GPU 单价不得高于 `$1.59/h` |
| 镜像 | RunPod 官方 PyTorch，Ubuntu 22.04、CUDA 11.8；官方模板标识可核为 `runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04` |
| CPU/RAM | 目标 `16 vCPU / 125 GB RAM`；不得静默换成明显更低规格 |
| Container Disk | `50 GB` |
| Volume Disk | `300 GB`，挂载点 `/workspace` |
| 网络 | Public IP、暴露 TCP 22、Full SSH 可用 |
| 调度 | 不用 Spot/Interruptible，不开第二台 Pod，不买包月/长期合约 |

选择 A100 SXM 而不是更便宜的 A100 PCIe，是因为当前官方展示的 SXM 规格为 16 vCPU/125 GB RAM，基本满足 H2 的 CPU/RAM 目标；PCIe 规格只有 8 vCPU/117 GB RAM。H100 对本轮不增加必要结论，却把小时成本提高到约 `$2.89–$3.29/h`。

参考依据：

- GPU 当前规格与价格：<https://www.runpod.io/pricing>
- Pod 与磁盘计费：<https://docs.runpod.io/pods/pricing>
- Volume Disk 的 `/workspace` 持久化语义：<https://docs.runpod.io/pods/storage/types>
- Full SSH 与文件传输：<https://docs.runpod.io/pods/configuration/use-ssh>
- 官方 PyTorch 模板示例：<https://docs.runpod.io/api-reference/templates/GET/templates>

控制台是最终价格来源。若没有完全匹配的 A100 SXM、实际单价超过 `$1.59/h`、没有 300 GB Volume Disk 或没有 Full SSH，**停在创建前**，不得自行换 A100 PCIe、H100、48 GB 卡或其他平台。

## 三、30 美元总费用闸门

本轮批准建议不是“一直租到做完”，而是最多 16 GPU·h 的单次参考运行：

| 项目 | 上界算法 | 估算 |
|---|---:|---:|
| GPU | `$1.59 × 16 h` | `$25.44` |
| 300 GB Volume Disk | 官方运行中 `$0.10/GB/月`，按约 16 小时折算 | `< $0.70` |
| 50 GB Container Disk | 官方 `$0.10/GB/月`，按约 16 小时折算 | `< $0.12` |
| 预留 | 价格显示差异、启动/收尾时间 | 约 `$3.74` |
| **总管理上限** | 到达即关停 | **`$30.00`** |

费用规则：

1. 用户未明确同意 `$30` 上限前，不充值、不创建 Pod；RunPod credits 可能不可退，因此只充值控制台允许的最低必要金额。
2. 从 Pod 进入 running 开始记墙钟；每完成一个 checkpoint 都记录累计用时与控制台余额。
3. 运行 12 小时后必须复核剩余任务；预计无法在 16 小时或 30 美元内完成就停止，保存证据后再决定是否追加。
4. `Stop` 后 Volume Disk 仍可能按更高的 idle rate 计费；证据上传完成后应 `Terminate` Pod，并确认是否一并删除不再需要的 Volume。不得只关浏览器标签页。
5. 不以“已经花了钱”为由越过 C0—C7 的失败闸门。

## 四、创建前人工核对单

用户只需在产生费用前核对一次；其余步骤可由执行者接手：

- [ ] 已登录正确的 RunPod 账号，愿意使用该账号产生最多 30 美元费用；
- [ ] 页面显示 `A100 SXM 80 GB × 1`、按需实例和 GPU 单价 `≤ $1.59/h`；
- [ ] 显示约 `16 vCPU / 125 GB RAM`；
- [ ] 镜像是上述官方 Ubuntu 22.04/CUDA 11.8 PyTorch 模板；
- [ ] Container Disk 50 GB、Volume Disk 300 GB、挂载 `/workspace`；
- [ ] Public IP / TCP 22 / Full SSH 可用；
- [ ] 页面预估没有长期承诺、Spot 或第二块 GPU；
- [ ] 最终创建按钮和充值金额由用户确认。

不要在聊天中发送私钥、密码、API token、银行卡信息或完整账单。用户可以只提供控制台生成的公开 SSH 命令，例如 `ssh root@HOST -p PORT`；密钥留在本机。

## 五、SSH 交接

本机目前没有为本项目确认过可用 SSH alias。创建实例后，把控制台公开连接参数写成本机 `~/.ssh/config` 的独立条目；以下只是模板，不包含秘密：

```sshconfig
Host vla-relcomp-h2
  HostName REPLACE_WITH_PUBLIC_HOST
  User root
  Port REPLACE_WITH_PUBLIC_PORT
  IdentityFile REPLACE_WITH_LOCAL_PRIVATE_KEY_PATH
  IdentitiesOnly yes
  ServerAliveInterval 30
  ServerAliveCountMax 4
```

先执行只读连接测试：

```bash
ssh vla-relcomp-h2 'uname -a && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader'
```

只有输出确认单张 A100 SXM 80 GB 后，才传输教程。连接失败时保留控制台实例信息和错误文本，不反复重建付费实例。

先在本机做一次无网络 dry-run，再写入全新的版本目录；脚本拒绝覆盖已有目录，并用第二次 rsync checksum dry-run 核对远端副本：

```bash
export H2_LOCAL_TUTORIAL="/absolute/local/path/to/VLA-RelComp_教程"
python3 "$H2_LOCAL_TUTORIAL/scripts/h2_transfer_to_host.py" \
  --host vla-relcomp-h2 --package-id h2-20260825 \
  --tutorial-root "$H2_LOCAL_TUTORIAL"
# dry-run 的 host、文件数、字节数和目标目录正确后：
python3 "$H2_LOCAL_TUTORIAL/scripts/h2_transfer_to_host.py" \
  --host vla-relcomp-h2 --package-id h2-20260825 \
  --tutorial-root "$H2_LOCAL_TUTORIAL" \
  --execute --acknowledge-remote-write
```

这一步不需要 GitHub token；SSH 私钥仍只由本机 SSH agent/config 使用。若 package id 已存在，换一个新 id，不删除或覆盖旧包。

## 六、RunPod 上的 H2 根目录

RunPod Volume Disk 默认挂载在 `/workspace`，因此覆盖通用 README 中的 `/mnt` 示例：

```bash
export H2_ROOT=/workspace/vla-relcomp-h2
export H2_PACKAGE_ID=h2-20260825
export H2_TUTORIAL="$H2_ROOT/tutorial/$H2_PACKAGE_ID/VLA-RelComp_教程"
export H2_UPSTREAM="$H2_ROOT/upstream/VLA-Arena"
export H2_ASSETS="$H2_ROOT/assets"
export H2_CACHE="$H2_ROOT/cache"
export H2_VENVS="$H2_ROOT/venvs"
export H2_RUN_ID="h2-$(date -u +%Y%m%dT%H%M%SZ)"
export H2_RUN="$H2_ROOT/runs/$H2_RUN_ID"
```

先做一次**硬件保留探针**。它只决定这台付费实例的 Linux/架构、A100 显存、驱动 CUDA 和 300 GB 磁盘是否合格；`uv`、ffmpeg、Git 或 EGL 尚未安装不会误判为硬件失败：

```bash
mkdir -p "$H2_ROOT/preflight"
python3 "$H2_TUTORIAL/scripts/h2_system_probe.py" \
  --mode linux-gpu-host --disk-root "$H2_ROOT" \
  --output "$H2_ROOT/preflight/host_probe.json"
```

退出非零就立即保留输出并停在 C0 之前，不花时间装依赖。退出 0 后初始化 run，并将正式 C0 设为 running：

```bash
python3 "$H2_TUTORIAL/scripts/h2_prepare_run.py" init \
  --run-root "$H2_RUN" --upstream "$H2_UPSTREAM"
python3 "$H2_TUTORIAL/scripts/h2_checkpoint_state.py" \
  --state "$H2_RUN/checkpoint_state.json" --checkpoint C0 --status running
python3 "$H2_TUTORIAL/scripts/h2_system_probe.py" \
  --mode linux-gpu-host --disk-root "$H2_ROOT" \
  --output "$H2_RUN/system/host_probe.json"
```

官方镜像是否已带齐工具必须实测，不能假定。缺少项在这个临时 Pod 内最小补装，并把每条命令留收据：

```bash
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c0-apt-update" -- apt-get update
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c0-apt-install" -- \
  apt-get install -y git curl ffmpeg libegl1 libgl1 libglfw3
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c0-uv-download" -- \
  curl --proto '=https' --tlsv1.2 -LsSf \
  https://astral.sh/uv/0.10.8/install.sh \
  -o "$H2_RUN/tmp/uv-install-0.10.8.sh"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c0-uv-verify" -- \
  python3 "$H2_TUTORIAL/scripts/h2_verify_file.py" \
  --root "$H2_RUN" --path "$H2_RUN/tmp/uv-install-0.10.8.sh" \
  --bytes 68278 \
  --sha256 eae5e1dae89cd0b74d357f549ccd6faa94b2ad6c1d89d78972a625655a4556ae
mkdir -p "$H2_ROOT/tools/bin"
python3 "$H2_TUTORIAL/scripts/h2_capture_command.py" \
  --evidence-dir "$H2_RUN/commands/c0-uv-install" -- \
  env UV_UNMANAGED_INSTALL="$H2_ROOT/tools/bin" \
  sh "$H2_RUN/tmp/uv-install-0.10.8.sh"
export PATH="$H2_ROOT/tools/bin:$PATH"
```

`assets/h2_tooling.lock` 固定安装脚本的版本、URL、字节数和 SHA-256；校验不通过绝不执行。`UV_UNMANAGED_INSTALL` 避免修改 shell profile，并禁用自更新。安装后运行完整 runtime 探针，并只在 JSON 显示 `recommended_80gb_300gb=true` 时结束 C0：

```bash
python3 "$H2_TUTORIAL/scripts/h2_system_probe.py" \
  --mode linux-gpu --disk-root "$H2_ROOT" \
  --output "$H2_RUN/system/probe.json"
python3 "$H2_TUTORIAL/scripts/h2_checkpoint_state.py" \
  --state "$H2_RUN/checkpoint_state.json" --checkpoint C0 --status passed \
  --evidence system/host_probe.json \
  --evidence commands/c0-apt-update --evidence commands/c0-apt-install \
  --evidence commands/c0-uv-download --evidence commands/c0-uv-verify \
  --evidence commands/c0-uv-install --evidence system/probe.json \
  --note "A100 80GB/300GB hardware and Git/uv/ffmpeg/EGL runtime checked"
```

随后严格回到 `h2_preflight/README.md`，从 C1“锁定上游”继续执行；不重复 C0、不提前下载 OpenVLA、不先跑完整 pilot。任一步失败都以实际已存在的证据将 C0 标为 `failed`，再结束实例或新建 retry run，不能把“可补装工具缺失”写成硬件不合格。

## 七、首轮停止与替代规则

- A100 SXM 暂时无库存：停止，等待用户决定“等库存 / 改 A100 PCIe / 改 H100”，不自动替换。
- C0 系统探针失败：最多修复明确缺失的系统包；GPU、磁盘、驱动或 EGL 规格不符则结束实例。
- SmolVLA 单 episode OOM：保存日志，不直接购买 H100；先审计加载路径和进程占用。
- C3 跑通但 C4/C7 无研究信号：这是研究切口结论，不是硬件失败；按 checkpoint matrix 的 Gate 处理。
- 到 16 GPU·h 或 30 美元：无条件停止并封存当前证据，是否追加是新的用户决策。
