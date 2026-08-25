# VLA-RelComp 前 14 天零基础实操教程

这是正式项目决策 D1 的教程与轻量验证版。它不重选方向、不声称完成 70 天研究，也不把计划输出写成实验结果。目标是让零科研基础学习者按 Day 0—14 建立可解释、可复现的 VLA-Arena 诊断开工能力。

## 使用顺序

1. 阅读 `00_课程使用说明与学习地图.md` 与 `assets/证据标签与目录约定.md`；
2. 从 `day00/README.md` 顺序做到 `day14/README.md`，不得跳过 Gate；
3. 每天先做开始前自检，再读指定范围、运行最小实验、改变一个变量、保存交付物、最后脱离 Agent 口述；
4. 答案位于每日末尾；先答后看；
5. `scripts/` 是教程代码，`work/VLA-Arena-upstream` 是制作者静态核验副本，正式项目期应建立独立 `upstream/VLA-Arena` 与项目 `src/`。

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

获得用户对云平台、预算与付费的明确批准后，另设“完整参考运行”目标，在正确 Linux/NVIDIA 环境按教程完整走一遍，记录真实时间、显存、下载量、输出和修订。之后才进入用户亲自学习运行。当前没有获得这类授权。
