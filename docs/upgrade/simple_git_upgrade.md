# 代码自动升级方案（简化版 —— 内置 git + 启动时检查）

> 文档版本：v1.0
> 创建日期：2026-05-04
> 适用范围：Windows / macOS / Linux 三平台 ZIP 分发包

---

## 一、背景

项目以 ZIP 形式分发给普通终端用户，用户点 `start.bat` / `start.command` 即用。当前没有代码自动升级能力，仅支持 Alembic 数据库迁移。

用户已明确：
- **用户是小白**，但**可以自带 git 二进制**
- **暂不需要灰度发布与紧急撤回**
- **二进制锁定**（MySQL / ffmpeg / uv 不更新），仅升级 Python 代码
- 希望**尽量简单**，不要复杂的 Updater 进程和状态机

---

## 二、核心思路

**一句话：在启动脚本里（主程序启动之前），用 git 检查远程差异 → 询问用户 → git pull 更新 → 正常启动。**

```
start.bat / start.command / linux_start_prod.sh
  │
  ▼
[阶段 1] 检查更新（Python 脚本，无独立进程）
  1. 找 git 二进制
  2. 检查 .git 目录 → 没有则自动初始化
  3. git fetch origin {branch}
  4. 检查 HEAD 与 origin 是否有差异
  5. 有差异 → 显示简要信息，问用户是否更新
  6. 用户确认 → git stash → git pull --ff-only → git stash pop（冲突则丢弃）
  7. 无差异/跳过/失败 → 继续
  │
  ▼
[阶段 2] 原有启动流程（不变）
  检查 uv → 检查 config → 检查 MySQL → uv run start_windows.py
```

**为什么不需要 Updater 独立进程？**
- git 操作在 Python 主程序启动**之前**执行
- 此时没有进程持有 `.py` 文件锁，git pull 可以正常覆盖
- 不需要"进程替换自己"的复杂处理

---

## 三、启动流程修改

### 3.1 start.bat（Windows）

```batch
@echo off
chcp 65001 > nul

:: === 新增：启动前检查更新 ===
echo [INFO] 检查更新...
"%PYTHON%" scripts\upgrade_check.py
if errorlevel 2 (
    echo [ERROR] 更新检查遇到严重错误
    pause
    exit /b 1
)
:: ============================

:: 原有逻辑继续...
echo [INFO] 检查 uv 环境...
:: ... 其余不变
```

### 3.2 start.command（macOS）

```bash
#!/bin/bash

# === 新增：启动前检查更新 ===
echo "[INFO] 检查更新..."
"$PYTHON" scripts/upgrade_check.py
if [ $? -eq 2 ]; then
    echo "[ERROR] 更新检查遇到严重错误"
    read -p "按回车键继续..."
    exit 1
fi
# ============================

# 原有逻辑继续...
echo "[INFO] 检查 uv 环境..."
```

### 3.3 linux_start_prod.sh（Linux）

```bash
#!/bin/bash

# === 新增：启动前检查更新 ===
echo "[INFO] 检查更新..."
python3 scripts/upgrade_check.py
if [ $? -eq 2 ]; then
    echo "[ERROR] 更新检查遇到严重错误"
    exit 1
fi
# ============================

# 原有逻辑继续...
export comfyui_env=prod
python3 scripts/running/run_prod.py
```

---

## 四、新增脚本：`scripts/upgrade_check.py`

### 4.1 完整逻辑

