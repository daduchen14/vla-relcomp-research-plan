# Day 1：从两张图像到 success——第一次看懂 VLA 闭环

## 当日目标，以及为什么服务于 VLA-RelComp

今天建立最重要的共同语言：VLM、VLA、observation、state、action、episode、step、reward、done 与 success。你不背定义，而是追踪一个“把番茄放到碗上”的闭环，亲手查看样例字段，再到官方 evaluator 与 BDDL 找到对应位置。VLA-RelComp 要把总体失败拆成阶段事件；如果混淆 observation 与 simulator state，oracle 和诊断就会发生数据泄漏。

## 前置知识和开始前自检

需要完成 Day 0，并能定位教程根目录。开始前不看下文回答：一张相机图像是不是环境全部 state？一次 action 是否等于一个 episode？`done=True` 是否总等于成功？把答案保存，课末再修正。

## 具体场景与最小例子

指令是“Pick the tomato in the top drawer and place it on the bowl between the vase and the teapot”。机器人每一步收到相机图像、机器人自身数值状态与同一条语言指令，输出一个连续动作；环境执行后产生新 observation。循环直到目标谓词成立或超时。

假设最后视频只显示番茄被抓起但掉在碗旁：`target_lifted=1`，`relation_satisfied=0`，`success=0`。这比只写“失败”多告诉我们控制链在哪一段断裂，但仍不能证明模型内部“理解了番茄”。

## 零基础知识讲义

### VLM 与 VLA

VLM（视觉语言模型）通常把图像和文字变成回答、描述或共同表示；它可以告诉你“红色物体在碗旁”。VLA（视觉—语言—动作模型）还必须把感知与指令变成环境可执行的动作，并在新 observation 到来后继续闭环。类比：VLM 像看导航图后说“向左”；VLA 像每隔一小段根据新路况实际打方向盘。

### observation 与 state

Observation 是策略在推理时获准看到的输入，例如 agent-view RGB、wrist RGB、末端执行器/夹爪状态和指令。State 是环境内部用于推进物理和判定任务的更完整变量，例如每个物体的精确位姿、接触关系和 goal predicate。state 可生成 observation，但 observation 通常不能唯一还原全部 state。

本项目可用 state 做离线诊断标签（例如是否抬升），但如果把测试时的目标真值坐标输入最终修复，就把答案泄露给模型。视觉 oracle 可暂时用特权 state 来定位瓶颈，但必须和最终方法分栏。

### action、step 与 action chunk

Action 是一次环境控制输入。VLA-Arena 的目标 evaluator 最终把动作传给 `env.step(action.tolist())`。当前机械臂路径常见 7 维：前三维平移、接着三维旋转、最后一维夹爪；精确符号、归一化和坐标系必须以具体 evaluator 为准，不能只凭“7维”猜。

一个 step 是 observation → policy → action → environment transition 的一次循环。某些策略一次模型调用预测多个未来 action，称 action chunk；环境仍逐步执行。今天只建立概念，Day 2 亲手改 chunk。

### episode、done、reward 与 success

Episode 是从 reset/设定 init state 开始，到成功或超时/异常结束的一整条轨迹。`done` 是“本 episode 结束”，success 是“目标谓词满足”。在锁定代码 `bddl_base_domain.py:step` 中，`done = success or timeout_done`，所以 done 可能只是超时。reward 是训练/评估可能使用的数值信号，不应自动当 success。VLA-Arena 的 success 来自 BDDL `:goal` 谓词经过 `_check_success` 求合取。

### 四段行为链

本项目记录：目标接触 → 目标抬升 → 靠近参照区域 → 终态关系满足。后一步通常依赖前一步，但传感器噪声和操作性阈值可能产生不一致，所以事件定义、阈值和人工抽查必须固定。语言解析和视觉 grounding 仍是潜变量；不能从“接触正确番茄”直接宣称模型有抽象概念。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 看完会什么 | 暂时跳过 |
|---|---|---|---:|---|---|
| VLA-Arena 论文 v4 | 看到正式闭环问题与 benchmark 边界 | PDF pp.1–3 图1、§1 | 30–45 分钟 | 解释框架从任务到评测的链 | 相关工作表格 |
| 目标 BDDL 示例 | 看到 state/goal 的真实表示 | 锁定仓库 `.../level_0/pick_the_tomato_in_the_top_layer...between...bddl` 的 `:language`、`:obj_of_interest`、`:init`、`:goal` | 30 分钟 | 指出指令与 goal 不是同一字段 | regions 数值细节 |
| success 实现 | 避免把 done 当 success | `bddl_base_domain.py` 的 `_check_success`、`step` | 25–40 分钟 | 用源码解释 success/timeout | safety cost |
| SmolVLA evaluator | 看真实 episode 循环 | `models/smolvla/evaluator.py` 的 `run_episode` | 35–50 分钟 | 找到 reset、observation、action、env.step、done | 模型内部架构 |

精确固定链接见 `../assets/official_source_index.md`。

## 操作步骤、状态与预期输出

从教程根目录执行：

```bash
cd "$(git rev-parse --show-toplevel)/VLA-RelComp_教程"
python3 scripts/action_chunk_demo.py
```

