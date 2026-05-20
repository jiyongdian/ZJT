"""Add doubao models to zjt_api vendor with tiered billing

为 zjt_api 供应商新增 doubao-seed-2-0-pro 和 doubao-seed-2-0-lite 模型的分段计费配置，
计费率与 volcengine 供应商下的 doubao 模型完全一致。

Revision ID: 20260520_zjt_api_doubao
Revises: 20260519_shared_space
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260520_zjt_api_doubao'
down_revision: Union[str, None] = '20260519_shared_space'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 zjt_api 供应商添加 doubao-seed-2-0-pro/lite 分段计费配置"""
    conn = op.get_bind()

    # 1. doubao-seed-2-0-pro 三档分段计费（与 volcengine 一致）
    # 档位1: ≤32K — input=12500, out=2500, cache=62500, raw=32000
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 12500, 2500, 62500, 32000
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'doubao-seed-2-0-pro'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold = 32000
        )
    """))
    logger.info("[Migration] Added zjt_api doubao-seed-2-0-pro tier 1 (<=32K): input=12500, out=2500, cache=62500, raw=32000")

    # 档位2: 32K~128K — input=8333, out=1666, cache=41666, raw=128000
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 8333, 1666, 41666, 128000
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'doubao-seed-2-0-pro'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold = 128000
        )
    """))
    logger.info("[Migration] Added zjt_api doubao-seed-2-0-pro tier 2 (32K~128K): input=8333, out=1666, cache=41666, raw=128000")

    # 档位3: 128K~256K — input=4166, out=833, cache=20833, raw=256000
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 4166, 833, 20833, 256000
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'doubao-seed-2-0-pro'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold = 256000
        )
    """))
    logger.info("[Migration] Added zjt_api doubao-seed-2-0-pro tier 3 (128K~256K): input=4166, out=833, cache=20833, raw=256000")

    # 2. doubao-seed-2-0-lite 三档分段计费（与 volcengine 一致）
    # 档位1: ≤32K — input=66666, out=11111, cache=333333, raw=32000
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 66666, 11111, 333333, 32000
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'doubao-seed-2-0-lite'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold = 32000
        )
    """))
    logger.info("[Migration] Added zjt_api doubao-seed-2-0-lite tier 1 (<=32K): input=66666, out=11111, cache=333333, raw=32000")

    # 档位2: 32K~128K — input=44444, out=7407, cache=222222, raw=128000
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 44444, 7407, 222222, 128000
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'doubao-seed-2-0-lite'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold = 128000
        )
    """))
    logger.info("[Migration] Added zjt_api doubao-seed-2-0-lite tier 2 (32K~128K): input=44444, out=7407, cache=222222, raw=128000")

    # 档位3: 128K~256K — input=22222, out=3703, cache=111111, raw=256000
    conn.execute(text("""
        INSERT INTO `vendor_model` (vendor_id, model_id, created_at, input_token_threshold, out_token_threshold, cache_read_threshold, raw_token_threshold)
        SELECT v.id, m.id, NOW(), 22222, 3703, 111111, 256000
        FROM `vendor` v, `model` m
        WHERE v.vendor_name = 'zjt_api' AND m.model_name = 'doubao-seed-2-0-lite'
        AND NOT EXISTS (
            SELECT 1 FROM vendor_model vm
            WHERE vm.vendor_id = v.id AND vm.model_id = m.id AND vm.raw_token_threshold = 256000
        )
    """))
    logger.info("[Migration] Added zjt_api doubao-seed-2-0-lite tier 3 (128K~256K): input=22222, out=3703, cache=111111, raw=256000")


def downgrade() -> None:
    """回滚：删除 zjt_api 下 doubao 模型的 vendor_model 记录"""
    conn = op.get_bind()

    conn.execute(text("""
        DELETE FROM `vendor_model`
        WHERE vendor_id = (SELECT id FROM vendor WHERE vendor_name = 'zjt_api')
        AND model_id IN (
            SELECT id FROM `model`
            WHERE model_name IN ('doubao-seed-2-0-pro', 'doubao-seed-2-0-lite')
        )
    """))
    logger.info("[Migration] Deleted vendor_model records for doubao models under zjt_api")
