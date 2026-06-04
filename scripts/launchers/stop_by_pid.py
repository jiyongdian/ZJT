"""
通过 PID 文件停止进程
只停止记录在 PID 文件中的进程，避免误杀其他进程

处理的极端情况：
1. PID 残留：只停止实际运行的进程
2. PID 重用：通过进程名 + 目录验证避免误杀
3. 文件损坏：自动处理损坏的文件
4. 多项目隔离：只停止属于当前项目的进程，避免误杀其他项目的进程
"""
import os
import sys
import subprocess

# 导入 PID 管理模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pid_manager import (
    get_pid_entries,
    clear_pids,
    is_process_running
)


def get_project_dir():
    """
    获取当前项目根目录
    stop_by_pid.py 位于 scripts/launchers/ 下，向上两级到项目根目录
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def kill_process(pid, process_name=None):
    """
    停止进程（包括子进程）

    Args:
        pid: 进程 ID
        process_name: 进程名（用于验证）

    Returns:
        tuple: (是否成功, 消息)
    """
    try:
        result = subprocess.run(
            ['taskkill', '/F', '/T', '/PID', str(pid)],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='gbk',
            errors='ignore'
        )
        return result.returncode == 0
    except Exception:
        return False


def main():
    """主函数"""
    project_dir = get_project_dir()

    # 只获取属于当前项目的 PID 条目，避免误杀其他项目的进程
    entries = get_pid_entries(project_dir=project_dir)

    if not entries:
        return

    killed_count = 0
    failed_count = 0
    skipped_count = 0

    for entry in entries:
        pid = entry.get('pid')
        process_name = entry.get('name', 'unknown')
        cwd = entry.get('cwd', 'N/A')

        if not pid:
            continue

        # 先检查进程是否仍在运行（验证进程名 + 目录）
        if not is_process_running(pid, process_name, cwd):
            skipped_count += 1
            continue

        # 停止进程
        if kill_process(pid, process_name):
            killed_count += 1
        else:
            failed_count += 1

    # 只清除当前项目的 PID 记录，不影响其他项目
    clear_pids(project_dir=project_dir)


if __name__ == "__main__":
    main()
