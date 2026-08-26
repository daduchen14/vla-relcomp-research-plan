# Fresh clone 唯一入口

> 本页只建立可移植目录和版本基线，不安装依赖、不下载模型、不启动仿真或 GPU。私有仓库需使用本机已配置的 GitHub SSH 权限；不在命令、聊天或仓库中粘贴凭据。

## 1. 获取冻结功能分支

```bash
git clone git@github.com:daduchen14/vla-relcomp-research-plan.git
cd vla-relcomp-research-plan
git switch h2-linux-nvidia-preflight
git merge-base --is-ancestor fba7a7fc17c240f2f1d2ce5c245bc00704e6efa9 HEAD
git status --short
```

`merge-base` 退出 0 表示当前 HEAD 包含 H2.4 冻结基线，同时允许本分支后续的可移植修复提交。`status --short` 应为空。不要改到 `main`。

## 2. 自动定位教程

```bash
export VLA_RELCOMP_REPO="$(git rev-parse --show-toplevel)"
export VLA_RELCOMP_TUTORIAL="$VLA_RELCOMP_REPO/VLA-RelComp_教程"
export VLA_ARENA_UPSTREAM="$VLA_RELCOMP_REPO/upstream/VLA-Arena"
python3 "$VLA_RELCOMP_TUTORIAL/scripts/vla_relcomp.py" setup --dry-run \
  --repo-root "$VLA_RELCOMP_REPO" --upstream "$VLA_ARENA_UPSTREAM"
```

`setup --dry-run` 只输出 argv 计划。它不执行 clone、安装、下载或 run 初始化。需要本地源码核验时，按计划将公开 VLA-Arena 克隆到 `$VLA_ARENA_UPSTREAM`，然后执行：

```bash
python3 "$VLA_RELCOMP_TUTORIAL/scripts/validate_upstream.py" "$VLA_ARENA_UPSTREAM"
python3 "$VLA_RELCOMP_TUTORIAL/scripts/vla_relcomp.py" doctor \
  --repo-root "$VLA_RELCOMP_REPO" --upstream "$VLA_ARENA_UPSTREAM"
```

`doctor` 只读检查分支、基线祖先、工作树、上游 commit 与本机工具；不把当前 Mac 或 fixture 写成 Linux/GPU 结果。

## 3. 两条不混用的路径

- 学习者本地路径：从 `$VLA_RELCOMP_TUTORIAL/day00/README.md` 开始；上游位置始终用 `$VLA_ARENA_UPSTREAM` 显式传入。
- Linux/NVIDIA 参考运行：只在用户批准实例/费用后进入 `runpod_first_run.md`，云端使用 `H2_*` 变量。

两条路径都不假设作者电脑的目录存在。
