# Day 2：张量、device、推理模式、7维动作与 action chunk

## 当日目标，以及为什么服务于 VLA-RelComp

今天把“图像和数字送进模型”变成可检查的 shape、dtype 与 device；理解推理为什么不需要梯度；拆开 7 维动作和动作块。VLA-RelComp 后续要记录动作、比较阶段失败并插入只读探针，若看不懂维度，最容易把 batch、时间或动作维错位而产生无声错误。

## 前置知识和开始前自检

完成 Day 1。开始前写出：一张 256×256 RGB 图像大约有哪些轴？`[4,7]` 的 action chunk 中 4 和 7 各代表什么？如果不知道可以继续，但不能跳过变量实验。

## 具体场景与最小例子

先拆一帧真实数据结构。下面的字段名和 shape 来自 Every-Embodied 的 LeRobot/MuJoCo 示教数据结构；它只用于帮助你看懂“一帧 episode 记录里有什么”，不是 VLA-Arena 数据，也不要求安装或运行该项目。示例值省略，避免把未运行数据写成实验结果。

| LeRobot/MuJoCo 类比字段 | 单帧 shape / 含义 | 映射回锁定 VLA-Arena SmolVLA evaluator | 不能混淆的地方 |
|---|---|---|---|
| `observation.image` | `(256,256,3)`，外部相机 RGB | 原始 `obs['agentview_image']` 经翻转、归一化和转轴后成为 `observation.images.image`，模型输入为 `[1,3,H,W]` | 字段名、分辨率和预处理以 VLA-Arena 锁定代码为准 |
| `observation.wrist_image` | `(256,256,3)`，腕部相机 RGB | 原始 `obs['robot0_eye_in_hand_image']` 处理后成为 `observation.images.wrist_image` | 不能把两路相机交换，也不能假设所有模型使用相同键名 |
| `observation.state` | `(6,)`，该示例写末端位姿 | VLA-Arena 把 `robot0_eef_pos`、四元数转轴角、`robot0_gripper_qpos` 拼成 state；实际长度由代码决定 | 两边 state 维数和语义并不相同，不能直接复用 checkpoint 或数据 |
| `action` | `(7,)`，该示例写 6 个关节量加夹爪 | VLA-Arena 环境也接收 7 维动作，但 evaluator 的坐标约定、归一化和夹爪后处理才是事实依据 | “都是 7 维”不代表控制语义相同 |
| `obj_init` | `(6,)`，示例环境的物体初始信息，训练不用 | VLA-Arena 初始状态由冻结 `.pruned_init` 和 init selector 管理，不是模型 observation 字段 | 特权初始真值不能因为便于诊断而送给策略 |

把这一帧加入 batch 后，单个 7 维 action 是 `[1,7]`；连续四帧动作组成教学 chunk 才是 `[1,4,7]`。这张表替代纯抽象背轴：先问“字段代表什么”，再检查 shape，最后回到锁定 evaluator 确认真实键名与预处理。

## 零基础知识讲义

### 为什么现在需要张量

张量是带规则形状和数值类型的多维数组。标量是 0 维，动作向量是 1 维，图像是 3 维，batch 图像是 4 维。shape 只给轴长度，不自动给轴名字；研究记录要写 `[batch, time, action_dim]`，不能只写 `[1,50,7]`。

### dtype 与归一化

图像可能以 `uint8` 表示 0–255，也可能转为 `float32` 并归一化。动作通常是浮点数。错误 dtype 可导致溢出、精度或模型输入错误。动作最后一维的开/合符号尤其不能凭经验猜：OpenVLA evaluator 中先归一化并可能反转夹爪符号，真实含义以 `process_action` 为准。

### CPU、GPU 与 device

CPU 适合通用控制，GPU 擅长大规模并行矩阵运算。张量和模型必须处于兼容 device；“模型在 CUDA、输入在 CPU”会直接报错。显存是 GPU 的内存，不等于系统内存。当前 Mac 的轻量脚本使用 CPU；正式模型路径是 Linux/NVIDIA CUDA。不要把 Apple MPS 小样例性能外推到 A100。

