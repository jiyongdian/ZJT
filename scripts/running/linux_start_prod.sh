#!/bin/bash
export comfyui_env=prod

# === 启动前检查更新 ===
echo "[upgrade] Checking for updates..."
python3 scripts/upgrade_check.py
UPGRADE_RC=$?
if [ $UPGRADE_RC -eq 2 ]; then
    echo "[ERROR] 更新检查遇到严重错误"
    exit 1
elif [ $UPGRADE_RC -eq 1 ]; then
    echo "[WARN] 更新检查失败，继续使用本地版本"
fi
# ======================

# 使用统一启动器管理 scheduler 和 gunicorn
python3 run_prod.py
