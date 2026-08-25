# VLA-RelComp 教程制作与验证进度日志

> 状态口径：`待制作`、`制作中`、`待验证`、`已验收`、`阻塞`。本日志记录教程工程进度，不冒充用户真实学习进度或 GPU 实验结果。

## 总队列

| 工作包 | 状态 | 验收重点 | 证据位置 |
|---|---|---|---|
| 必读材料与接手核验 | 已验收 | 顺序完整、冻结项与暂停条件一致 | `validation/00_内部接手核验.md` |
| Day 0 | 已验收 | 开工诊断、工具纪律、版本冻结、证据标签 | `day00/README.md` |
| Day 1 | 已验收 | VLM/VLA、observation/state/action/episode/success 闭环 | `day01/README.md` |
| Day 2 | 已验收 | tensor/device/inference、7维动作、action chunk、随机 episode | `day02/README.md` |
| Day 3 | 已验收 | Transformer、视觉编码、语言与动作头、单 episode 路径 | `day03/README.md` |
| Day 4 | 已验收 | 行为克隆、复现性、成功判定、Gate 1 | `day04/README.md` |
| Day 5 | 已验收 | L0/L1/L2、OOD、组合泛化 | `day05/README.md` |
| Day 6 | 已验收 | baseline、seed、置信区间、pilot 记录 | `day06/README.md` |
| Day 7 | 已验收 | 双模型诊断价值、OpenVLA 静态运行准备 | `day07/README.md` |
| Day 8 | 已验收 | 主诊断模型选择、Gate 2 | `day08/README.md` |
| Day 9 | 已验收 | CBDDL、任务清单、对象/关系/goal | `day09/README.md` |
| Day 10 | 已验收 | 四段状态事件与只读 instrumentation | `day10/README.md` |
| Day 11 | 已验收 | 最小反事实、配对与控制变量 | `day11/README.md` |
| Day 12 | 已验收 | 语言/视觉 oracle、对照与特权信息 | `day12/README.md` |
| Day 13 | 已验收 | 恢复率、配对检验、置信区间、失败边界 | `day13/README.md` |
| Day 14 | 已验收 | 数据泄漏、Gate 3、三分钟答辩 | `day14/README.md` |
| 免费本地验证 | 已验收 | 脚本/链接/格式/fixture 均留日志 | `validation/01_静态与轻量验证报告.md` |
| 零基础学习者审计 | 已验收 | 无需自行拼路线；命令、输出、止损完整 | `validation/02_零基础学习者视角审计.md` |
| 研究协议一致性审计 | 已验收 | 与 D1、数据字典、泄漏边界一致 | `validation/03_研究协议一致性审计.md` |
| 完成报告与私有备份 | 已验收 | 验收矩阵、GPU 待验证项、风险和下一阶段 | `validation/04_完成报告.md` |

## 变更记录

### 2026-08-25

- 按用户指定顺序完整读取 7 份必读文件，共 842 行。
- 完成内部接手核验；确认不重开选题、不启动付费阶段。
- 建立 Day 0—14 教程、验证、审计与交付队列。
- 锁定官方 SHA，核验 15 BDDL/15 init、关键函数、论文 PDF 页码与 13 个官方链接。
- 完成 Day 0—14、配置/模板、7 个免费脚本并通过自动验证。
- 完成零基础学习者审计与研究协议一致性审计。
- 按用户冻结范围最小整合 Every-Embodied：Day 2 用单帧字段映射替代抽象 shape 例子，Day 4 用五段流程替代抽象分布偏移说明，Day 10 增加“官方 success 主评价＋行为过程辅助诊断”；其余材料统一为非必读按需索引。未增加安装、GPU、仿真、下载或必修时长，并重新通过原有离线验证。

## 当前下一步

本阶段已完成。下一阶段须经用户批准云平台、预算和付费后，执行 Linux/NVIDIA 完整参考运行。
