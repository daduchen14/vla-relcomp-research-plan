# Day 7：SmolVLA、OpenVLA 与“可分析模型”的选择

## 当日目标，以及为什么服务于 VLA-RelComp

理解模型选择不是排行榜，也不是越轻越好：诊断需要足够 L0 成功样本。准备 OpenVLA 单 episode 的命令级检查、资源字段和失败分类，但不在当前阶段下载权重。

## 前置知识和开始前自检

能解释 baseline、地板效应、action token/chunk。自检：SmolVLA 更小是否自动适合作主诊断模型？主诊断模型和后续可微调模型必须相同吗？

## 具体场景与最小例子

若 SmolVLA 在 25 个 L0 episode 只成功 1 次，L1 为 0 不说明“组合差异导致下降”，因为模型连训练组合也几乎不会。OpenVLA 若 L0 足够，则用于诊断；后续最小修复仍可选择更易训练的轻量模型。这是研究角色分工，不是排名。

## 零基础知识讲义

主诊断模型需满足能力下限、执行稳定和70天吞吐可行。更大模型可能显存/时延更高，但能提供成功对照；量化会引入额外变量，所以首次诊断默认 80GB GPU 且不量化。模型卡尺寸只是资产规模，真实峰值显存必须实测。

OpenVLA 自回归输出动作 token，再反归一化/处理为连续动作；SmolVLA 用轻量 VLM+动作专家预测连续 chunk。架构差异是背景，不提前作为失败原因。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 会什么 | 跳过 |
|---|---|---|---:|---|---|
| 两个官方模型卡 | 核对身份/文件树 | card、files/revision | 35 分钟 | 记录精确 revision | 下载权重 |
| 两个 evaluator/config | 命令级比较 | dataclass、初始化、episode、YAML | 60–90 分钟 | 列共同字段/差异 | trainer |
| 论文模型说明 | 不凭印象描述 | PDF pp.6–7 与 p.39 H.1 | 35 分钟 | 准确描述输出族 | 全超参 |

## 操作步骤、状态与预期输出

`静态核验`：复制而不编辑 upstream YAML，逐项检查 checkpoint、suite、level、trials、seed、init、日志、视频、replacement。目标配置必须 `use_replacements:false`。

`实测`：用 Python 标准库读 YAML 文本并搜索这些键，保存结果；不需要 PyYAML。`待用户执行`：正式 A100 80GB 上先 1 episode smoke test，记录模型 revision、峰值显存、墙钟、异常和视频。`估计—未运行`：当前不承诺显存或完成时间。

预期成功形态是 checkpoint 完整加载、无 NaN、environment step 推进、episode 以 success/timeout 结束并留证据；仅“下载完成”不算。

## 在真实代码中的位置

`models/{smolvla,openvla}/evaluator.py`、`configs/evaluation/{smolvla,openvla}.yaml`、两个 HF 模型卡。SmolVLA 配置键是 `policy_path`，OpenVLA 是 `pretrained_checkpoint`；教程不能混写。

## 常见错误、诊断顺序、备用路线与止损

先核配置解析，再 checkpoint revision/完整性，再 CUDA OOM，再渲染，再动作。OOM 不立即量化：先确认 80GB 正确实例与无重复模型。OpenVLA 单 episode 排错最长一工作块 90 分钟，完整 D7 一日；需要登录/token 或付费时暂停请求用户。

## 时间预算、最低完成线、标准完成线与选做

正常 6–8 小时。最低：完成双模型配置对照与失败分类。标准：写可复制 smoke-test 卡及资源记录模板。选做：比较输出接口，不比较所有 VLA。

## 当日交付物

双模型对照表、两份配置副本草案、OpenVLA smoke-test 卡、口述“为何轻量不等于适合诊断”。

## 自测题、参考答案与复试口述

问题：主诊断为何需要 L0 成功？能否因 OOM 直接 4bit？两个角色可否不同模型？模型卡大小等于显存吗？当前得到了 OpenVLA 结果吗？

参考答案：需要可匹配成功对照；不能先引入量化混杂；可以；不等于；没有，只有静态核验。复试口述必须提地板效应、角色分工与资源实测。
