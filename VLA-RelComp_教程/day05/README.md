# Day 5：L0/L1/L2、OOD 与组合泛化

## 当日目标，以及为什么服务于 VLA-RelComp

用目标套件 15 个真实任务理解训练分布、OOD、组合泛化与三级评测，避免把“更难”误解成单一噪声强度。VLA-RelComp 只研究此套件的新对象—关系组合，不扩到其他 suite。

## 前置知识和开始前自检

能解释 episode 与行为克隆。自检：学过 tomato、bowl、on 是否保证会做一个新 tomato-bowl-on 组合？L1/L2 可否用于训练？

## 具体场景与最小例子

模型在 L0 见过对象和空间关系的若干组合；L1 重新组合已见对象与关系；L2 把关系放进新场景配置。组合泛化问的是已学成分能否重组，不是简单的“看见全新物体”。论文 PDF p.36 表22给出全部任务。

## 零基础知识讲义

训练分布是生成训练样本的组合与条件；OOD 是测试条件偏离它。IID/OOD 不是某条样本永恒属性，而是相对训练协议。组合泛化关注组成元素可能分别见过、组合未见。VLA-Arena 明确 fine-tuning 限 L0；L1/L2 用于泛化评测。

L0 不是“必然简单成功”，L2 也不是“所有方面全新”。若主模型 L0 几乎全失败，就没有足够成功对照来判断 L1/L2 的新增组合效应，因此 D8 设最低成功样本门槛。

不要把论文已报告的 L0→L1/L2 掉点当创新。项目增量是匹配反事实、阶段链与 oracle 恢复；今天只建立正确分层。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 会什么 | 跳过 |
|---|---|---|---:|---|---|
| VLA-Arena v4 | 官方定义 | PDF p.6 PrepositionCombinations；p.36 §G.8/表22 | 45–60 分钟 | 逐级解释任务 | 其他 suites |
| 任务 map | 对照真实字符串 | `vla_arena_suite_task_map.py` 同名键 | 30 分钟 | 核对 5/5/5 | 其他 map |
| BDDL 目录 | 看级别不是空标签 | 三个 `level_*` 各抽一项 | 45 分钟 | 对比 language/init/goal | regions 全坐标 |

## 操作步骤、状态与预期输出

`实测` / `待用户执行`：

```bash
cd '/Users/nokian97/Documents/Codex/2026-08-24/x/方向筛选/VLA-RelComp_教程'
mkdir -p validation/generated
python3 scripts/parse_bddl.py --upstream-root '../../work/VLA-Arena-upstream' --output validation/generated/task_manifest.csv
```

预期 `wrote 15 tasks`，levels 为 `{0:5,1:5,2:5}`。CSV 每行有 language、obj_of_interest、goal 和路径。若上游克隆不在该路径，改 `--upstream-root`，不要改脚本逻辑。

`静态核验`：随机抽每级一行，与 PDF p.36 和原 BDDL 对照。`估计—未运行`：SmolVLA 5 个 L0 task×5 trials 共 25 episodes；当前不填成功率。正式执行为 `待用户执行`。

变量实验：从 manifest 选择 L0/L1 两项，只圈出对象、起始关系、目标关系和场景中变化的字段。若超过一个因素变化，不称“最小反事实”。

## 在真实代码中的位置

注册在 `benchmark/__init__.py`，任务字符串在 `vla_arena_suite_task_map.py`，真值在 BDDL，初态在同名 `.pruned_init`，配置用 `task_level`。短名只用于 README 展示。

## 常见错误、诊断顺序、备用路线与止损

短名报 suite 不存在时改用注册名；manifest 非 15 行先检查锁定 commit；把 L2 当全新对象时回到 p.36；想扩 suite 写 parking lot。路径排错 20 分钟，任务语义单项 30 分钟；不因普通解析错误暂停项目。

## 时间预算、最低完成线、标准完成线与选做

正常 6–7.5 小时。最低：生成 15 行 manifest、解释三等级与 OOD 相对性。标准：人工核对 5 项并写出一组候选配对为何尚非严格反事实。选做：制作关系/对象组合矩阵，不跑模型。

## 当日交付物

`task_manifest.csv`、5 项人工核对表、L0/L1/L2 一页解释、90 秒口述。GPU 结果栏留空并标记。

## 自测题、参考答案与复试口述

问题：OOD 相对什么定义？组合泛化与新对象识别有何不同？为何只用 L0 训练？L0 低成功为何破坏诊断？复跑三级掉点为何不创新？

参考答案：相对训练协议；前者重组已见成分，后者对象类别/实例可未见；防止测试泄漏；缺少成功对照导致地板效应；原论文已证明总体下降。复试口述需用 p.36 的具体任务说明 L1/L2。
