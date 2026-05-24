"""Reduce deepseek-v4-pro billing rates to 1/4 of original price

将 deepseek-v4-pro 模型在 deepseek 和 zjt_api 两个供应商下的计费 threshold 更新为新值：
- 原单价：输入12元/百万, 输出24元/百万, 缓存0.1元/百万
- 新单价：输入3元/百万, 输出6元/百万, 缓存0.025元/百万
- 公式：threshold = 0.04 × 10^6 / 单价(元/百万token)

Revision ID: 20260524_ds_v4_pro_cut
Revises: 20260520_zjt_api_doubao
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260524_ds_v4_pro_cut'
down_revision: Union[str, None] = '20260522_media_label'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 新计费阈值（单价降为原来的 1/4 → threshold × 4）
# 输入: 0.04×10^6/3 = 13333
# 输出: 0.04×10^6/6 = 6667
# 缓存: 0.04×10^6/0.025 = 1600000
NEW_INPUT = 13333
NEW_OUTPUT = 6667
NEW_CACHE = 1600000

# 旧计费阈值（用于 downgrade）
OLD_INPUT = 3333
OLD_OUTPUT = 1667
OLD_CACHE = 400000

VENDORS = ['deepseek', 'zjt_api']


def upgrade() -> None:
    """Update deepseek-v4-pro billing thresholds for deepseek and zjt_api vendors"""
    conn = op.get_bind()

    for vendor_name in VENDORS:
        conn.execute(text("""
            UPDATE `vendor_model` vm
            JOIN `vendor` v ON vm.vendor_id = v.id
            JOIN `model` m ON vm.model_id = m.id
            SET vm.input_token_threshold = :input_val,
                vm.out_token_threshold = :output_val,
                vm.cache_read_threshold = :cache_val
            WHERE v.vendor_name = :vendor
              AND m.model_name = 'deepseek-v4-pro'
        """), {
            'input_val': NEW_INPUT,
            'output_val': NEW_OUTPUT,
            'cache_val': NEW_CACHE,
            'vendor': vendor_name,
        })
        logger.info(
            f"[Migration] Updated {vendor_name}/deepseek-v4-pro billing: "
            f"input={NEW_INPUT}, output={NEW_OUTPUT}, cache={NEW_CACHE}"
        )


def downgrade() -> None:
    """Restore original deepseek-v4-pro billing thresholds"""
    conn = op.get_bind()

    for vendor_name in VENDORS:
        conn.execute(text("""
            UPDATE `vendor_model` vm
            JOIN `vendor` v ON vm.vendor_id = v.id
            JOIN `model` m ON vm.model_id = m.id
            SET vm.input_token_threshold = :input_val,
                vm.out_token_threshold = :output_val,
                vm.cache_read_threshold = :cache_val
            WHERE v.vendor_name = :vendor
              AND m.model_name = 'deepseek-v4-pro'
        """), {
            'input_val': OLD_INPUT,
            'output_val': OLD_OUTPUT,
            'cache_val': OLD_CACHE,
            'vendor': vendor_name,
        })
        logger.info(
            f"[Migration] Restored {vendor_name}/deepseek-v4-pro billing: "
            f"input={OLD_INPUT}, output={OLD_OUTPUT}, cache={OLD_CACHE}"
        )
