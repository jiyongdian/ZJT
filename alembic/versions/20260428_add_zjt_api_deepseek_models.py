"""Add zjt_api vendor association with deepseek-v4-flash/deepseek-v4-pro models with billing config

Revision ID: 20260428_zjt_api_deepseek
Revises: 20260427_add_deepseek
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260428_zjt_api_deepseek'
down_revision: Union[str, None] = '20260427_add_deepseek'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Associate deepseek-v4-flash and deepseek-v4-pro models with zjt_api vendor using same billing config"""
    conn = op.get_bind()

    # 1. deepseek-v4-flash 计费配置（关联到 zjt_api）
    # 输入1元/百万, 缓存命中0.02元/百万, 输出2元/百万
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 40000, 20000, 2000000, NULL
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'deepseek-v4-flash'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id
        )
    """))
    logger.info("[Migration] Added zjt_api + deepseek-v4-flash billing: input=40000, out=20000, cache=2000000, raw_threshold=NULL")

    # 2. deepseek-v4-pro 计费配置（关联到 zjt_api）
    # 输入12元/百万, 缓存命中0.1元/百万, 输出24元/百万
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 3333, 1667, 400000, NULL
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'deepseek-v4-pro'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id
        )
    """))
    logger.info("[Migration] Added zjt_api + deepseek-v4-pro billing: input=3333, out=1667, cache=400000, raw_threshold=NULL")


def downgrade() -> None:
    """Revert: Remove vendor_model records for deepseek models under zjt_api"""
    conn = op.get_bind()

    # 删除 zjt_api 供应商下 deepseek 模型的 vendor_model 关联（不删除 vendor 和 model）
    conn.execute(text("""
        DELETE FROM `vendor_model`
        WHERE vendor_id = (SELECT id FROM vendor WHERE vendor_name = 'zjt_api')
        AND model_id IN (
            SELECT id FROM `model`
            WHERE model_name IN ('deepseek-v4-flash', 'deepseek-v4-pro')
        )
    """))
    logger.info("[Migration] Deleted vendor_model records for deepseek models under zjt_api")
