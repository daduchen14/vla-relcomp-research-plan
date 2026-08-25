# Day 0：开工前诊断、证据纪律与工具最小闭环

## 当日目标，以及为什么服务于 VLA-RelComp

今天不跑模型。目标是建立一个以后能回答“我到底运行了什么”的工作台：分清教程、上游代码、项目代码和实验证据；确认本机工具；学会使用锁定提交；建立不泄密、不伪造、不盲贴命令的记录习惯。VLA-RelComp 的研究价值依赖匹配反事实和可复现证据，如果 Day 0 连版本、目录和证据标签都混乱，后面的“恢复率”没有可信来源。

完成后你应该能独立解释：为什么当前 Mac 的 `nvidia-smi` 缺失不等于项目失败；为什么 `main`、模型名和数据集名不够精确；为什么“静态核验”不能写成“实测跑通”。

## 前置知识和开始前自检

只假设你会打开终端。先不问术语定义，逐项实际做：

- 能否用 `pwd` 回答当前目录？
- 能否用 `ls` 看见文件而不修改文件？
- 能否说出绝对路径与相对路径的差别？
- 是否知道终端粘贴命令会立即影响当前目录？
- 是否愿意把 token、密码、云密钥永远留在仓库外？

若前三项答不出，仍可继续；本日操作会现场补齐。若最后一项不能做到，本项目不得开始。

## 具体场景与最小例子

你看到日志写着“OpenVLA 运行成功”。这句话不可复现，因为缺少：官方仓库 commit、模型 revision、suite、level、task、seed、init state、配置副本、程序退出码和证据路径。今天要把它改成一种可核验陈述：

> `估计—未运行`：计划在 VLA-Arena `babe582…`、`extrapolation_preposition_combinations`、L0、固定 seed/init state 上运行 OpenVLA；当前只核验命令与代码路径，未加载 checkpoint，未得到显存、时延或成功率。

前一句听起来更有进展，后一句才是研究记录。

## 零基础知识讲义

### 为什么现在需要“路径”

计算机不会理解“那个教程文件”。绝对路径从磁盘根开始，例如 `/Users/.../x`；相对路径从当前工作目录开始，例如 `方向筛选/VLA-RelComp_教程`。`pwd` 回答“我站在哪里”，`ls` 回答“这里有什么”。同一条相对命令在不同目录可能指向不同文件，所以每段教程都写明从哪个目录执行。

### 为什么现在需要“环境”

Python 解释器、第三方包和系统库共同构成环境。不同项目可能需要冲突版本，虚拟环境就像给项目一个独立工具箱。VLA-Arena 锁定 Python 3.11，并用 `uv` 管理多个模型环境；本机 Python 版本只负责运行本教程的纯标准库脚本，不能据此声称官方环境兼容。

### 为什么现在需要“版本”

Git commit 是代码快照的不可变地址；branch `main` 会移动。模型 revision、数据 revision 与代码 commit 分别回答“哪套权重、哪份数据、哪版程序”。只记模型展示名相当于只记书名、不记版次。教程锁文件位于 `assets/upstream.lock`。

### 四类证据

- `实测`：当前机器真的运行过，保存命令、输出与退出码。
- `静态核验`：打开锁定源码或官方材料确认存在，但未完成运行。
- `估计—未运行`：只描述预期形态或资源范围。
- `待用户执行`：必须由你亲手做、口述或在获批环境完成。

这四类不是完成度排名。Mac 上无法做 CUDA 推理时，诚实的静态核验比伪造“跑通”更有价值。

### Agent 的正确角色

Agent 可生成脚手架、查路径和帮助排错；你必须能说清输入、改动、输出和失败边界。每次复制命令前做“三问”：当前目录是什么？会写哪些文件？失败后如何停止或回滚？任何要求输入 token 的步骤立刻停止，不把 token 粘进聊天、脚本或日志。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 看完会什么 | 暂时跳过 |
|---|---|---|---:|---|---|
| `../assets/证据标签与目录约定.md` | 建立统一证据口径 | 全文 | 15–25 分钟 | 给任一步正确贴标签 | 无 |
| `../assets/upstream.lock` | 看真实版本冻结 | 全文 | 5 分钟 | 找到 commit、paper v4、suite 注册名 | 无 |
| 官方仓库 README | 防止教程自创命令 | Quick Start、Installation | 20–30 分钟 | 说出 `uv run --project` 形式与系统要求 | leaderboard 投稿 |
| Git 官方书 | 理解 commit/working tree | https://git-scm.com/book/en/v2/Getting-Started-What-is-Git%3F 的 “Snapshots, Not Differences” | 20–35 分钟 | 用快照解释 commit | 分支高级操作 |

完整官方链接和固定提交见 `../assets/official_source_index.md`。

## 操作步骤、状态与预期输出

以下命令均从工作目录 `/Users/nokian97/Documents/Codex/2026-08-24/x` 开始。

### 1. 只读定位（`待用户执行`；制作者已 `实测`）

```bash
pwd
ls '方向筛选/VLA-RelComp_教程'
```

正常预期输出第一行是工作目录绝对路径；列表中应有 `assets`、`scripts`、`validation` 和 `progress_log.md`。路径不一致意味着你站错目录，不要靠不断加 `../` 猜；先 `cd` 到工作目录再重试。

### 2. 本机探针（`待用户执行`；制作者已 `实测`）

```bash
python3 '方向筛选/VLA-RelComp_教程/scripts/system_probe.py' \
  > '方向筛选/VLA-RelComp_教程/validation/day00_system_probe_user.json'
```

