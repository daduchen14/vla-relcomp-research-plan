# 官方资料与代码证据索引

> 核验日期：2026-08-25。网页可能变化；代码链接固定到提交 `babe582ebffc82b979b77964a7e56417d02f63a4`。论文统一使用 arXiv v4（2026-08-07 修订）。PDF 页码指 PDF 查看器页码。

## 项目与论文

| 主题 | 精确入口 | 必读范围 | 为什么看 | 建议时间 | 看完能做什么 | 暂时跳过 |
|---|---|---|---|---:|---|---|
| 框架全貌 | https://github.com/PKU-Alignment/VLA-Arena/tree/babe582ebffc82b979b77964a7e56417d02f63a4 | README: Quick Start、Task Suites、Installation | 识别官方命令与资源边界 | 20 分钟 | 说出 11 suites/170 tasks 与 uv 工作流 | leaderboard 投稿、全套件图片 |
| 研究问题 | https://arxiv.org/pdf/2512.22539v4 | PDF pp.1–3，图1与 §1 | 看到原论文已解决什么 | 30 分钟 | 区分 benchmark 贡献与本项目增量 | 相关工作细节 |
| CBDDL 与分级 | 同上 | PDF pp.3–6，§2、§3、§4.1 | 理解任务结构、诊断扰动与 L0/L1/L2 | 45 分钟 | 解释三种难度与训练只用 L0 | 其他十个 suite 细节 |
| 目标套件 | 同上 | PDF p.6 的定义；PDF p.36 §G.8 与表22 | 精确查看 15 个任务 | 30 分钟 | 对照代码清单核验每级 5 项 | G.1–G.7、G.9–G.11 |
| 原论文结果与边界 | 同上 | PDF pp.7–10，§4.2–§4.4；PDF pp.14–18 附录结果/失败分析 | 避免把已知的平均掉点或 attention 图当创新 | 60 分钟 | 说出本项目为何必须做行为级诊断 | 全表逐项背数值 |
| 实现细节 | 同上 | PDF pp.39–45，§H 与 §I | 对照模型、训练、评测和数据清洗口径 | 60 分钟 | 知道哪些数字是论文条件而非本机承诺 | 与当前任务无关模型超参 |

## 目标代码路径

统一前缀：`https://github.com/PKU-Alignment/VLA-Arena/blob/babe582ebffc82b979b77964a7e56417d02f63a4/`

| 要回答的问题 | 仓库路径 / 符号 | 已核事实 |
|---|---|---|
| suite 真正叫什么 | `vla_arena/vla_arena/benchmark/__init__.py`：`vla_arena_suites`、`suite_to_problem_folder` | 注册名是 `extrapolation_preposition_combinations` |
| 15 项任务是什么 | `vla_arena/vla_arena/benchmark/vla_arena_suite_task_map.py`：同名键 | 0/1/2 每级各 5 项 |
| 任务真值在哪里 | `vla_arena/vla_arena/bddl_files/extrapolation_preposition_combinations/level_{0,1,2}/*.bddl` | 每项含 `:language`、`:obj_of_interest`、`:init`、`:goal` |
| 初始状态在哪里 | `vla_arena/vla_arena/init_files/extrapolation_preposition_combinations/level_{0,1,2}/*.pruned_init` | 每个 BDDL 有同名 init 文件 |
| success 谁判定 | `vla_arena/vla_arena/envs/bddl_base_domain.py`：`_check_success`、`step` | goal predicates 合取；`info['success']`；success 或 timeout 导致 done |
| SmolVLA episode 循环 | `vla_arena/models/smolvla/evaluator.py`：`Args`、`run_episode`、`run_task`、`main` | 加载 observation、生成 action、step、保存视频与日志 |
| OpenVLA episode 循环 | `vla_arena/models/openvla/evaluator.py`：`GenerateConfig`、`run_episode`、`run_task`、`main` | 同一闭环但模型预处理/动作解码不同 |
| 初始状态如何选 | `vla_arena/vla_arena/utils/eval_init_state.py`：`select_init_state_index` | `first` 与 `episode_idx` 及 offset 明确实现 |
| 配置字段 | `vla_arena/configs/evaluation/smolvla.yaml`、`openvla.yaml`、`random.yaml` | suite、level、trials、seed、init、日志、视频字段存在 |
| 7 维动作如何处理 | 两个 evaluator 的动作处理函数与 dummy action | 6 个末端位姿/增量维度加 1 个夹爪维度；具体语义以 evaluator 为准 |

## 模型与数据卡

| 资产 | 官方入口 | 当前阶段动作 |
|---|---|---|
| SmolVLA checkpoint | https://huggingface.co/VLA-Arena/smolvla-vla-arena | 只读模型卡和文件树；不下载权重 |
| OpenVLA checkpoint | https://huggingface.co/VLA-Arena/openvla-7b-finetuned-vla-arena | 只读模型卡和文件树；D7 获批 GPU 后再下载 |
| SmolVLA L0 数据 | https://huggingface.co/datasets/VLA-Arena/VLA_Arena_L0_L_lerobot_smolvla/tree/main | 只读数据卡/文件树；本阶段不下载约 32.5 GB 版本 |
| SmolVLA 原理/训练 | https://github.com/huggingface/lerobot/blob/main/docs/source/smolvla.mdx | 只读 Overview、Architecture、Training；跳过真机设备章节 |

## 基础教材（官方或经典原文）

| 知识点 | 精确范围 | 用法 |
|---|---|---|
| PyTorch tensor/device/inference | https://docs.pytorch.org/tutorials/beginner/basics/tensorqs_tutorial.html 的 Attributes 与 Operations；https://docs.pytorch.org/docs/2.9/generated/torch.autograd.grad_mode.inference_mode.html 的开头说明 | Day 2 只学当前推理链需要的张量形状、设备和关闭梯度 |
| Transformer | https://arxiv.org/pdf/1706.03762 PDF pp.1–5，图1、§3.2 | Day 3 只理解 token、embedding、attention 与序列映射 |
| Vision Transformer | https://arxiv.org/pdf/2010.11929 PDF pp.1–4，图1、§3.1 | Day 3 理解图像如何切 patch 成 token |
| 行为克隆/模仿学习 | https://huggingface.co/docs/lerobot/il_robots 的 Introduction 与 imitation learning 数据流 | Day 4 理解训练样本是 observation→action，不展开 RL |
| 二项置信区间 | https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm | Day 6 对成功率报告区间，不把 2/5 当稳定结论 |

## 版本差异提示

- 锁定提交的 README 同时写明 macOS 12+ 可安装、GPU 加速需 CUDA 11.8+；这不等于 Mac 能完成正式 VLA 参考运行。教程把本地脚本/静态核验与 Linux/NVIDIA episode 严格分开。
- README 展示短名 `preposition_combinations`，代码注册表与目录使用带前缀的 `extrapolation_preposition_combinations`；执行配置使用后者。
- 默认 YAML 是上游示例，目标 suite 需复制到项目 `configs/` 后改，不直接编辑 upstream。
