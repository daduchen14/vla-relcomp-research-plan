# Day 4：行为克隆、复现性、成功判定与 Gate 1

## 当日目标，以及为什么服务于 VLA-RelComp

理解行为克隆/SFT 的训练样本，区分“程序运行、模型出动作、episode 成功”，并把单 episode 复现要求写成 Gate 1 检查表。它服务于本项目的地基：只有相同配置可重复，后续反事实差异才可能归因于受控变量。

## 前置知识和开始前自检

完成 Day 0–3；能画 VLA 闭环并解释 success。自检：一条示范轨迹如何变成多条 observation→action 训练样本？重复三次应固定哪些量？

## 具体场景与最小例子

示范者在 step 0 看见图像/状态/指令并做 action 0，step 1 收到新 observation 再做 action 1。行为克隆让模型最大化示范动作在对应输入下的概率或最小化动作预测损失。训练 loss 下降不等于闭环任务成功：微小动作误差会改变后续 observation 并累积。

## 零基础知识讲义

行为克隆属于监督式模仿学习：数据是 observation、instruction、action 序列；标签是示范 action，不是“模型自己探索得到奖励”。SFT 在这里指用有监督数据微调已有模型。它会遇到 distribution shift：训练只看专家访问的状态，推理错误后进入陌生状态。闭环 success 因而必须由环境 goal 判断。

复现不是要求随机系统每次像素完全相同，而是明确版本、seed、init state 与允许差异。seed 控制部分伪随机源；初始状态索引直接控制场景起点；两者不能互相替代。异常、timeout 和模型失败必须分栏。

Gate 1 要求正确 Ubuntu/NVIDIA 环境中官方 checkpoint 可重复启动，日志对应任务/level/seed/init/action steps/终态并保存视频；用户能解释完整数据流。当前教程阶段只准备和静态核验，不能提前打勾。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 看完会什么 | 暂时跳过 |
|---|---|---|---:|---|---|
| LeRobot 模仿学习文档 | 看训练样本闭环 | Introduction 与 imitation-learning 数据流 | 35–50 分钟 | 区分示范 action 与 reward | 真机采集 |
| VLA-Arena 论文 | 核对训练/评测口径 | PDF pp.39–45，重点 H.3/H.4/I | 50–70 分钟 | 说明论文条件不是本机承诺 | 全模型超参 |
| 两个 evaluator | 找成功、timeout、异常 | `run_episode`、`run_task` | 60 分钟 | 画三类失败分支 | 内部模型层 |

## 操作步骤、状态与预期输出

1. `静态核验`：在锁定代码找到 `policy.eval()`、episode loop、`is_success_done`、视频保存函数，写成四列“输入/处理/输出/异常”。预期每列有真实函数名。
2. `实测`：运行 `python3 scripts/analyze_registry.py assets/sample_episode_registry.csv`。预期 `validated_rows=5`，按 level 输出原始计数与 Wilson 区间，末行声明 fixture。
3. `待用户执行`：把样例 CSV 复制到个人作业，故意把成功行的 `relation_satisfied` 改 0，验证器应拒绝。解释这是 schema 一致性检查，不是物理正确性证明。
4. `估计—未运行`：正式 GPU 日重复同一配置 3 次，保存 config、日志、视频、结果和 init 索引；当前不填写时延/显存/成功率。

正常输出含原始计数而非只有百分比；验证失败应指出 episode id。若脚本运行成功，只能说明本地分析链可用。

## 在真实代码中的位置

- 训练：各模型 `trainer.py` 与 LeRobot policy `forward`；
- 推理：SmolVLA/OpenVLA `evaluator.py:run_episode`；
- goal：`bddl_base_domain.py:_check_success`；
- 复现：`eval_init_state.py:select_init_state_index` 与配置 seed/init 字段；
- Gate 证据未来存 `notes/gates/gate1.md`，不改官方 YAML。

## 常见错误、诊断顺序、备用路线与止损

先判环境是否启动，再判模型加载，再判动作是否 finite，再判 episode 是否 timeout，最后判 goal。安装异常不得记模型失败。单项排错 45 分钟，Gate 1 总失败只再给一个工作日；之后查官方 issue/提交差异，不直接训练。视频可播放但无日志不算通过；loss 低但 success 低不矛盾。

## 时间预算、最低完成线、标准完成线与选做

正常 6–8 小时。最低完成线：解释 BC 与闭环误差、运行验证器、列 Gate 1 字段。标准完成线：独立区分环境/模型/评测失败并完成 Gate 草稿。选做：用三步二维轨迹演示单步误差如何改变后续输入。

## 当日交付物

Gate 1 草表、验证器正反例日志、单 episode 证据清单、2 分钟口述。所有真实 GPU 项标 `待用户执行`。

## 自测题、参考答案与复试口述

问题：BC 的标签是什么？loss 低为何不等于 success 高？seed 与 init index 差别？程序无异常算成功吗？Gate 1 当前能否通过？

参考答案：标签是示范 action；闭环会累积误差且 goal 更严格；seed 控制随机流而 init index指定起点；无异常只说明工程链运行；当前未在批准 Linux/NVIDIA 运行，不能通过。复试口述：说明“模型运行成功不等于任务成功”，必须提 goal predicate、timeout 和阶段证据。
