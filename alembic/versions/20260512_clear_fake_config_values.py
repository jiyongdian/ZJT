"""
清理 config_prod.yml 中虚假的填充值

将以下虚假填充值替换为空字符串，避免系统误判密钥已配置：
- runninghub.api_key: 9549532f3c3d435eXXXX
- duomi.token: 5q26ybqAXXXXX
- llm.google.api_key: sk_xxxxx
- llm.qwen.api_key: sk-f3694dd0XXXX
- llm.baidu.api_key: bce-v3/ALTAK-RW7XXXX
- volcengine.api_key: your_volcengine_api_key
- vidu.token: vda_xxxx

Revision ID: 20260512_clear_fake_cfg_vals
Revises: 20260509_opt_ai_tools_idx
Create Date: 2026-05-12
"""
import re
from pathlib import Path

from alembic import op


# revision identifiers, used by Alembic.
revision = '20260512_clear_fake_cfg_vals'
down_revision = '20260509_opt_ai_tools_idx'
branch_labels = None
depends_on = None


# 项目根目录下的 config_prod.yml（Path 跨平台兼容 Windows/Linux/macOS）
CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / 'config_prod.yml'

# 虚假填充值 -> 正确值的替换映射
# 正则兼容有引号（"vda_xxxx"）和无引号（vda_xxxx）两种 YAML 写法
REPLACEMENTS = [
    # runninghub.api_key 假值
    (r'api_key:\s*["\']?9549532f3c3d435eXXXX["\']?', 'api_key: ""'),
    # duomi.token 假值
    (r'token:\s*["\']?5q26ybqAXXXXX["\']?', 'token: ""'),
    # llm.google.api_key 假值
    (r'api_key:\s*["\']?sk_xxxxx["\']?', 'api_key: ""'),
    # llm.qwen.api_key 假值
    (r'api_key:\s*["\']?sk-f3694dd0XXXX["\']?', 'api_key: ""'),
    # llm.baidu.api_key 假值
    (r'api_key:\s*["\']?bce-v3/ALTAK-RW7XXXX["\']?', 'api_key: ""'),
    # volcengine.api_key 假值
    (r'api_key:\s*["\']?your_volcengine_api_key["\']?', 'api_key: ""'),
    # vidu.token 假值
    (r'token:\s*["\']?vda_xxxx["\']?', 'token: ""'),
]


def upgrade():
    if not CONFIG_FILE.exists():
        return

    # newline='' 保留原始行尾符（Windows \r\n / Linux \n），避免跨平台写入时破坏行尾
    with open(CONFIG_FILE, 'r', encoding='utf-8', newline='') as f:
        content = f.read()

    new_content = content
    for pattern, replacement in REPLACEMENTS:
        new_content = re.sub(pattern, replacement, new_content)

    if new_content != content:
        with open(CONFIG_FILE, 'w', encoding='utf-8', newline='') as f:
            f.write(new_content)


def downgrade():
    # 清理假值是不可逆的操作，downgrade 不恢复假值
    pass
