#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动前检查更新脚本
由 start.bat / start.command / linux_start_prod.sh 在主程序启动前调用

通过监控远程 git tag 变化判断是否需要升级。
升级时执行 git stash -> git pull --ff-only -> git stash pop。

返回值：
  0 - 正常（已更新 / 无需更新 / 跳过），继续启动
  1 - 更新失败但可继续，使用本地版本
  2 - 严重错误，应暂停并提示用户
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_project_dir() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent.resolve()


def find_git_binary():
    """查找 git 二进制

    优先查找项目自带的 git，其次在系统 PATH 中查找。
    """
    project_dir = get_project_dir()

    # 1. 检查项目自带的 git
    bundled_paths = [
        project_dir / "bin" / "git" / "git.exe",       # Windows
        project_dir / "bin" / "git" / "bin" / "git",   # macOS/Linux
    ]
    for p in bundled_paths:
        if p.exists():
            return str(p)

    # 2. 系统 PATH 中找
    git_cmd = shutil.which("git")
    if git_cmd:
        return git_cmd

    return None


def get_upgrade_config():
    """读取升级相关配置

    优先使用 config_util 读取配置（如果可用）。
    如果 import 失败（如 Python 环境未就绪），回退到直接解析 YAML。
    """
    defaults = {
        "enabled": True,
        "repo_url": "",
        "branch": "main",
        "check_on_startup": True,
        "auto_update": False,
        "timeout_seconds": 30,
    }

    try:
        from config.config_util import get_config_value
        result = {}
        for key in defaults:
            result[key] = get_config_value("upgrade", key, default=defaults[key])
        return result
    except Exception:
        return _read_config_from_yaml(defaults)


def _read_config_from_yaml(defaults):
    """直接解析配置文件读取 upgrade 配置（回退方案）"""
    project_dir = get_project_dir()
    env = os.environ.get("comfyui_env", "dev")
    config_file = project_dir / f"config_{env}.yml"

    if not config_file.exists():
        base_file = project_dir / f"config_{env}.base.yaml"
        if base_file.exists():
            config_file = base_file
        else:
            return defaults

    try:
        import yaml
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        upgrade = config.get("upgrade", {})
        result = {}
        for key in defaults:
            result[key] = upgrade.get(key, defaults[key])
        return result
    except Exception:
        return defaults


def parse_version(v):
    """解析版本号为可比较的数字列表

    支持格式: "1.5.1", "v1.5.1", "1.5.1-beta"
    返回: [1, 5, 1]
    """
    v = v.lstrip("vV")
    num_part = v.split("-")[0]
    result = []
    for p in num_part.split("."):
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    return result


def compare_version(v1, v2):
    """比较两个版本号

    返回:
        1  if v1 > v2
        -1 if v1 < v2
        0  if v1 == v2
    """
    p1, p2 = parse_version(v1), parse_version(v2)
    for a, b in zip(p1, p2):
        if a != b:
            return 1 if a > b else -1
    return len(p1) - len(p2)


def get_local_version(project_dir):
    """读取本地 pyproject.toml 版本号"""
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("version"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return "unknown"


def run_git(git_cmd, args, cwd, timeout=30, capture=True):
    """运行 git 命令

    返回 (returncode, stdout, stderr)
    """
    cmd = [git_cmd] + args
    try:
        if capture:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, cwd=str(cwd), timeout=timeout)
            return result.returncode, "", ""
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def get_remote_latest_tag(git_cmd, project_dir, timeout):
    """获取远程最新的 tag 版本号

    使用 git ls-remote 获取远程所有 tag，本地排序找出最新的。
    过滤掉 peeled refs (^{}) 和非版本格式的 tag。
    """
    rc, out, _ = run_git(
        git_cmd, ["ls-remote", "--tags", "origin"],
        project_dir, timeout=timeout
    )
    if rc != 0 or not out.strip():
        return None

    tags = []
    for line in out.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if not ref.startswith("refs/tags/"):
            continue
        tag = ref.replace("refs/tags/", "")
        # 过滤 peeled refs
        if tag.endswith("^{}"):
            continue
        # 只保留类似 v1.5.1 或 1.5.1 的 tag（至少有一个点号）
        clean = tag.lstrip("vV").split("-")[0]
        if "." in clean:
            tags.append(tag)

    if not tags:
        return None

    tags.sort(key=parse_version, reverse=True)
    return tags[0]


def init_git_repo(project_dir, git_cmd, repo_url, branch, timeout):
    """首次启动：.git 不存在，自动初始化"""
    print("[upgrade] 首次运行，初始化 git 仓库...")

    rc, _, err = run_git(git_cmd, ["init"], project_dir, timeout=timeout)
    if rc != 0:
        print(f"[upgrade] git init 失败: {err}")
        return False

    rc, _, err = run_git(
        git_cmd, ["remote", "add", "origin", repo_url],
        project_dir, timeout=timeout
    )
    if rc != 0:
        print(f"[upgrade] 添加远程仓库失败: {err}")
        return False

    rc, _, err = run_git(
        git_cmd, ["fetch", "origin", branch, "--depth", "1", "--tags"],
        project_dir, timeout=timeout
    )
    if rc != 0:
        print(f"[upgrade] fetch 远程分支失败: {err}")
        return False

    rc, _, err = run_git(
        git_cmd, ["reset", "--hard", f"origin/{branch}"],
        project_dir, timeout=timeout
    )
    if rc != 0:
        print(f"[upgrade] 重置到远程版本失败: {err}")
        return False

    print("[upgrade] 初始化完成，已同步到最新版本")
    return True