```python
#!/usr/bin/env python3
"""
启动前检查更新脚本
由 start.bat / start.command / linux_start_prod.sh 在主程序启动前调用

返回值：
  0 - 正常（已更新 / 无需更新 / 跳过），继续启动
  1 - 更新失败但可继续，使用本地版本
  2 - 严重错误，应暂停并提示用户
"""

import os
import subprocess
import sys
from pathlib import Path


def find_git_binary():
    """查找 git 二进制"""
    # 1. 先检查项目自带的 git
    project_dir = Path(__file__).parent.parent.resolve()
    bundled_paths = [
        project_dir / "bin" / "git" / "git.exe",       # Windows
        project_dir / "bin" / "git" / "bin" / "git",   # macOS/Linux
    ]
    for p in bundled_paths:
        if p.exists():
            return str(p)

    # 2. 系统 PATH 中找
    for cmd in ["git", "git.exe"]:
        if shutil.which(cmd):
            return shutil.which(cmd)

    return None


def get_config(key, default=None):
    """读取配置（复用 config_util.py，或简单解析 YAML）"""
    # 实际实现时调用 config/config_util.py 的 get_config
    # 这里简化示意
    configs = {
        "upgrade.branch": "main",
        "upgrade.auto_update": False,
        "upgrade.check_on_startup": True,
        "upgrade.repo_url": "https://github.com/owner/repo.git",
    }
    return configs.get(key, default)


def init_git_repo(project_dir, git_cmd, repo_url, branch):
    """首次启动：.git 不存在，自动初始化"""
    print("[upgrade] 首次运行，初始化 git 仓库...")
    try:
        subprocess.run([git_cmd, "init"], cwd=project_dir, check=True, capture_output=True)
        subprocess.run([git_cmd, "remote", "add", "origin", repo_url],
                      cwd=project_dir, check=True, capture_output=True)
        subprocess.run([git_cmd, "fetch", "origin", branch, "--depth", "1"],
                      cwd=project_dir, check=True, capture_output=True, timeout=60)
        subprocess.run([git_cmd, "reset", "--hard", f"origin/{branch}"],
                      cwd=project_dir, check=True, capture_output=True)
        # 注意：reset --hard 不会覆盖 PRESERVE_PATHS 中的文件（因为它们在 .gitignore 中）
        print("[upgrade] 初始化完成")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"[upgrade] 初始化失败: {e}")
        return False


def check_and_update():
    project_dir = Path(__file__).parent.parent.resolve()

    # 1. 找 git 二进制
    git_cmd = find_git_binary()
    if not git_cmd:
        print("[upgrade] 未找到 git，跳过更新检查")
        return 0

    # 2. 读配置
    branch = get_config("upgrade.branch", "main")
    auto_update = get_config("upgrade.auto_update", False)
    check_on_startup = get_config("upgrade.check_on_startup", True)
    repo_url = get_config("upgrade.repo_url", "")

    if not check_on_startup:
        print("[upgrade] 已关闭启动时检查")
        return 0

    # 3. 检查 .git 目录
    git_dir = project_dir / ".git"
    if not git_dir.exists():
        if not repo_url:
            print("[upgrade] 未配置仓库地址，跳过更新")
            return 0
        if not init_git_repo(project_dir, git_cmd, repo_url, branch):
            print("[upgrade] 初始化失败，跳过更新，使用本地版本")
            return 1
        # 初始化后当前版本已与 remote 一致，无需再 pull
        return 0

    # 4. fetch remote
    try:
        subprocess.run([git_cmd, "fetch", "origin", branch],
                      cwd=project_dir, timeout=30, check=True, capture_output=True)
    except subprocess.TimeoutExpired:
        print("[upgrade] 网络超时，跳过更新，使用本地版本")
        return 1
    except subprocess.CalledProcessError:
        print("[upgrade] 获取远程信息失败，跳过更新，使用本地版本")
        return 1

    # 5. 检查差异
    try:
        result = subprocess.run([git_cmd, "log", f"HEAD..origin/{branch}", "--oneline"],
                              cwd=project_dir, capture_output=True, text=True, check=False)
        if not result.stdout.strip():
            print("[upgrade] 已是最新版本")
            return 0
    except Exception:
        return 1

    commits = result.stdout.strip().split("\n")
    commit_count = len(commits)

    # 6. 显示更新信息
    print(f"[upgrade] 检测到 {commit_count} 个更新：")
    for c in commits[:5]:
        print(f"  {c}")
    if commit_count > 5:
        print(f"  ... 还有 {commit_count - 5} 个更新")

    # 7. 静默模式？
    if auto_update:
        print("[upgrade] 自动更新模式，开始更新...")
    else:
        # 询问用户（Windows 用 input，macOS/Linux 也可用）
        try:
            answer = input("是否更新并启动？(Y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        if answer not in ("", "y", "yes"):
            print("[upgrade] 跳过更新，使用本地版本")
            return 0

    # 8. 执行更新
    # 8.1 暂存用户本地修改（防止冲突）
    stashed = False
    try:
        subprocess.run([git_cmd, "stash", "push", "--include-untracked", "-m", "auto-upgrade-stash"],
                      cwd=project_dir, check=True, capture_output=True)
        stashed = True
        print("[upgrade] 本地修改已暂存")
    except subprocess.CalledProcessError:
        pass  # 可能没有本地修改，stash 失败没关系

    # 8.2 pull
    try:
        subprocess.run([git_cmd, "pull", "origin", branch, "--ff-only"],
                      cwd=project_dir, check=True, capture_output=True)
        print("[upgrade] 更新成功")
    except subprocess.CalledProcessError as e:
        print(f"[upgrade] 更新失败: {e}")
        if stashed:
            subprocess.run([git_cmd, "stash", "pop"], cwd=project_dir, check=False)
        return 1

    # 8.3 恢复 stash
    if stashed:
        try:
            subprocess.run([git_cmd, "stash", "pop"], cwd=project_dir, check=True, capture_output=True)
            print("[upgrade] 本地修改已恢复")
        except subprocess.CalledProcessError:
            # pop 冲突，丢弃 stash
            subprocess.run([git_cmd, "stash", "drop"], cwd=project_dir, check=False)
            print("[upgrade] 警告: 本地修改与新版本冲突，已自动丢弃。如需保留请提前备份。")

    # 9. 检查 requirements.txt 变化
    try:
        diff_result = subprocess.run([git_cmd, "diff", "--name-only", "HEAD@{1}", "HEAD"],
                                    cwd=project_dir, capture_output=True, text=True)
        if "requirements.txt" in diff_result.stdout:
            print("[upgrade] 依赖有更新，启动时将自动安装")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(check_and_update())
```

