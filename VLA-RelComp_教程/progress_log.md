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
| H2 Linux/NVIDIA 预检包 | 已验收 | C0–C7、资产/环境锁、脚本、证据、恢复、安全审计 | `validation/05_H2预检完成报告.md` |
| H2.1 证据链修补 | 已验收 | 逐 episode 视频、吞异常 fail-closed、manifest 绑定、多 seed C7 runner、下载前元数据闸门 | `validation/05_H2预检完成报告.md` |
| H2.2 云端创建与费用闸门 | 已验收（未购买） | 唯一平台/规格、30 美元上限、SSH 交接、库存与替代停止条件 | `h2_preflight/runpod_first_run.md` |
| H2.3 检查点状态机 | 已验收 | C0→C7 合法转换、前置 Gate、终态证据、失败不可覆盖 | `validation/h2_static_validation.json` |
| H2.4 云端冷启动交接 | 已验收（未连接） | 版本化 SSH 传输、硬件/运行时两段探针、uv 安装锁与文件校验 | `validation/h2_static_validation.json` |

## 变更记录

### 2026-08-25

- 按用户指定顺序完整读取 7 份必读文件，共 842 行。
- 完成内部接手核验；确认不重开选题、不启动付费阶段。
- 建立 Day 0—14 教程、验证、审计与交付队列。
- 锁定官方 SHA，核验 15 BDDL/15 init、关键函数、论文 PDF 页码与 13 个官方链接。
- 完成 Day 0—14、配置/模板、7 个免费脚本并通过自动验证。
- 完成零基础学习者审计与研究协议一致性审计。
- 按用户冻结范围最小整合 Every-Embodied：Day 2 用单帧字段映射替代抽象 shape 例子，Day 4 用五段流程替代抽象分布偏移说明，Day 10 增加“官方 success 主评价＋行为过程辅助诊断”；其余材料统一为非必读按需索引。未增加安装、GPU、仿真、下载或必修时长，并重新通过原有离线验证。
- H2 Linux/NVIDIA 预检：建立只读上游、隔离 uv 环境、固定 HF revision/大文件哈希、C0–C7 检查点、真单 episode wrapper、命令收据、状态 sidecar schema、断点恢复和证据封存。当前标记为 Mac 免费实测/静态核验，未运行 GPU、MuJoCo episode、checkpoint 或 Gate。
- H2.1：修复 pilot 空 video_path 与 episode 审计 fail-open；C3/pilot/C7 统一捕获 evaluator 吞掉的 `Episode error:`；C7 以 pair_family/pair_id/condition 绑定 manifest，支持同一 manifest 多 seed 并新增可执行 language-oracle runner；下载前用官方 metadata 核实际 snapshot 字节和完整性。fixture/static 通过，不是 GPU 结果。
- H2.2：将首台真实运行固定为 RunPod 按需 `1×A100 SXM 80 GB`、官方 Ubuntu 22.04/CUDA 11.8 PyTorch 模板、50 GB container + 300 GB `/workspace` volume、Full SSH；依据 2026-08-25 官方价格建立 16 GPU·h/30 美元硬上限与不自动替换规则。未登录、未充值、未购买、未运行。
- H2.3：增加 fail-closed 检查点状态机，消除云上人工编辑 `checkpoint_state.json`、跳级或覆盖失败证据的风险；锁定官方 commit 的全包回归通过 22 项必需文件与 16 组检查，未下载模型、未运行 GPU/episode。
- H2.4：增加只接受安全 SSH alias 的版本化教程传输器，拒绝覆盖并以 rsync checksum dry-run 复核；把 C0 拆为硬件保留探针与工具安装后 runtime 探针，固定 uv 0.10.8 安装脚本的 68,278 字节/SHA-256。最新全包回归通过 25 项必需文件与 19 组检查；未连接云主机。

## 当前下一步

H2 免费预检和云端创建说明已完成。下一阶段只等待用户明确批准 RunPod 最多 30 美元费用、确认最终创建动作，并提供公开 SSH 连接参数或已配置的 `vla-relcomp-h2` alias；不接收聊天中的私钥/token/密码。获批后从 C0 系统探针开始，严格按 C0→C7 执行。
