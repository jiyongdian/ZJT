"""Fix site_number NULL in implementation_power_config for site-based implementations

修复 implementation_power_config 表中基于站点的实现方 site_number 为 NULL 的问题。
这些记录是通过 set_power()/set_config() 方法创建的，INSERT 时未传入 site_number。

通过 UnifiedConfigRegistry 动态获取 site_number，而非硬编码映射。

Revision ID: 20260513_fix_site_number
Revises: 20260512_add_image_urls
Create Date: 2026-05-13
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260513_fix_site_number'
down_revision: Union[str, None] = '20260512_add_image_urls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """修复 site_number 为 NULL 的站点实现方记录"""
    # 初始化统一配置（确保 UnifiedConfigRegistry 可用）
    from config.unified_config import init_unified_config, UnifiedConfigRegistry
    init_unified_config()

    conn = op.get_bind()
    fixed_count = 0

    # 从配置注册表动态获取所有实现方，筛选有 site_number 的
    for impl_name, impl_config in UnifiedConfigRegistry.get_all_implementations().items():
        site_number = impl_config.site_number
        if site_number is None:
            continue

        # 查找该实现方中 site_number 为 NULL 的记录
        result = conn.execute(text("""
            SELECT id, driver_key FROM implementation_power_config
            WHERE implementation_name = :impl_name AND site_number IS NULL
        """), {'impl_name': impl_name})

        rows = result.fetchall()
        if rows:
            conn.execute(text("""
                UPDATE implementation_power_config
                SET site_number = :site_number
                WHERE implementation_name = :impl_name AND site_number IS NULL
            """), {'site_number': site_number, 'impl_name': impl_name})

            for row in rows:
                logger.info(f"Fixed site_number: {impl_name} (id={row[0]}, driver_key={row[1]}) -> site_number={site_number}")
            fixed_count += len(rows)

    logger.info(f"Total fixed {fixed_count} records with NULL site_number")


def downgrade() -> None:
    """回滚：将修复的记录的 site_number 恢复为 NULL"""
    from config.unified_config import init_unified_config, UnifiedConfigRegistry
    init_unified_config()

    conn = op.get_bind()

    for impl_name, impl_config in UnifiedConfigRegistry.get_all_implementations().items():
        if impl_config.site_number is None:
            continue

        conn.execute(text("""
            UPDATE implementation_power_config
            SET site_number = NULL
            WHERE implementation_name = :impl_name
        """), {'impl_name': impl_name})

    logger.info("Reverted site_number to NULL for all site-based implementations")