### 4.2 关键设计点

| 设计点 | 处理 |
|--------|------|
| git 二进制 | 优先找项目自带 `bin/git/`，其次系统 PATH |
| .git 不存在 | 自动 `git init` + `remote add` + `fetch --depth 1` + `reset --hard origin/{branch}` |
| 网络不通 | timeout 30s，失败返回 1（跳过更新，继续启动） |
| 无差异 | 静默通过，返回 0 |
| 有差异 | 显示前 5 条 commit，问用户（input） |
| 用户拒绝 | 返回 0，正常启动本地版本 |
| 本地修改冲突 | `git stash` → `git pull` → `git stash pop` → pop 冲突则 `stash drop` |
| requirements.txt 变化 | 检测并提示，uv 启动时自动安装 |
| 数据库迁移 | git pull 后 Alembic 脚本更新，启动时 `run_prod.py` 自动执行 `alembic upgrade head` |

---

## 五、用户数据保护

git 不会触碰以下路径（已 `.gitignore`）：

```gitignore
# 当前 .gitignore 中已保护
data/
upload/
logs/
config_*.yml
*.local.json
enterprise/
scheduler.lock
```

升级后这些文件保持不变。

**如果用户改了 git 跟踪的文件（如 `web/`）：**
- 升级前自动 `git stash` 暂存
- 升级后尝试 `git stash pop` 恢复
- 如果冲突，丢弃 stash 并提示用户

---

## 六、配置项

`config/config.example.yml` 新增：

```yaml
upgrade:
  enabled: true              # 总开关
  repo_url: "https://github.com/owner/repo.git"  # 仓库地址
  branch: "main"             # 跟踪分支
  check_on_startup: true     # 启动时是否检查
  auto_update: false         # 静默自动更新（不询问）
  timeout_seconds: 30        # fetch 超时
```

`config/config_prod.base.yaml` 同样新增默认值。

---

## 七、文件改动清单

### 新增

| 文件 | 作用 |
|------|------|
| `scripts/upgrade_check.py` | 启动前检查更新（核心脚本） |

### 修改

| 文件 | 修改点 |
|------|--------|
| `start.bat` | uv 检查之前插入 `python scripts\upgrade_check.py` |
| `start.command` | 同上 |
| `scripts/running/linux_start_prod.sh` | 同上 |
| `config/config.example.yml` | 新增 `upgrade:` 段 |
| `config/config_prod.base.yaml` | 新增 `upgrade:` 默认值 |
| `config/constant.py` | 新增升级常量（可选，如 UPGRADE_TIMEOUT） |
| `scripts/package.py` | 可选：改为保留 `.git` 目录（见 7.1 节） |

### 复用的现有功能

| 现有模块 | 复用点 |
|---------|--------|
| `config/config_util.py` | 读取配置 |
| `run_prod.py` 中的 Alembic 迁移 | 数据库升级自动执行 |
| `start.bat` 中的 uv run | requirements.txt 变化后自动装依赖 |

---

## 八、关于 `.git` 目录的两种策略

### 策略 A：分发包不带 .git（推荐，保持现状）

- package.py 继续排除 `.git`
- 首次启动时 `upgrade_check.py` 自动 `git init` + `fetch`
- **优点**：ZIP 体积小
- **缺点**：首次启动需要网络（fetch），无网环境无法初始化

### 策略 B：分发包带 .git（shallow clone）