### 梯度与 inference mode

训练时自动微分保存中间量以计算参数梯度；推理只需预测动作。`torch.inference_mode()` 关闭与推理无关的 autograd 跟踪，通常减少开销，但不等于自动调用 `model.eval()`；后者切换 dropout、batch norm 等模块行为。官方 SmolVLA 初始化明确 `policy.eval()`，设备由配置决定。

### 7维动作

本任务环境接收的常见控制向量可以理解为 `Δx, Δy, Δz, Δroll, Δpitch, Δyaw, gripper`。这是教学语义，不是对所有模型的通用保证；不同模型可能先离散化、归一化或使用不同坐标约定。锁定代码的 dummy action 为六个 0 加一个 `-1.0`，OpenVLA 的 `process_action` 处理夹爪。

### action chunk

动作块是一次模型预测未来 H 个动作，形状通常 `[batch,H,action_dim]`。优势是减少频繁推理并提供短期一致性；风险是环境变化后旧动作可能不再合适。SmolVLA 锁定配置默认 `chunk_size=50`、`n_action_steps=50`；`predict_action_chunk` 产生块，`select_action` 用队列逐个取出。教程的 `[4,7]` 是小型类比，不是官方 checkpoint 的实测配置。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 看完会什么 | 暂时跳过 |
|---|---|---|---:|---|---|
| PyTorch Tensor 教程 | 认识 shape/dtype/device | Tensor Attributes、Operations | 35–50 分钟 | 打印并解释三个属性 | 数据集与 autograd 全章 |
| `torch.inference_mode` 官方页 | 区分推理与 eval | 开头说明与示例 | 15–20 分钟 | 解释两者不等价 | thread-local 细节 |
| SmolVLA 配置 | 找真实 chunk 参数 | `configuration_smolvla.py` 的 `chunk_size`、`n_action_steps`、校验 | 20–30 分钟 | 解释两个参数关系 | 所有优化器参数 |
| SmolVLA policy | 看块如何进入队列 | `modeling_smolvla.py` 的 `predict_action_chunk`、`select_action` | 30–45 分钟 | 说出 `[B,H,A]` 到逐步 action | flow matching 数学推导 |
| OpenVLA evaluator | 确认动作后处理 | `process_action` 与 episode 中 `env.step` | 20–30 分钟 | 说明夹爪符号不可猜 | OpenVLA 训练代码 |

精确入口见 `../assets/official_source_index.md`。

## 操作步骤、状态与预期输出

### 1. 纯 Python action chunk（`实测` / `待用户执行`）

```bash
cd "$(git rev-parse --show-toplevel)/VLA-RelComp_教程"
python3 scripts/action_chunk_demo.py > validation/day02_action_chunk_user.txt
```

预期 `action_chunk_shape` 是 `[4,7]`；四行每行七个有限浮点数；最后明确 synthetic。前三个数是教学规则计算的位移，后三个旋转增量为零，末维为夹爪占位。它验证 shape 教学和脚本，不验证官方策略。

### 2. 改一个变量（`待用户执行`）

制作个人副本，把 `target_xyz` 的 x 从 `0.18` 改成 `0.26`。预测再运行：x 方向每步增量应增大，shape 不变。若 shape 变化，说明你改错了结构而非数值。

### 3. 可选 PyTorch 最小实验（当前制作者环境为 `估计—未运行`）

只有在隔离 Python 3.11 环境已安装 PyTorch 时执行：

```python
import torch
x = torch.zeros((1, 2, 3, 256, 256), dtype=torch.float32)
print(x.shape, x.dtype, x.device)
with torch.inference_mode():
    y = x.mean(dim=(-2, -1))
print(y.shape)
```

正常形态：输入 `[1,2,3,256,256]` 表示 batch、camera、channel、height、width；输出 `[1,2,3]`。当前系统未为教程安装 torch，所以不能标 `实测`。

