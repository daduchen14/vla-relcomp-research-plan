# Day 6：baseline、seed、初始状态与置信区间

## 当日目标，以及为什么服务于 VLA-RelComp

学会把成功率写成原始计数与 Wilson 置信区间，建立可信 baseline、seed 和 init-state 口径。项目的恢复率与配对差异样本很小；只报百分比会制造虚假确定性。

## 前置知识和开始前自检

完成 15 任务 manifest。自检：1/2 与 50/100 都是 50%，证据强度相同吗？更换 seed 是否保证更换 init state？

## 具体场景与最小例子

模型 5 次成功 2 次，点估计 0.4，但区间很宽。baseline 不是“最差模型”，而是固定协议下可比较的参照。每任务计数比只报宏平均更能暴露某一任务地板效应。

## 零基础知识讲义

Seed 初始化伪随机序列；同 seed 只有在代码、硬件/算法确定性和调用顺序相同等条件下才有复现意义。Init state index 选择具体场景状态。记录两者可减少“相同 seed 其实不同起点”的歧义。

成功率 `k/n` 是二项比例。Wilson 区间比简单 `p±1.96√p(1-p)/n` 在小样本和 0/1 边界更稳健。区间不是“真实概率有 95% 概率落入这次区间”的贝叶斯陈述；它是重复抽样覆盖性质。pilot 主要检验可行性，不据小样本下最终结论。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 会什么 | 跳过 |
|---|---|---|---:|---|---|
| NIST 二项区间 | 官方统计口径 | Confidence intervals for proportions，Wilson/改进法 | 35 分钟 | 解释计数和区间 | 高阶证明 |
| init 选择代码 | 看 seed/init 分工 | `eval_init_state.py:select_init_state_index` | 30 分钟 | 解释 first/episode_idx/offset | OpenPI 专属逻辑 |
| 配置 YAML | 看真实字段 | smolvla/openvla 的 seed、trials、init | 30 分钟 | 制作配置副本 | 训练参数 |

## 操作步骤、状态与预期输出

`实测` / `待用户执行`：运行 `python3 scripts/analyze_registry.py assets/sample_episode_registry.csv`。预期打印每级 `success=k/n rate=... wilson95=[low,high]`。解释 L0 只有 1 条时区间极宽，不能说模型稳定。

改变量：复制 fixture，再添加 9 条与 L0 相同结果的合法行，观察 n 增大后区间变化。保持成功比例近似不变。`静态核验` 官方配置默认 trials=10 且有 seed/init 字段。`估计—未运行` 的真实 pilot 是每模型 5 tasks×3 levels×5 trials=75 episodes；正式执行 `待用户执行`。

## 在真实代码中的位置

配置字段位于 evaluation YAML 和 evaluator dataclass；init index 由 `select_init_state_index` 产生；结果由 evaluator 聚合。项目 registry 必须逐 episode 保存，汇总表由脚本生成，不能手改百分比。

## 常见错误、诊断顺序、备用路线与止损

分母漏掉异常 episode：异常先单独分类，再预先规定是否进入分母；只报平均：回到任务级；seed 重复但 init 不同：检查 selection mode；CI 实现错误：用 0/5、5/5 边界测试。统计排错上限 45 分钟，不在小 pilot 做复杂模型。

## 时间预算、最低完成线、标准完成线与选做

正常 5.5–7 小时。最低：计算并解释 k/n 与 Wilson CI。标准：写 pilot 注册表规则与异常口径。选做：比较 Wald 和 Wilson 在 0/5 的差异，但最终只用预登记 Wilson。

## 当日交付物

分析日志、一个增大 n 的对照、pilot registry 草案、2 分钟口述。

## 自测题、参考答案与复试口述

问题：2/5 能否写 40% 后结束？seed 等于 init state 吗？CI 表示什么？异常如何防止冒充失败？为何报任务级？

参考答案：必须给计数/区间；不等于；描述方法在重复抽样下的覆盖；异常分栏并保留日志；宏平均可能掩盖地板/天花板。复试口述：解释为何 pilot 不用于稳定科学结论。