def perform_update(git_cmd, project_dir, timeout):
    """执行更新（stash + pull + stash pop）

    返回 (success, message)
    """
    stashed = False
    rc, _, _ = run_git(
        git_cmd, ["stash", "push", "--include-untracked", "-m", "auto-upgrade-stash"],
        project_dir, timeout=timeout
    )
    if rc == 0:
        stashed = True
        print("[upgrade] 本地修改已暂存")

    rc, out, err = run_git(
        git_cmd, ["pull", "origin", "--ff-only"],
        project_dir, timeout=timeout
    )
    if rc != 0:
        msg = err or out or "未知错误"
        if stashed:
            run_git(git_cmd, ["stash", "pop"], project_dir, timeout=timeout)
        return False, f"pull 失败: {msg}"

    print("[upgrade] 代码更新成功")

    if stashed:
        rc, _, _ = run_git(
            git_cmd, ["stash", "pop"],
            project_dir, timeout=timeout
        )
        if rc == 0:
            print("[upgrade] 本地修改已恢复")
        else:
            run_git(git_cmd, ["stash", "drop"], project_dir, timeout=10)
            return True, "本地修改与新版冲突，已自动丢弃"

    return True, ""


def ask_user_yes_no(prompt, default=True):
    """询问用户 yes/no

    在非交互式环境（如 CI）下返回默认值。
    """
    if not sys.stdin.isatty():
        return default

    suffix = "(Y/n): " if default else "(y/N): "
    try:
        answer = input(f"{prompt} {suffix}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if answer == "":
        return default
    return answer in ("y", "yes")


def check_requirements_changed(git_cmd, project_dir, timeout):
    """检查 requirements.txt 是否有变化"""
    rc, out, _ = run_git(
        git_cmd, ["diff", "--name-only", "HEAD@{1}", "HEAD"],
        project_dir, timeout=timeout
    )
    if rc == 0 and out:
        if "requirements.txt" in out:
            print("[upgrade] 注意：依赖有更新，启动时将自动安装")


def main():
    """主入口"""
    project_dir = get_project_dir()

    cfg = get_upgrade_config()

    if not cfg.get("enabled", True):
        print("[upgrade] 已禁用")
        return 0

    if not cfg.get("check_on_startup", True):
        print("[upgrade] 已关闭启动时检查")
        return 0

    branch = cfg.get("branch", "main")
    timeout = cfg.get("timeout_seconds", 30)
    auto_update = cfg.get("auto_update", False)
    repo_url = cfg.get("repo_url", "").strip()

    git_cmd = find_git_binary()
    if not git_cmd:
        print("[upgrade] 未找到 git，跳过更新检查")
        return 0

    git_dir = project_dir / ".git"

    if not git_dir.exists():
        if not repo_url:
            print("[upgrade] 未配置仓库地址，跳过更新检查")
            print("[upgrade] 提示：如需自动更新，请在配置中设置 upgrade.repo_url")
            return 0

        if not init_git_repo(project_dir, git_cmd, repo_url, branch, timeout):
            print("[upgrade] 初始化失败，使用本地版本")
            return 1

        return 0

    # 1. 读取本地版本
    local_version = get_local_version(project_dir)
    print(f"[upgrade] 当前版本: {local_version}")

    # 2. fetch 远程（包含 tag）
    rc, _, err = run_git(
        git_cmd, ["fetch", "origin", branch, "--tags"],
        project_dir, timeout=timeout
    )
    if rc != 0:
        print(f"[upgrade] fetch 远程信息失败: {err}")
        return 1

    # 3. 获取远程最新 tag
    latest_tag = get_remote_latest_tag(git_cmd, project_dir, timeout)
    if not latest_tag:
        print("[upgrade] 远程无可用版本 tag，跳过更新检查")
        return 0

    print(f"[upgrade] 远程最新版本: {latest_tag}")

    # 4. 比较版本
    cmp = compare_version(latest_tag, local_version)
    if cmp <= 0:
        if cmp == 0:
            print("[upgrade] 已是最新版本")
        else:
            print(f"[upgrade] 本地版本 ({local_version}) 高于远程 ({latest_tag})，无需更新")
        return 0

    # 5. 提示更新
    print(f"[upgrade] 发现新版本: {local_version} -> {latest_tag}")

    if auto_update:
        print("[upgrade] 自动更新模式，开始更新...")
    else:
        if not ask_user_yes_no("是否更新并启动？"):
            print("[upgrade] 跳过更新，使用本地版本")
            return 0

    # 6. 执行更新
    success, message = perform_update(git_cmd, project_dir, timeout)
    if not success:
        print(f"[upgrade] 更新失败: {message}")
        return 1

    if message:
        print(f"[upgrade] 警告: {message}")

    # 7. 检查依赖变化
    check_requirements_changed(git_cmd, project_dir, timeout)

    print("[upgrade] 更新完成，继续启动...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
