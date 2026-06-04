"""Add gemini-3.5-flash model to jiekou vendor

新增 gemini-3.5-flash 模型，关联到 jiekou 供应商。
价格为 gemini-3-flash-preview 的 3 倍，对应 thresholds 为 gemini-3-flash-preview 的 1/3。

gemini-3-flash-preview thresholds: input=11000, output=1800, cache_read=112000
gemini-3.5-flash thresholds:       input=3667,  output=600,  cache_read=37333

Revision ID: 20260604_gemini35flash
Revises: 20260604_char_identity
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260604_gemini35flash'
down_revision: Union[str, None] = '20260604_char_identity'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 gemini-3.5-flash 模型并关联到 google 供应商"""
    conn = op.get_bind()

    # 1. 添加 gemini-3.5-flash 模型到 model 表
    conn.execute(text("""
        INSERT INTO `model` (model_name, context_window, supports_tools, max_output_tokens, supports_vl, created_at, note)
        VALUES ('gemini-3.5-flash', 1048576, 1, 64000, 0, NOW(), '')
    """))
    logger.info("[Migration] Inserted gemini-3.5-flash model")

    # 2. 关联到 google 供应商，设置计费阈值
    # 价格为 gemini-3-flash-preview 的 3 倍，thresholds 为 1/3
    # gemini-3-flash-preview: input=11000, output=1800, cache_read=112000
    # gemini-3.5-flash:       input=3667,  output=600,  cache_read=37333
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 3667, 600, 37333, NULL
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'google' AND m.model_name = 'gemini-3.5-flash'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold IS NULL
        )
    """))
    logger.info("[Migration] Added gemini-3.5-flash billing config: input=3667, output=600, cache_read=37333")


def downgrade() -> None:
    """回滚：删除 gemini-3.5-flash 的 vendor_model 记录和 model 记录"""
    conn = op.get_bind()

    # 1. 删除 vendor_model 关联
    conn.execute(text("""
        DELETE FROM `vendor_model`
        WHERE vendor_id = (SELECT id FROM vendor WHERE vendor_name = 'google')
        AND model_id = (SELECT id FROM `model` WHERE model_name = 'gemini-3.5-flash')
    """))
    logger.info("[Migration] Deleted vendor_model records for gemini-3.5-flash under google")

    # 2. 删除 model 记录
    conn.execute(text("""
        DELETE FROM `model` WHERE model_name = 'gemini-3.5-flash'
    """))
    logger.info("[Migration] Deleted gemini-3.5-flash model")
