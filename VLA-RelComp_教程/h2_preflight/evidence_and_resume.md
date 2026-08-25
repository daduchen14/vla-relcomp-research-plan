# 证据、断点恢复与 Gate 交接

## 每个检查点的最小证据

```text
runs/<run_id>/
├── run_manifest.json              # 范围、锁定 commit、证据声明
├── checkpoint_state.json          # C0–C7: pending/running/passed/failed/skipped
├── system/probe.json              # 主机/GPU/磁盘/EGL/工具
├── commands/<checkpoint>/
│   ├── command.json                 # argv、白名单 env、时间、退出码、GPU 快照
│   ├── stdout.txt
│   └── stderr.txt
├── configs/                       # 当次渲染后不再改的 YAML
├── logs/ results/ videos/         # evaluator 原始输出
├── registry/episode_registry.csv  # 每个 episode 一行
├── registry/c7_episode_registry.csv # 只含 manifest 允许的 C7 行
├── registry/stage_sidecar.csv     # C6 原始行为量，阈值未校准
├── patches/                       # 项目 wrapper/patch 的副本与 hash
├── gates/                         # Gate 1–3 实例
└── hashes/sha256_manifest.json    # 最后封存
```

## `checkpoint_state.json` 更新规则

1. 命令开始前：把当前 Cx 设为 `running`，记录命令证据目录。
2. 退出 0 且成功条件人工核对完：设 `passed`。退出 0 不自动等于 episode success；它只表示命令正常收尾。
3. 失败：设 `failed`，填 `failure_class`、首个有效堆栈、止损时间和 `retry-01` 路径。
4. 条件不触发（例如 Smol 已过 Gate 2，不需 OpenVLA）：设 `skipped`，写冻结规则与证据，不写 `passed`。
5. 继续运行前先用 `h2_finalize_evidence.py` 检查已有文件。不再跑 `passed`，不覆盖 `failed`。

## episode 记录的两层口径

- 主层：`success` 只来自锁定环境 official goal success。
- 诊断层：逐步接触、高度、目标—参照距离、predicate 原始值放 `stage_sidecar.csv`。真实 rollout 与人工抽查前，`definition_status` 必须是 `uncalibrated`，阈值列留空。

行为诊断不改 official success，不创建“修正成功率”。

## C6 只读 patch 验收

- 接入点在 `env.step` 之后、done break 之前；
- 输入只是 env state/info/原 observation 的副本；
- 输出只是 sidecar，不返回给 policy/env；
- 同 seed/init 在 logger on/off 各跑一次，action 序列和 official result 应不因 logger 变化；
- 保存 patch 和 SHA-256，upstream `git status --short` 仍为空。

## C7 最小 pilot 交接

1. 使用 `pair_manifest_template.csv`；同一设计共用 `pair_family`，每个 seed 使用唯一 `pair_id` 且恰有两条 condition。每个 pair_id 共享 family/seed/init/model/config/changed_factor；同一 family 至少两个 seed。
2. 先做 BDDL goal/instruction 同步和环境可达回放，然后才跑模型。
3. runner 对每个 condition 先 `none`，再仅 `language_oracle`；全局 RNG、env seed、registry seed 同源，每次重建 env 并清 policy state；同时报 failure→success recovery 和 success→failure damage。
4. Oracle 使用的 object id/真值框/goal 解析必须标 `privileged`，不进入最终方法。
5. 至少 2 seeds 的重复证据齐全后才填 Gate 3；单个好看视频不过 Gate。
6. C7 使用独立 registry；事后审计以 manifest 为唯一允许集合，未登记、缺行、重复、pair_family/changed_factor 等字段漂移或证据路径为空均失败。

## 云实例关闭前检查

- `h2_finalize_evidence.py --run-root "$H2_RUN"` 退出 0；
- `episode_registry.csv` 与存在时的 `c7_episode_registry.csv` 均被扫描，所有行的 video/log/result 非空且存在，`missing_registry_paths=0`；
- `git -C "$H2_UPSTREAM" status --short` 为空；
- 已将当次 `runs/$H2_RUN_ID` 下载/备份到持久存储；
- 云控制台确认实例已停止计费。