这是制作者 `实测`、学习者 `待用户执行` 的纯 Python 样例。预期先打印 `observation`：两个图像占位符是可见输入，`robot_state` 是策略可见的机器人自身量，`instruction` 是语言，`target_xyz` 特意作为教学规则需要的字段。随后 `action_chunk_shape` 为 `[4, 7]`，表示 4 个动作、每个 7 维。最后一行明确写 synthetic，禁止把它当 VLA 结果。

变量实验：把脚本中 `chunk_size=4` 临时改成 2，重新运行。你应观察 shape 变 `[2,7]`，单步位移约变大一倍，而总计划位移近似不变。完成后撤销改动或只把差异写入个人作业；教程源文件保持原样。

然后查看真实样例 episode（脚本为 `实测`，字段来源为 `静态核验`）：

```bash
python3 - <<'PY'
import csv
from pathlib import Path
p = Path('assets/sample_episode_registry.csv')
rows = list(csv.DictReader(p.open(encoding='utf-8')))
for key in ['episode_id','level','intervention','target_lifted','relation_satisfied','success']:
    print(key, '=>', rows[1][key])
PY
```

预期第二条样例为 L1、无干预，抬升成功但关系/任务失败。每项都是 `fixture_` 数据；这证明脚本和字段教学可运行，不证明真实模型有相同行为。

官方 GPU episode 命令与输出目前为 `估计—未运行`：预计日志包含 task description、trial/init index、episode steps、success、结果 JSON 与可选视频。具体字段由正式环境实测后回填。

## 在 VLA-Arena / VLA-RelComp 真实代码和数据中的位置

- Observation 准备：SmolVLA `evaluator.py` 的 episode 循环与 observation 字典构造；OpenVLA `prepare_observation`。
- Action 产生：SmolVLA policy `select_action`；OpenVLA evaluator 调 `get_action` 后 `process_action`。
- Transition：两个 evaluator 均调用 `env.step(...)`。
- State 与 success：`envs/bddl_base_domain.py` 的 parsed problem、`_check_success`、`step`。
- 任务语义：目标 suite 的 15 个 `.bddl` 中 `:language`/`:obj_of_interest`/`:init`/`:goal`。
- 本项目记录：`assets/episode_registry_schema.csv` 是字段空表；`sample_episode_registry.csv` 是假想示例。

## 常见错误、诊断顺序、备用路线与止损

1. 把图片叫 state：先问“策略能直接看到全部物体精确坐标吗”；止损 15 分钟。
2. 把机器人自身 state 和 simulator full state 混为一谈：在记录中写 `robot_state_observation` 与 `simulator_privileged_state`；止损 20 分钟。
3. 把 `done=True` 当 success：检查 `info['success']` 与 timeout；止损 15 分钟。
4. 把 reward 当 success：回到 goal predicate；止损 15 分钟。
5. 样例脚本报路径错：`pwd`、`ls scripts`、再运行；止损 15 分钟。
6. 想马上学完整控制理论：记入 parking lot；当前只需理解动作是闭环接口。

若当前 Python 无法运行纯标准库脚本，保存完整 traceback，换 `python3` 绝对路径；30 分钟仍失败时继续静态练习并标记待修，不触发项目暂停。

## 时间预算、最低完成线、标准完成线与选做

正常耗时 6.5–8 小时：概念 120 分钟，源码跟读 120–150 分钟，脚本 60–90 分钟，字段作业 60 分钟，记录与口述 60–75 分钟，排错最多 45 分钟。

- 最低完成线：不用术语堆砌，说清 observation/state、step/episode、done/success 三组差异；成功运行两个样例。
- 标准完成线：在锁定源码准确指出输入、动作、环境 step 与 success 判定；完成一条 episode 字段解释。
- 提前完成选做：画出 observation→policy→action→environment→new observation 的闭环，并在旁边标出 privileged state 只进入诊断日志。

## 当日交付物

- `day01_field_walkthrough.md`：六个字段的值、来源、意义、不能推出什么；
- action chunk 改变量前后输出截图或文本；
- 一张闭环图；
- 90 秒脱离 Agent 口述：“一次 episode 如何开始和结束”。

## 自测题、参考答案与复试口述

1. VLM 与 VLA 最小区别是什么？
2. observation 为什么通常小于完整 state？
3. `done=True, success=False` 如何出现？
4. `target_lifted=True` 能否证明模型理解关系？
5. state 什么时候可以用，什么时候会泄漏？

参考答案：1. VLA 还要输出并闭环执行动作。2. 策略只得到允许的传感/本体输入，环境还持有完整物理真值。3. 超时或其他终止。4. 不能，只能说明行为达到抬升操作性条件。5. 可作离线分段标签或明确 oracle；最终修复推理不能使用 L1/L2 测试真值。

复试口述问题：如果视频看见抓错番茄，但 goal 最后偶然满足，你怎样记录？答题要点：分别记录目标选择/接触、抬升、参照接近和 goal；说明自动 success 与人工阶段核验的差异，保留异常案例，不用一个标签覆盖整条链。
