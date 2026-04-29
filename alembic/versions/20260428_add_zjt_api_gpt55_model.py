"""Add zjt_api vendor association with gpt-5.5 model with tiered billing config

Revision ID: 20260428_zjt_api_gpt55
Revises: 20260428_zjt_api_deepseek
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260428_zjt_api_gpt55'
down_revision: Union[str, None] = '20260428_zjt_api_deepseek'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add gpt-5.5 model and associate with zjt_api vendor with tiered billing config

    计算公式: threshold = 0.04 × 10^6 / 单价(元/百万token), 1美元=7人民币

    Tier 1 (raw_input_token <= 272000):
      输入 $5/百万 = ¥35/百万  → input_threshold  = 1143
      缓存 $0.5/百万 = ¥3.5/百万 → cache_threshold = 11429
      输出 $30/百万 = ¥210/百万 → output_threshold = 190

    Tier 2 (272000 < raw_input_token <= 1050000, 上下文上限):
      输入 $10/百万 = ¥70/百万  → input_threshold  = 571
      缓存 $1/百万 = ¥7/百万   → cache_threshold = 5714
      输出 $45/百万 = ¥315/百万 → output_threshold = 127
    """
    conn = op.get_bind()

    # 1. 添加 gpt-5.5 模型
    conn.execute(text("""
        INSERT INTO `model` (model_name, context_window, supports_tools, max_output_tokens, supports_thinking, created_at, note)
        VALUES ('gpt-5.5', 1050000, 1, 128000, 1, NOW(), 'GPT-5.5，支持函数调用/结构化输出/推理')
    """))
    logger.info("[Migration] Inserted gpt-5.5 model")

    # 2. gpt-5.5 分段计费配置（关联到 zjt_api）
    # 分段1: raw_token_threshold=272000
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 1143, 190, 11429, 272000
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'gpt-5.5'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold = 272000
        )
    """))
    logger.info("[Migration] Added zjt_api + gpt-5.5 billing tier 1: input=1143, out=190, cache=11429, raw_threshold=272000")

    # 分段2: raw_token_threshold=1050000
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 571, 127, 5714, 1050000
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'gpt-5.5'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold = 1050000
        )
    """))
    logger.info("[Migration] Added zjt_api + gpt-5.5 billing tier 2: input=571, out=127, cache=5714, raw_threshold=1050000")


def downgrade() -> None:
    """Revert: Remove vendor_model records for gpt-5.5 under zjt_api, and remove gpt-5.5 model"""
    conn = op.get_bind()

    # 1. 删除 vendor_model 关联
    conn.execute(text("""
        DELETE FROM `vendor_model`
        WHERE vendor_id = (SELECT id FROM vendor WHERE vendor_name = 'zjt_api')
        AND model_id = (SELECT id FROM `model` WHERE model_name = 'gpt-5.5')
    """))
    logger.info("[Migration] Deleted vendor_model records for gpt-5.5 under zjt_api")

    # 2. 删除 model
    conn.execute(text("""
        DELETE FROM `model` WHERE model_name = 'gpt-5.5'
    """))
    logger.info("[Migration] Deleted gpt-5.5 model")
