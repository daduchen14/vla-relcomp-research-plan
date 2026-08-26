# Day 10：四段状态探针与只读 instrumentation

## 当日目标，以及为什么服务于 VLA-RelComp

把总体 success 拆成目标接触、抬升、靠近参照、终态满足四段事件，设计只读日志而不改变 action。它是项目核心：从“失败了”变成可观察的断点，但不越界宣称内部理解。

## 前置知识和开始前自检

能读 BDDL 和 trajectory CSV。自检：接触错物体算 target contact 吗？抬升阈值相对桌面还是绝对 z？终态成功能否反推所有阶段都被正确检测？

## 具体场景与最小例子

synthetic fixture 中，step2 接触、step3 达到 fixture 抬升条件、step5 达到 fixture 靠近条件、step6 relation 成立。探针报告首次事件 step，而不是只报最终布尔值，便于检查顺序。fixture 里的数值只验证脚本分支，不是未来真实实验阈值，更不是从社区杯子任务迁移来的阈值。

## 零基础知识讲义

Instrumentation 是测量旁路：读取环境状态、计算事件、写日志，不改 observation、action、物理或 goal。操作性定义必须固定对象实例、接触稳定条件、高度基准/阈值、距离度量/持续步数和 predicate。阈值是研究选择，应先用少量轨迹和人工回放校准，再冻结。

四段事件是行为证据：正确接触说明行为指向目标，不证明模型内部识别；抬升说明抓取阶段完成；距离下降说明搬运方向；goal 是 CBDDL 最终判定。事件可非严格单调，需保存原始每步值和首次/持续条件。

### 双层记录：主评价与辅助诊断

| 层级 | 记录内容 | 用途 | 纪律 |
|---|---|---|---|
| A. 官方 goal success（主要评价） | 锁定环境 `_check_success` / `info['success']`、done、timeout 与官方 goal predicates | 计算论文主表、Gate 成功率和模型比较 | 不被阶段探针覆盖；即使视频观感不好也先原样保存官方值 |
| B. 行为过程诊断（辅助） | 目标接触、相对抬升、向参照靠近、终态关系的原始逐步量、首次事件和定义版本 | 定位失败发生在哪一段、挑选录像复核、形成反事实假设 | 不另造“修正版成功率”，不取代官方指标，不作为提前改标签的理由 |

真实运行前，B 层只保存可直接读取的原始量和 `definition_status=uncalibrated`；不得预填接触持续步数、抬升高度或距离阈值。获得真实 rollout 后，先盲抽少量成功/失败视频与状态轨迹，提出候选阈值，检查与人工判读的一致性，再在看正式 L1/L2 结果前冻结 `definition_version`。社区项目的杯子高度、姿态或距离数值一律不迁移。若 B 层与 A 层不一致，报告为“官方 success + 诊断分歧”并复核视频，官方 success 仍是主评价。

## 必读材料

| 材料 | 为什么看 | 看哪里 | 看多久 | 会什么 | 跳过 |
|---|---|---|---:|---|---|
| 数据字典 | 固定操作定义 | §二、§四、§六 | 35 分钟 | 列四段字段 | E4 |
| 环境源码 | 找只读点 | `bddl_base_domain.py:step/_check_success`、obs/state helpers | 60 分钟 | 选旁路位置 | 修改物理 |
| evaluator | 找 episode loop | action 后 `env.step` 至 done | 45 分钟 | 设计 logger 调用 | 模型训练 |

## 操作步骤、状态与预期输出

`实测` / `待用户执行`：

```bash
cd "$(git rev-parse --show-toplevel)/VLA-RelComp_教程"
python3 scripts/stage_probe_demo.py assets/sample_trajectory.csv
```

预期首次 step 为 contact=2、lift=3、approach=5、relation=6，source 明确 synthetic。变量实验：把最后 relation 改 0，前三段不变而 success 段缺失；说明分段信息多于最终标签。

`静态核验`：候选插入点在 evaluator `env.step` 之后、done break 之前；只读取状态并写项目日志。`估计—未运行`：真实对象接触 API、坐标阈值和持续步数需 Linux 仿真 pilot 校准；正式为 `待用户执行`。

真实 episode 汇总至少并列保存 `official_goal_success`、`done_reason`、`diagnostic_definition_version` 和四段事件；校准前后不得覆写这些历史字段。当前 fixture 输出只证明 B 层记录器能分段，不产生 A 层真实成功率，也不完成阈值校准。

## 在真实代码中的位置

上游 env step 返回 `info['success']`；项目新增应放 `VLA-RelComp/src/instrumentation`，通过小补丁/包装器接入 evaluator，upstream 保持不改或保存明确 patch。registry 存 episode 汇总，trajectory 文件存每步状态。

## 常见错误、诊断顺序、备用路线与止损

错实例→查 task manifest；高度基准漂移→用相对初始支撑面；距离偶然抖动→预登记持续步数；logger 改 observation/action→立即撤销设计；探针与视频不符→保留原始 state 并人工抽查。单事件定义 60 分钟止损。若状态 API 最终不可获得且无等价只读替代，记录为 Gate 3/D1 硬风险。

## 时间预算、最低完成线、标准完成线与选做

正常 6–8 小时。双层表替代“分段事件与 success 关系”的抽象辨析，不增加必修时长。最低：运行样例并写四个候选操作定义，同时说明官方 success 是主指标。标准：伪代码、原始字段、阈值校准/冻结流程与人工抽查表齐全。选做：只在真实 pilot 后比较候选持续条件；当前不预设数值。

## 当日交付物

stage probe 日志、操作定义表、只读接入伪代码、5 条人工抽查模板、口述。

## 自测题、参考答案与复试口述

问题：探针为何必须只读？接触能证明识别吗？为什么保存首次 step？官方 success 与行为诊断谁是主指标？阈值何时冻结？state 可否给最终模型？

参考答案：避免改变被测行为；不能；支持顺序/回放核验；官方 goal success；真实 pilot 与人工校准后、正式结果前；不能用测试特权 state。复试口述：先声明官方 success 是主评价，再解释四段各能说与不能说什么。
