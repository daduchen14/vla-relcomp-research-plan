# Day 3：Transformer、视觉编码与 VLA 数据流

## 当日目标，以及为什么服务于 VLA-RelComp

今天不推导整套 Transformer，而是建立能读 VLA 代码的最小模型：文字变 token，图像变视觉 token，embedding 表示各 token，attention 让信息交互，动作头/专家把共同表示映射成动作块。VLA-RelComp 的语言 oracle、视觉对象提示 oracle 和阶段诊断分别干预不同位置；没有这张数据流图，就无法解释干预针对什么瓶颈。

## 前置知识和开始前自检

完成 Day 2，能解释 `[B,H,A]`。开始前画一条猜测链：instruction、两张 RGB、robot state 如何进入模型，输出如何到环境。保留初稿，课末用真实函数名修正。

## 具体场景与最小例子

指令含两个关键实体 tomato/bowl 与关系 between。文本 tokenizer 把词/子词变 token id；视觉编码器把图像区域变视觉表示；模型需要把“tomato”与正确红色物体、把“bowl between vase and teapot”与正确参照物关联，再输出移动和夹爪动作。注意力权重可以展示关联线索，但注意力图本身不证明因果理解，所以本项目要看受控干预后的行为恢复。

## 零基础知识讲义

### token 与 embedding

Token 是序列的离散单位，可能是词、子词、特殊图像占位或动作表示。Token id 只是整数索引；embedding 把它映射到连续向量。位置编码让模型区分顺序。不要把一个 token 等同一个英文单词，也不要假设 `between` 永远是单 token。

### attention 的必要原理

对每个 token 构造 query、key、value。相关度由 query 与 key 的点积决定，经缩放和 softmax 得权重，再对 value 加权求和。形式是 `softmax(QKᵀ/√d_k)V`。直觉上，“tomato”位置可以按当前上下文收集图像/文字中与目标有关的信息。多头 attention 让不同投影关注不同关系；它仍只是计算机制，不自动等同可解释因果。

### 自回归与并行动作

自回归模型按已有 token 预测下一个 token；OpenVLA 把连续动作离散化成 token，再逐个解码。其他 VLA 可用回归或 flow matching 并行生成动作块。两者最终都要转回环境可执行连续动作。模型架构不同可能带来不同速度与错误，但本项目不能把架构印象当归因，必须用相同任务与阶段证据比较。

### 视觉编码

Vision Transformer 常把图像切成 patch，把每个 patch 投影成视觉 token，加位置表示后送入 Transformer。VLA 实际实现可能用现成 VLM 的视觉塔和投影层；你只需追踪“原始 RGB → resize/normalize → visual features/tokens”，不需要第 3 天复现预训练。

### 多模态融合

文字与视觉可以拼成序列做 self-attention，也可以让一个流通过 cross-attention 读取另一个流。SmolVLA 锁定实现由 SmolVLM 与 action expert 组成；`smolvlm_with_expert.py` 同时有 attention/cross-attention 相关前向，`modeling_smolvla.py` 负责策略输入、flow matching 与动作输出。当前目标是认接口，不背全部层数。

### robot state 与动作专家

仅看图像和文字不一定知道机械臂当前位姿与夹爪状态，所以策略还接收 robot state observation。动作专家/动作头把融合后的条件表示转成动作轨迹。SmolVLA 会把动作 pad 到 `max_action_dim`，预测 chunk，再裁回数据定义的真实动作维。

### 三种“表示”不要混淆

1. 文本/视觉 embedding：模型内部连续向量；
2. simulator state：环境物理真值；
3. 项目 stage event：从 state 按操作性定义计算的离散标签。

看到 embedding 聚类或 attention 热图，只能说内部表示出现某种相关结构；要定位行为瓶颈，仍需匹配反事实和 oracle 恢复。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 看完会什么 | 暂时跳过 |
|---|---|---|---:|---|---|
| Attention Is All You Need | 建立 token/attention 最小原理 | PDF pp.1–5，图1，§3.2 | 45–60 分钟 | 解释 Q/K/V 与权重和 | 训练成本、翻译结果全表 |
| Vision Transformer | 理解图像 token | PDF pp.1–4，图1、§3.1 | 30–45 分钟 | 画出 patch→token | 大规模预训练消融 |
| VLA-Arena 论文 | 连接模型族与 benchmark | PDF pp.6–7 的 §4.1；PDF p.39 §H.1 | 35–50 分钟 | 区分自回归、flow matching、回归路线 | 所有模型超参 |
| SmolVLA 官方文档 | 看实际轻量 VLA 架构 | Overview、Architecture、Training 开头 | 40–60 分钟 | 描述 VLM+action expert | 真机设置 |
| 锁定策略源码 | 用函数名修正数据流 | `configuration_smolvla.py`；`modeling_smolvla.py` 的 `predict_action_chunk`、`select_action`、`forward`；`smolvlm_with_expert.py` 的 `forward` | 60–90 分钟 | 从输入追到 action chunk | 优化器和分布式细节 |

固定链接见 `../assets/official_source_index.md`。

## 操作步骤、状态与预期输出

### 1. 手算一个 attention（`实测` / `待用户执行`）

```bash
python3 - <<'PY'
import math
q = [1.0, 0.0]
keys = [[1.0, 0.0], [0.0, 1.0]]
scores = [sum(a*b for a,b in zip(q,k))/math.sqrt(2) for k in keys]
exps = [math.exp(s) for s in scores]
weights = [e/sum(exps) for e in exps]
print('scores=', [round(x,3) for x in scores])
print('weights=', [round(x,3) for x in weights], 'sum=', round(sum(weights),3))
PY
```

