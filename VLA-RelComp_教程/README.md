# VLA-RelComp 前 14 天零基础实操教程

这是正式项目决策 D1 的教程与轻量验证版。它不重选方向、不声称完成 70 天研究，也不把计划输出写成实验结果。主教程面向“零科研基础，但有 408/C 基础并接触过少量 Python、Linux 和 Git”的冻结画像，目标是按 Day 0—14 建立可解释、可复现的 VLA-Arena 诊断开工能力。

真正零编程基础者不直接进入 Day 0：先按 [`assets/零编程基础前置轨说明.md`](assets/零编程基础前置轨说明.md) 做就绪检查。该说明只定义前置门槛和补齐边界，不往原 14 天叠加第二套课程。

## 使用顺序

1. 首次从 GitHub 获取时，先按 [`h2_preflight/fresh_clone_quickstart.md`](h2_preflight/fresh_clone_quickstart.md) 锁定受审发布 tag 和目录；
2. 阅读 `00_课程使用说明与学习地图.md` 与 `assets/证据标签与目录约定.md`；
3. 从 `day00/README.md` 顺序做到 `day14/README.md`，不得跳过 Gate；
4. 每天先做开始前自检，再读指定范围、运行最小实验、改变一个变量、保存交付物、最后脱离 Agent 口述；
5. 答案位于每日末尾；先答后看；
6. `scripts/` 是教程/执行 wrapper；官方 VLA-Arena 始终是独立、锁定 commit 的只读克隆，路径通过 `VLA_ARENA_UPSTREAM` 或 H2 的 `H2_UPSTREAM` 显式传入。

## 预计总时长

Day 0—3 约 26–32 小时；Day 4—8 约 30–39 小时；Day 9—14 约 37–47 小时；总计约 93–118 小时。每日按约 8 小时设计，但以交付物和口述通过为准。原估计不因个体实测被静默覆盖；个人日志另记真实耗时。

## 证据状态

- `实测`：纯 Python 探针、action chunk fixture、BDDL 解析、stage fixture、registry/CI 分析和结构校验已在当前 Mac 运行，日志见 `validation/`；
- `静态核验`：官方仓库提交、15 BDDL/15 init、注册名、evaluator、success、配置和论文页码已核；
- `估计—未运行`：VLA checkpoint 推理、CUDA 显存、仿真墙钟、真实成功率、pair/oracle 结果；
- `待用户执行`：学习作业、口述、正式 Linux/NVIDIA Gate 1–3。

## 软硬件闸门

本地免费阶段需要终端、Git、Python 3；脚本只用标准库。正式参考运行需要 Ubuntu 20.04+、Python 3.11、CUDA 11.8+ 与 NVIDIA GPU/EGL，推荐首台 A100/H100 80GB。购买/租用、账号/token、单项超过 20GB 下载必须先请求用户。

Gate 1（D4）验证单 episode；Gate 2（D8）选择可分析模型；Gate 3（D14）验证反事实/oracle 切口。Mac 无 CUDA 不构成失败。

## 完成本教程后能做什么

学习者能解释 VLM/VLA 数据流和全部核心概念，读目标 BDDL 与 evaluator，建立 episode registry，报告计数/区间，设计只读阶段探针、匹配 pair 和诊断 oracle，识别数据泄漏，并用三分钟讲清研究问题与证据边界。

## 下一阶段

Linux/NVIDIA 执行前的 H2/H2.5 包位于 `h2_preflight/`：包含 fresh clone 唯一入口、只读 doctor/setup/status/resume/smoke 导航、系统/磁盘规格、C0–C7 检查点、版本与下载前实际资产闸门、隔离环境、EGL、单 episode/pilot/C7 wrapper、配对统计、逐 episode 视频、证据封存与断点恢复。`h2_preflight/runpod_first_run.md` 已固定首次 RunPod 配置、16 GPU·h/30 美元费用闸门、版本化 SSH 传输、硬件/runtime 两段冷启动、工具安装锁和停止条件。当前只完成 Mac 免费实测、锁定源码静态核验和云端执行设计；获得账号/最终付费批准后才能执行真实 D0—D14 参考运行。
