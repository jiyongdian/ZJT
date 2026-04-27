"""Add DeepSeek vendor and deepseek-v4-flash/deepseek-v4-pro models with billing config

Revision ID: 20260427_add_deepseek
Revises: 20260424_cleanup_qwen_stale
Create Date: 2026-04-27
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260427_add_deepseek'
down_revision: Union[str, None] = '20260424_cleanup_qwen_stale'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deepseek vendor, deepseek-v4-flash and deepseek-v4-pro models, and billing config"""
    conn = op.get_bind()

    # 1. 添加 deepseek 供应商
    conn.execute(text("""
        INSERT INTO vendor (vendor_name, created_at, note)
        VALUES ('deepseek', NOW(), 'DeepSeek 官方 API')
    """))
    logger.info("[Migration] Inserted deepseek vendor")

    # 2. 添加 deepseek-v4-flash 模型
    conn.execute(text("""
        INSERT INTO `model` (model_name, context_window, supports_tools, max_output_tokens, supports_thinking, created_at, note)
        VALUES ('deepseek-v4-flash', 1000000, 1, 384000, 1, NOW(), 'DeepSeek V4 Flash，支持思考模式')
    """))
    logger.info("[Migration] Inserted deepseek-v4-flash model")

    # 3. 添加 deepseek-v4-pro 模型
    conn.execute(text("""
        INSERT INTO `model` (model_name, context_window, supports_tools, max_output_tokens, supports_thinking, created_at, note)
        VALUES ('deepseek-v4-pro', 1000000, 1, 384000, 1, NOW(), 'DeepSeek V4 Pro，支持思考模式')
    """))
    logger.info("[Migration] Inserted deepseek-v4-pro model")

    # 4. deepseek-v4-flash 计费配置
    # 输入1元/百万, 缓存命中0.02元/百万, 输出2元/百万
    # threshold = 0.04 × 10^6 / 单价(元/百万token)
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 40000, 20000, 2000000, NULL
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'deepseek' AND m.model_name = 'deepseek-v4-flash'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id
        )
    """))
    logger.info("[Migration] Added deepseek-v4-flash billing: input=40000, out=20000, cache=2000000, raw_threshold=NULL")

    # 5. deepseek-v4-pro 计费配置
    # 输入12元/百万, 缓存命中0.1元/百万, 输出24元/百万
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 3333, 1667, 400000, NULL
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'deepseek' AND m.model_name = 'deepseek-v4-pro'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id
        )
    """))
    logger.info("[Migration] Added deepseek-v4-pro billing: input=3333, out=1667, cache=400000, raw_threshold=NULL")


def downgrade() -> None:
    """Revert: Remove vendor_model records, models, and vendor for DeepSeek"""
    conn = op.get_bind()

    # 1. 删除 vendor_model 关联
    conn.execute(text("""
        DELETE FROM `vendor_model`
        WHERE vendor_id = (SELECT id FROM vendor WHERE vendor_name = 'deepseek')
        AND model_id IN (
            SELECT id FROM `model`
            WHERE model_name IN ('deepseek-v4-flash', 'deepseek-v4-pro')
        )
    """))
    logger.info("[Migration] Deleted vendor_model records for deepseek models")

    # 2. 删除 model
    conn.execute(text("""
        DELETE FROM `model` WHERE model_name IN ('deepseek-v4-flash', 'deepseek-v4-pro')
    """))
    logger.info("[Migration] Deleted deepseek models")

    # 3. 删除 vendor
    conn.execute(text("""
        DELETE FROM vendor WHERE vendor_name = 'deepseek'
    """))
    logger.info("[Migration] Deleted deepseek vendor")