预期第一项权重大于第二项，二者和为 1。score 表示未归一化相关度，softmax 权重表示相对分配。这个二维例子只展示公式，不是模型 attention 实测。

变量实验：把 q 改为 `[0,1]`，两项权重应翻转；把 q 改为 `[1,1]`，权重接近相等。写出哪个变量改变、观察到什么、和目标/参照选择有何类比。

### 2. 追踪真实数据流（`静态核验`）

在本地锁定源码依次搜索：

```bash
rg -n "def run_episode|select_action|predict_action_chunk|def forward" \
  work/VLA-Arena-upstream/vla_arena/models/smolvla/evaluator.py \
  work/VLA-Arena-upstream/vla_arena/models/smolvla/src/lerobot/policies/smolvla
```

若从工作目录执行，预期命中 evaluator 的 episode 函数与 policy 的三个关键函数。把自己的初稿图改成：环境 obs/指令 → evaluator 构造 batch → `select_action` → 队列缺动作时 `predict_action_chunk` → action → `env.step` → 新 obs。不要把所有 `forward` 都画成一条直线；区分训练 forward 与推理入口。

### 3. 模型推理（`估计—未运行`）

正式 Linux/NVIDIA 环境加载 checkpoint 后，预期会初始化 policy、移动到 CUDA、设 eval，episode 内多次输出 action。当前未下载权重、未运行仿真，所以不填写 token 数、推理时延、显存或真实 chunk 值；这些由 D3 参考运行日志记录。

### 4. 用户复写（`待用户执行`）

关掉教程，用不超过 12 个框画数据流；必须含两个 camera observation、robot state、instruction、视觉编码、文本 token、融合/attention、动作头/专家、action chunk、environment、privileged state logger。再打开教程订正。

## 预期输出每部分意味着什么

- attention 权重随 q 改变：证明小公式实现正确，不证明 VLA grounding。
- `rg` 命中函数：证明锁定路径存在，不证明依赖可安装。
- 数据流图把 privileged logger 画在策略旁路：表示 state 可做诊断、不能偷偷进入最终策略。
- 模型能输出动作：未来仍需 goal success 和阶段事件，不能把“无异常”当任务成功。

## 在 VLA-Arena / VLA-RelComp 真实代码和数据中的位置

- 文本/视觉模型与专家：SmolVLA 的 `smolvlm_with_expert.py`。
- 策略输入、padding、chunk 和队列：`modeling_smolvla.py`。
- 环境图像/指令到策略：`models/smolvla/evaluator.py:run_episode`。
- OpenVLA 对照：`models/openvla/evaluator.py` 与其 prismatic 模型代码；不要求今天逐层读。
- 语言 oracle 未来改变 instruction 表达；视觉 oracle 改可撤销视觉提示；stage probe 只读 simulator state。这三条必须在图上分开。

## 常见错误、诊断顺序、备用路线与止损

1. 把 token 当单词：查看 tokenizer 输出只是可变子词单位；止损 20 分钟。
2. 背公式却画不出闭环：回到 Day 1 episode；止损 30 分钟。
3. 把 attention 热图当理解证据：写出至少两种替代解释；止损 20 分钟。
4. 在数千行源码迷路：只追 `run_episode→select_action→predict_action_chunk`；90 分钟到点停止。
5. 想从零实现 Transformer：降为选做；第 14 天前不需要。
6. 官方文档与 vendored LeRobot main 不同：以锁定仓库内 vendored 代码解释当前 evaluator，同时记录外部文档日期。

## 时间预算、最低完成线、标准完成线与选做

正常 7–8.5 小时：概念/论文 150–180 分钟，手算与变量实验 60 分钟，源码追踪 120–150 分钟，画图 60–75 分钟，记录/口述 60 分钟，排错上限 45 分钟。

- 最低完成线：解释 token/embedding/attention/视觉 patch；完成手算；画闭环。
- 标准完成线：用真实函数名追到 action chunk；分清训练 forward 与推理入口；标出三类干预位置。
- 提前完成选做：比较 OpenVLA 离散动作 token 与 SmolVLA 连续动作块的输出接口，只写一页，不评判谁一定更强。

## 当日交付物

- attention 三组输出与解释；
- 一张带真实函数名的数据流图；
- “attention 能说明/不能说明”各两条；
- 2 分钟口述：“图像、文字、robot state 如何变成 action chunk”。

## 自测题、参考答案与复试口述

1. token id 和 embedding 有什么区别？
2. attention 权重为何不是因果证明？
3. 视觉 patch 的作用是什么？
4. 自回归动作与动作块有什么不同？
5. language oracle、visual oracle、stage probe 分别在哪条链？

参考答案：1. 前者是离散索引，后者是连续向量。2. 权重是模型计算中的相关结构，可能受多个变量影响；需受控干预和行为恢复。3. 把二维图像变成可由 Transformer 处理的序列表示。4. 前者顺序预测离散动作 token；后者可并行/整体生成多个连续未来动作。5. 分别改语言输入、可见图像提示、策略旁路的特权状态日志。

复试口述问题：为什么 VLA-Arena 已有 attention 分析后，本项目还需要 oracle？答题要点：attention 只能提供相关线索，且原论文已有此证据；匹配反事实与可撤销干预测量行为恢复，能更接近定位限制环节，但仍只做有限因果推断。
