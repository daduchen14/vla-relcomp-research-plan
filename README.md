# VLA-RelComp Research Plan

这是一个私人研究规划仓库，用于保存“从个人约束、目标院校研究生态和公开项目中，收敛出一个70天研究型复试项目”的完整过程。

## 当前结论

- 主方向：具身智能中的 VLA 组合泛化、grounding 与可靠性；
- 主项目：VLA-RelComp；
- 官方锚点：VLA-Arena 的 Preposition Combinations 套件；
- 备用路线：Fine-R1-3B 细粒度视觉证据充分性诊断；
- 当前状态：已完成决策、Day 0—14 教程、免费轻量验证和 H2.5.2 tag-only 可移植发布入口；尚未租用 GPU、下载模型或运行真实 VLA episode。

## 唯一首次执行入口

1. 从 [`VLA-RelComp_教程/h2_preflight/fresh_clone_quickstart.md`](./VLA-RelComp_教程/h2_preflight/fresh_clone_quickstart.md) 获取并核验受审发布 tag；
2. 进入 [`VLA-RelComp_教程/README.md`](./VLA-RelComp_教程/README.md) 按 Day 0—14 顺序学习；
3. Linux/NVIDIA 真实参考运行只按 [`VLA-RelComp_教程/h2_preflight/README.md`](./VLA-RelComp_教程/h2_preflight/README.md) 的 C0–C7 状态机执行。

[`25_正式项目决策D1_VLA-RelComp.md`](./25_正式项目决策D1_VLA-RelComp.md) 仍是研究方向和推翻条件的事实基线。[`26_教程任务交接说明.md`](./26_教程任务交接说明.md) 只保留为 H1 历史交接记录，不是当前执行入口。其他 00–24 号文件用于追溯决策与概要协议，无需在首次执行时按顺序重读。

## 历史调查

09—24 号文件保留方向筛选、候选项目、学习负担、新颖性、导师风险、零门槛样例和最终二选一过程；26 号文件保留教程生产任务的历史要求。它们均是证据记录；若与 D1 冲突，以 25 号正式决策为准；若与当前操作路径冲突，以 H2.5.2 fresh-clone 页和教程 README 为准。

## 使用纪律

- 仓库暂时保持 private；
- 不上传密码、token、云密钥、个人联系方式；
- 不上传模型权重、数据集、虚拟环境、缓存、原始大日志和视频；
- 未来每次正式改变方向或项目，都新增书面 Decision，不静默覆盖历史；
- 论文、仓库、模型和数据必须记录精确版本；
- Agent 可以帮助实现，但本人必须能解释核心代码、实验和失败边界。

## 正式开工

完整参考运行开始前，需要先确定开始日期、云端预算和 GPU 账户；按教程执行 D4、D8、D14 三道闸门，不重新打开大方向筛选。当前 Mac 验证日志只证明教程小工具与静态链路，不代表真实模型已经运行。
