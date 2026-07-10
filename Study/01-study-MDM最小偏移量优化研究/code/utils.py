"""
Study/01 工具模块

功能：
- setup_path(): 将平台代码路径加入 sys.path
- get_git_info(): 获取 git commit hash + dirty 标记
- now_iso(): UTC 时间戳
"""

import os
import sys
import subprocess
from datetime import datetime, timezone


def setup_path():
    """将 D:\\weibull\\python 加入 sys.path，使脚本可以 import 平台模块。"""
    platform_path = r"D:\weibull\python"
    if platform_path not in sys.path:
        sys.path.insert(0, platform_path)


def get_git_info():
    """获取当前 git commit hash（短）+ dirty 标记。

    Returns:
        str: 如 "a1b2c3d"（clean）或 "a1b2c3d-dirty"（有未提交修改），失败返回 "unknown"
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=r"D:\weibull"
        )
        if result.returncode != 0:
            return "unknown"
        commit = result.stdout.strip()

        # Check for dirty working tree
        dirty_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
            cwd=r"D:\weibull"
        )
        if dirty_result.returncode == 0 and dirty_result.stdout.strip():
            commit += "-dirty"
        return commit
    except Exception:
        return "unknown"


def now_iso():
    """返回 UTC ISO8601 时间戳。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def now_local():
    """返回本地时间字符串（日志用）。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
