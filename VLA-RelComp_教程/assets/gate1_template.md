# Gate 1（D4）

H2 运行对应：先完成 C0–C3；引用 `run_manifest.json`、C3 command receipt、`one_episode_*.json`、registry 行、日志与视频。`--dry-run` 和 fixture 不能勾选本 Gate。

- [ ] Ubuntu/NVIDIA 环境与版本记录完整
- [ ] 锁定 repo/model/data revision
- [ ] 同配置单 episode 可重复启动
- [ ] task/level/seed/init/action steps/终态可回溯
- [ ] 至少一个视频与对应日志/结果
- [ ] 环境异常、模型失败、评测失败分栏
- [ ] 用户能解释两张图像、robot state、instruction、7维 action 闭环

结论：`通过 / 再排错一个工作日 / 请求核查硬条件`