### 4. 源码形状追踪（`静态核验`）

在锁定仓库搜索 `predict_action_chunk` 与 `n_action_steps`。记录函数输出注释中 `(batch_size, n_action_steps, action_dim)`，再找转置后写入 deque 的代码。把这条轴语义写入个人笔记，不复制整段实现。

## 预期输出每部分意味着什么

- shape 正确只说明接口结构吻合，不说明动作有效。
- 数值 finite 只排除 NaN/Inf，不说明坐标和夹爪符号正确。
- `model.eval()` 与 inference mode 同时出现，才分别处理模块行为和梯度跟踪。
- 动作块被逐步执行，意味着 episode 日志应保存每个环境 action，而非只保存模型调用次数。

## 在 VLA-Arena / VLA-RelComp 真实代码和数据中的位置

- `models/smolvla/.../configuration_smolvla.py`：真实 chunk 配置与合法性检查。
- `models/smolvla/.../modeling_smolvla.py`：块预测、动作队列、裁剪到真实动作维。
- `models/smolvla/evaluator.py`：模型 device、`eval()`、episode action。
- `models/openvla/evaluator.py`：observation 预处理与夹爪后处理。
- 未来 `episode_registry` 保存 steps，而 instrumentation 轨迹另存每 step action/state；不要把块长度当环境步数。
- Every-Embodied 仅提供上面的字段类比；动作分箱、LIBERO 与社区模型排错统一列在 `../assets/按需参考索引.md`，不属于本日必读或安装任务。

## 常见错误、诊断顺序、备用路线与止损

1. 维度不匹配：打印 shape 与轴名，沿调用链逐层检查；止损 30 分钟。
2. dtype 错：打印 dtype 和数值范围；止损 20 分钟。
3. device 错：打印模型首个参数和输入 device；止损 20 分钟。
4. 动作出现 NaN：先停止 episode，保存原输入/配置，不继续扩大；止损 30 分钟。
5. 夹爪方向反了：查 evaluator 后处理，不手工“试到能抓”；止损 30 分钟。
6. PyTorch 未安装：继续纯 Python 与源码练习，不在系统 Python 盲装；本日不阻塞。

## 时间预算、最低完成线、标准完成线与选做

正常 6.5–8 小时：讲义 100–130 分钟，官方材料 90–120 分钟，最小实验 75–105 分钟，源码跟踪 90 分钟，记录/口述 60 分钟，排错上限 45 分钟。

- 最低完成线：能给 `[B,H,A]` 三个轴命名；运行纯 Python chunk；解释 dtype/device。
- 标准完成线：从配置追到 queue；说明 eval 与 inference mode 差异；解释 7 维语义为何需代码核对。
- 提前完成选做：画出模型调用次数、chunk 长度与环境 step 数的关系，列一个 stale action 风险例子。

## 当日交付物

- `validation/day02_action_chunk_user.txt`；
- shape/dtype/device 检查清单；
- 改变量前后对照；
- 90 秒复试口述：“为什么 action chunk 不是一个大 action”。

## 自测题、参考答案与复试口述

1. `[2,50,7]` 可能表示什么？
2. `model.eval()` 为什么不能替代 inference mode？
3. shape 正确为何仍可能动作全错？
4. chunk=50 是否等于 episode 只有 50 step？
5. 为什么不把 Mac MPS 时间当 A100 估计？

参考答案：1. 2 个样本、每个 50 步、每步 7 维。2. 它改变层行为但不自动禁用 autograd。3. 坐标系、归一化、符号或语义可错。4. 不等于，队列耗尽后可再次预测且 episode 有独立上限。5. 硬件、后端、精度和软件栈不同。

复试口述问题：模型输出 `[1,50,32]`，环境要 7 维，为什么不一定是 bug？答题要点：策略可能用最大动作维 padding；代码会按数据 action feature 裁剪到真实维，再逐步后处理与执行；必须看具体配置和裁剪位置。