输出是 JSON：`platform`/`machine` 表示当前系统架构；`python` 与 `python_executable` 表示真正调用的解释器；`tools.git` 和 `tools.uv` 是工具版本；`nvidia_smi` 在 Mac 上预计为 `null`。最后这一项只说明当前机器没有 NVIDIA 管理工具，不是 Gate 1 失败，因为 Gate 1 明确发生在正确 Linux/NVIDIA 环境。

### 3. 锁文件人工核对（`静态核验`）

```bash
sed -n '1,80p' '方向筛选/VLA-RelComp_教程/assets/upstream.lock'
```

检查完整 commit 为 `babe582ebffc82b979b77964a7e56417d02f63a4`，显示名与注册名不同。若官方 `main` 以后移动，不直接把 lock 改成新值：先比较目标 suite、evaluator、success 和 init-state 相关差异，写变更审查后决定。

### 4. 创建学习记录（`待用户执行`）

复制 `progress_log.md` 中当天条目到你的个人日志，写四句话：今天的问题、执行命令、证据路径、不能推出的结论。不要覆盖制作者验证日志。

### 5. 正式 GPU 命令预演（`估计—未运行`）

```bash
# 只阅读，不在当前 Mac 执行
uv run --project envs/smolvla vla-arena eval --model smolvla --config <项目配置副本>
```

预期形态是：首次创建隔离环境、加载配置、下载/读取模型、创建仿真环境并输出 episode 日志。当前阶段没有运行，因此教程不给任何真实显存、时延或成功率数字。

## 输出解释练习

把以下五项分别归类：

1. `git rev-parse HEAD` 打印锁定 SHA；
2. 论文表格报告某模型成功率；
3. 当前 Mac `nvidia-smi: command not found`；
4. 你预计 A100 能加载模型；
5. 你本人三分钟口述录音。

参考分类：1 是对本地克隆的实测版本证据；2 是论文事实而非本项目实测；3 是本机环境实测且不构成 D1 反证；4 是估计—未运行；5 是待用户执行的掌握证据。

## 在 VLA-Arena / VLA-RelComp 真实代码和数据中的位置

- 官方版本：仓库根目录 Git commit；本教程 `assets/upstream.lock` 保存冻结值。
- 模型环境：`envs/base`、`envs/smolvla`、`envs/openvla`。
- 官方默认配置：`vla_arena/configs/evaluation/*.yaml`，只读；正式项目复制到自己的 `configs/`。
- 目标任务：`vla_arena/vla_arena/bddl_files/extrapolation_preposition_combinations/`。
- 本项目证据：未来 `VLA-RelComp/experiments/registry`、`logs`、`results`、`videos`；不要放进 upstream。

## 常见错误、诊断顺序、备用路线与止损

1. 路径不存在：先 `pwd`，再逐级 `ls`；止损 15 分钟。
2. `python` 与 `python3` 不同：记录 `which python3` 和版本，不改系统 Python；止损 20 分钟。
3. `uv` 缺失：今天可继续纯 Python 脚本；正式环境按 uv 官方安装页处理；止损 30 分钟。
4. Mac 没有 CUDA：正确记录为平台边界，继续静态课，不安装来源不明的“CUDA for Mac”；止损 5 分钟。
5. GitHub 暂时不可达：使用已锁定的本地源码/证据索引，记录时间后继续；止损 20 分钟。
6. 命令要求 token：立即停止，这属于必须请求用户的条件。

不要用 `sudo pip install`，不要整段粘贴未读脚本，不要把失败输出删掉后声称成功。

## 时间预算、完成线与选做

正常耗时 5.5–7.5 小时：认知 90–120 分钟，跟做 90 分钟，独立改动 45–75 分钟，记录 45 分钟，口述/复写 45–60 分钟，缓冲与排错不超过 60 分钟。

- 最低完成线：能运行探针，指出四类证据差异，找到锁定 commit 和 suite 注册名。
- 标准完成线：能从错误目录自行恢复；完成个人 Day 0 日志；不看答案口述目录与版本纪律。
- 提前完成选做：用 `git show --stat babe582` 只读查看锁定提交改了哪些任务场景，不展开历史筛选。

## 当日交付物

- `validation/day00_system_probe_user.json`（你亲自运行）；
- 个人 Day 0 记录：问题、命令、证据、不能推出的结论；
- 60–90 秒口述稿：“为什么没有 GPU 不等于项目失败”；
- 自检表：无 token、无模型、无数据、大文件未下载。

## 自测题、参考答案与复试口述

1. 为什么 `main` 不是足够的版本记录？
2. `静态核验` 与 `实测` 的边界是什么？
3. 当前 Mac 没有 CUDA，会触发 D1 推翻吗？
4. 为什么 upstream 与项目代码必须分开？
5. 哪些情况必须暂停？

参考答案：1. `main` 会移动，commit 才固定快照。2. 前者只确认资料/路径/逻辑存在，后者实际执行并留输出。3. 不会；D1 门槛在正确 Linux/NVIDIA 环境。4. 便于追溯官方版本、保存清晰补丁并避免拉取更新污染实验。5. 付费/凭据、超 20 GB 单项下载、难撤销外部影响、重大官方变化、直接撞题、必读缺失或实质冲突。

复试口述问题：给你一条“模型跑通了”的日志，你需要追问哪些字段才相信？建议答到代码/模型/数据版本、配置、suite/level/task、seed/init state、退出状态、原始日志/视频/结果和异常分类。
