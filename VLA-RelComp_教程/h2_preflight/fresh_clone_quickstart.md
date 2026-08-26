# Fresh clone 唯一入口

> 本页只建立可移植目录和版本基线，不安装依赖、不下载模型、不启动仿真或 GPU。默认使用 HTTPS，私有仓库访问交给 Git Credential Manager 或已登录的 GitHub 凭据链处理；禁止把 PAT、密码或其他凭据粘贴到命令、聊天或仓库。

## 1. 获取不可漂移的受审发布

```bash
git clone --branch vla-relcomp-h2.5.1 --single-branch https://github.com/daduchen14/vla-relcomp-research-plan.git
cd vla-relcomp-research-plan
git describe --tags --exact-match
git rev-parse HEAD
git rev-list -n 1 vla-relcomp-h2.5.1
git status --short
```

HTTPS 克隆若请求身份，只使用操作系统的 Git Credential Manager/凭据弹窗或已登录的 GitHub 工具；不要把 PAT 改写进 URL。`git describe` 必须输出 `vla-relcomp-h2.5.1`，后两个 SHA 必须相同，`status --short` 必须为空。该 tag 是受审发布锁；不要切换回会继续漂移的开发分支，也不要改到 `main`。`setup` 和 `doctor` 都会再次拒绝 HEAD 不等于该 tag 的 checkout。

只有在 `ssh -o BatchMode=yes -T git@github.com` 已确认公钥可用时，才可将上述 HTTPS URL 替换为 `git@github.com:daduchen14/vla-relcomp-research-plan.git`。SSH 是可选替代，不是默认入口；验证失败时继续使用 HTTPS。

## 2. 自动定位教程

```bash
export VLA_RELCOMP_REPO="$(git rev-parse --show-toplevel)"
export VLA_RELCOMP_TUTORIAL="$VLA_RELCOMP_REPO/VLA-RelComp_教程"
export VLA_ARENA_UPSTREAM="$(cd "$VLA_RELCOMP_REPO/.." && pwd -P)/VLA-Arena-upstream"
python3 "$VLA_RELCOMP_TUTORIAL/scripts/vla_relcomp.py" setup --dry-run \
  --repo-root "$VLA_RELCOMP_REPO"
```

`setup --dry-run` 只输出 argv 计划。它不执行 clone、安装、下载或 run 初始化。不传 `--upstream` 时，它与上述变量一致，把公开 VLA-Arena 放在私有项目仓库外的 sibling `VLA-Arena-upstream`；这样 clone 不会让项目工作树变脏，也不需要放宽 `doctor` 的 clean 要求。需要本地源码核验时，按计划将公开 VLA-Arena 克隆到 `$VLA_ARENA_UPSTREAM`，然后执行：

```bash
python3 "$VLA_RELCOMP_TUTORIAL/scripts/validate_upstream.py" "$VLA_ARENA_UPSTREAM"
python3 "$VLA_RELCOMP_TUTORIAL/scripts/vla_relcomp.py" doctor \
  --repo-root "$VLA_RELCOMP_REPO" --upstream "$VLA_ARENA_UPSTREAM"
```

`doctor` 只读检查 HEAD 严格等于受审发布 tag、工作树、上游 commit 与本机工具；不把当前 Mac 或 fixture 写成 Linux/GPU 结果。

## 3. 两条不混用的路径

- 学习者本地路径：从 `$VLA_RELCOMP_TUTORIAL/day00/README.md` 开始；上游位置始终用 `$VLA_ARENA_UPSTREAM` 显式传入。
- Linux/NVIDIA 参考运行：只在用户批准实例/费用后进入 `runpod_first_run.md`，云端使用 `H2_*` 变量。

两条路径都不假设作者电脑的目录存在。
