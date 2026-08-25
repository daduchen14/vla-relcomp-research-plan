# Day 9：读懂 CBDDL——从语言到 init、对象与 goal

## 当日目标，以及为什么服务于 VLA-RelComp

把 15 个 BDDL 解析成任务—对象—关系—目标表，并人工核对至少 5 项。CBDDL 是研究的真值来源：反事实是否有效、success 如何判定、oracle 是否泄漏，都不能只凭英文任务名猜。

## 前置知识和开始前自检

完成 Day 5 的 manifest。自检：`:obj_of_interest` 是否一定只有被抓物？`:language` 与 `:goal` 是否语义相同但结构相同？region 是物体还是放置范围？

## 具体场景与最小例子

某 L0 文件语言要求“抽屉顶层的番茄放到花瓶与茶壶之间的碗上”；`:init` 中真正目标番茄是 `tomato_3`，目标碗是 `porcelain_bowl_3`，`:goal` 是 `(On tomato_3 porcelain_bowl_3)`。自然语言里的空间描述负责选择实体，goal 只检查最终关系。

## 零基础知识讲义

CBDDL 是声明式任务定义：`:regions` 描述可采样位置，`:fixtures` 是场景固定装置，`:objects` 声明可操作/参照实体，`:obj_of_interest` 给关注对象，`:init` 约束开局，`:goal` 定义完成条件。声明“希望世界满足什么”，不是给机器人逐步控制代码。

同名对象类型可有多个实例，英文说 tomato 不等于 `tomato_1`；必须由 init 中的位置关系解析目标。`obj_of_interest` 也可能列目标与参照对象，不能当唯一目标字段。goal predicate 的参数是自动 success 真值；本项目的 target/reference/relation 由 BDDL 登记并人工校验。

解析器是初筛工具，不是形式语言完整实现。它检查 5/5/5、提取块和 goal；复杂嵌套与语义仍需源码解析器和人工回放确认。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 会什么 | 跳过 |
|---|---|---|---:|---|---|
| 论文 CBDDL | 官方概念 | PDF pp.3–4 §2.1；pp.19–25 附录 E | 60 分钟 | 解释声明式结构 | 动态/安全扩展细节 |
| 场景构建文档 | 对照语法 | README 链接的 Scene Construction：file structure、initial/goal | 45 分钟 | 找 section | 动态障碍 |
| 目标 15 BDDL | 真实任务 | 每级至少 2、2、1 项 | 90 分钟 | 识别对象实例与 goal | 全部 region 坐标 |
| success 源码 | 连接 predicate | `_eval_predicate`、`_check_success` | 45 分钟 | 说明合取判定 | cost |

## 操作步骤、状态与预期输出

`实测` / `待用户执行`：运行 Day 5 的 `parse_bddl.py`，预期 15 行、每级 5 行。打开 CSV，任选 5 行，回到原文件逐字核 `language`、`obj_of_interest`、`goal`。把 `goal_verified=1` 只写在人工核过的清单。

变量实验：把个人副本里某 task 的 `:goal` 对象改名为不存在实例，解析器可能仍能提取字符串；这展示“语法提取成功不等于任务有效”。不要改 upstream。

`静态核验`：15 个 BDDL 与同名 `.pruned_init` 一一存在。`估计—未运行`：仿真中逐项加载与可达性回放尚未做；正式为 `待用户执行`。

## 预期输出及意义

manifest 的 `language` 是人类指令，`obj_of_interest` 是声明列表，`goal` 是结构化终态，`init_predicate_count` 只用于完整性提示。路径列支持回溯。任何字段空缺都不能凭任务名补猜。

## 在真实代码中的位置

BDDL/Init 目录、`benchmark/__init__.py` 注册、suite task map 排序、`bddl_base_domain.py` parsed problem 与 predicate evaluator。项目输出 `manifests/task_manifest.csv`，带人工核验列而非覆盖生成文件。

## 常见错误、诊断顺序、备用路线与止损

先查括号/section，再查对象声明，再查 init 关系，再查 goal 参数，最后查仿真可达。单文件静态 30 分钟、解析器 45 分钟止损；解析失败改进项目脚本，不改上游语义。无法获得 goal/state 才是 D1 硬风险，普通解析 bug 不是。

## 时间预算、最低完成线、标准完成线与选做

正常 6.5–8 小时。最低：15 行 manifest+5 项核对。标准：能从语言解析到具体实例和 goal，并说出自动解析边界。选做：画一个 BDDL section 树。

## 当日交付物

task manifest、5 项核对表、一个“解析成功但语义无效”反例、2 分钟口述。

## 自测题、参考答案与复试口述

问题：谁判 success？obj_of_interest 等于目标吗？init 与 goal 分工？为何要人工核对？能否按模型输出改 goal？

参考答案：goal predicate；不必然；前者开局、后者终态；轻量解析不验证语义/可达性；不能，会污染任务。复试口述需用一个真实 BDDL 实例串起 language→init→goal。
