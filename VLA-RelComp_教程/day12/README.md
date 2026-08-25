# Day 12：语言 oracle、视觉对象提示 oracle 与对照

## 当日目标，以及为什么服务于 VLA-RelComp

为一种语言 oracle 和一种视觉提示 oracle 写最小、可撤销、带无干预对照的规范。Oracle 用特权信息定位限制环节，不是最终方法涨点。

## 前置知识和开始前自检

有有效 pair 草案和四段探针。自检：oracle 后成功能证明原模型“理解”吗？测试真值能否进入最终修复？原成功被 oracle 破坏要不要报告？

## 具体场景与最小例子

原指令较长；语言 oracle 统一为 `target=tomato_3; source=in top drawer; action=place; relation=on; reference=bowl_3 between vase and teapot`。视觉 oracle 在渲染图上给目标/参照加可撤销轮廓。两者均利用 simulator 真值，必须标 privileged。

## 零基础知识讲义

Oracle 是把某环节变得近似正确，观察整体是否恢复的诊断干预。语言 oracle 降低关系/对象解析负担但仍可能改变 token 分布；视觉提示降低对象选择负担但也可能遮挡/产生新纹理。因此需无干预对照、damage 指标和相同 seed/init。

恢复只说明该信息/干预对行为有帮助，不能唯一证明内部瓶颈；无恢复也可能因控制失败或干预格式不兼容。最终修复必须只用部署时可得输入，不能保留真值框/对象 id。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 会什么 | 跳过 |
|---|---|---|---:|---|---|
| 实验协议 E3/泄漏 | 冻结边界 | §三 E3、§五 | 30 分钟 | 区分诊断/方法 | E4 细节 |
| 论文扰动诊断 | 避免重复贡献 | PDF §2.3/2.4、§4.3、附录 F | 60 分钟 | 说明与现有 W/V 扰动差异 | 全扰动等级 |
| replacement 代码 | 看官方语言改写入口 | config replacements 与 `apply_instruction_replacement` | 40 分钟 | 知道默认需关闭 | WordNet 实现细节 |

## 操作步骤、状态与预期输出

`静态核验`：确认 baseline `use_replacements:false`；语言 oracle 另设 intervention 名。`待用户执行`：写两份 intervention spec，含输入真值、变换、撤销、对照、风险、输出字段。`实测`：在 fixture registry 对比同 task/seed/init 的 none 与 language_oracle 行，列失败→成功；视觉行显示阶段改善但 goal 未恢复。`估计—未运行`：真实渲染提示与 checkpoint 行为未测。

预期报告同时含 `intervention_recovery` 与 `intervention_damage`；恢复样本分母是原失败，damage 分母是原成功。fixture 仅教学。

## 在真实代码中的位置

语言变体通过 evaluator 指令入口；视觉提示应包装 observation 渲染后、模型预处理前；原始图像必须保留。实现放 `src/interventions`，oracle 输入字段不进入最终修复配置。

## 常见错误、诊断顺序、备用路线与止损

先验证 baseline 未改，再验证一项 oracle，检查遮挡/token 长度，再看恢复与damage。单 oracle 原型 90 分钟止损；若提示破坏图像，改为更小轮廓并披露。不得调到测试结果最好看。

## 时间预算、最低完成线、标准完成线与选做

正常 6–8 小时。最低：两个规范+无干预对照。标准：特权信息、damage、可撤销与最终方法隔离均写清。选做：设计 placebo 提示但不扩第三种 oracle。

## 当日交付物

language/visual spec、对照表、首轮 fixture 结果、代码差异计划、口述。

## 自测题、参考答案与复试口述

问题：oracle 为何不是作弊方法？恢复证明什么？无恢复证明什么？damage 为何重要？真值何时必须移除？

参考答案：它明确只作诊断且与方法分栏；干预信息可能缓解限制；不能单独证明该环节无问题；防止干预普遍扰乱行为；最终修复推理前。复试口述要说明有限因果解释。