- package.py 改为保留 `.git`
- 打包前执行 `git gc --aggressive` 压缩
- 分支已跟踪 origin，用户拿到即用
- **优点**：首次启动就能检查更新，无需网络初始化
- **缺点**：ZIP 体积增加（.git 目录通常 5-20MB）

**建议：** 先用策略 A（不改动 package.py），后续根据用户反馈决定是否需要策略 B。

---

## 九、边界情况

| # | 场景 | 处理 |
|---|------|------|
| 1 | 找不到 git | 跳过检查，正常启动 |
| 2 | 没有 .git + 无网络 | 跳过检查，正常启动（策略 A） |
| 3 | fetch 超时 | 提示网络超时，跳过更新 |
| 4 | fetch 失败（仓库不存在/权限不足） | 提示失败，跳过更新 |
| 5 | 用户拒绝更新 | 正常启动本地版本 |
| 6 | git pull 失败（非 fast-forward） | 提示失败，stash pop 恢复，启动本地版 |
| 7 | stash pop 冲突 | 丢弃 stash，提示用户，继续启动 |
| 8 | 中文路径 | pathlib + utf-8，git 原生支持 |
| 9 | 升级后 requirements.txt 变了 | 提示"依赖更新"，uv 启动时自动安装 |
| 10 | 升级后 Alembic 迁移失败 | run_prod.py 抛错 → 启动失败 → 用户需手动回滚（`git reset --hard HEAD@{1}`） |
| 11 | 并发启动 | 无问题（顺序执行，无并发状态） |
| 12 | 用户改了被 git 跟踪的文件 | stash → pull → pop，冲突则丢弃 |
| 13 | 启动脚本升级 | start.bat 本身被 git 跟踪，升级后下次启动用新版脚本 |
| 14 | Windows 下 git 锁定 | 无问题（主程序未启动） |
| 15 | macOS ARM/Intel | git 命令一致，跨平台 |

---

## 十、与完整方案（auto_upgrade_design.md）的对比

| 维度 | 简化版（本文） | 完整版（auto_upgrade_design.md） |
|------|-------------|--------------------------------|
| **核心机制** | git pull | 独立 Updater + HTTP 下载 archive |
| **灰度发布** | ❌ 不支持 | ✅ manifest 控制 channel |
| **紧急撤回** | ❌ 不支持 | ✅ blacklisted 字段 |
| **断点续传** | ✅ git 自带 | ✅ 自实现 Range 下载 |
| **签名验证** | ❌ 不需要 | ✅ RSA 签名 manifest |
| **独立进程** | ❌ 不需要 | ✅ Updater 子进程 |
| **状态机** | ❌ 不需要 | ✅ 13 状态持久化 |
| **回滚** | 手动 git reset | ✅ 自动回滚 + DB downgrade |
| **代码量** | ~200 行 | ~3000+ 行 |
| **适用场景** | 快速上线、简单维护 | 大规模分发、需要精细控制 |

---

## 十一、发布流程（给维护者）

```bash
# 1. 开发完成 → 测试通过
# 2. 更新 pyproject.toml 版本号
# 3. commit + push
# 4. 完毕

# 不需要：
# - manifest.json
# - 签名
# - 上传 CDN
# - 计算 SHA256

# 用户下次启动时自动检测并提示更新
```

---

## 十二、测试计划

1. **无网络环境**：断网启动 → 应提示"网络不可用"→ 正常启动
2. **无 git**：删除 git 二进制 → 应提示"未找到 git"→ 正常启动
3. **无差异**：HEAD 与 origin 一致 → 静默通过
4. **有差异**：push 新 commit → 启动时应显示更新信息 → 确认后 pull
5. **用户拒绝**：显示差异 → 输入 n → 正常启动本地版
6. **本地修改冲突**：改一个被跟踪的文件 → stash → pull → pop 冲突 → 丢弃并提示
7. **requirements.txt 变化**：pull 后检测并提示依赖更新
8. **跨平台**：Win / macOS / Linux 分别测试
9. **中文路径**：用户目录含中文 → 正常执行
10. **首次启动无 .git**：策略 A，自动 init + fetch

---

## 十三、风险提示

1. **无灰度**：所有用户同时看到更新，push 前必须充分测试
2. **无撤回**：bug 版本 push 后无法阻止已 pull 的用户，只能通过再 push 修复
3. **Alembic 迁移失败**：git pull 后如果迁移脚本有 bug，启动会失败。用户需手动 `git reset --hard HEAD@{1}` 回退。建议大版本升级前在 changelog 中强提示备份
4. **用户本地修改丢失风险**：stash pop 冲突时会丢弃用户修改。应在 UI 中明确提示
