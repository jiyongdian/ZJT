"""
清理 config_prod.yml 中虚假的填充值

将 runninghub.api_key 的假值 "9549532f3c3d435eXXXX" 和 duomi.token 的假值 "5q26ybqAXXXXX"
替换为空字符串，避免系统误判密钥已配置。

Revision ID: 20260512_clear_fake_cfg_vals
Revises: 20260509_opt_ai_tools_idx
Create Date: 2026-05-12
"""
import os
import re

from alembic import op


# revision identifiers, used by Alembic.
revision = '20260512_clear_fake_cfg_vals'
down_revision = '20260509_opt_ai_tools_idx'
branch_labels = None
depends_on = None


# 项目根目录下的 config_prod.yml
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'config_prod.yml'
)

# 虚假填充值 -> 正确值的替换映射
REPLACEMENTS = [
    # runninghub.api_key 假值
    (r'api_key:\s*["\']9549532f3c3d435eXXXX["\']', 'api_key: ""'),
    # duomi.token 假值
    (r'token:\s*["\']5q26ybqAXXXXX["\']', 'token: ""'),
]


def upgrade():
    if not os.path.exists(CONFIG_FILE):
        return

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    for pattern, replacement in REPLACEMENTS:
        new_content = re.sub(pattern, replacement, new_content)

    if new_content != content:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)


def downgrade():
    # 清理假值是不可逆的操作，downgrade 不恢复假值
    pass
