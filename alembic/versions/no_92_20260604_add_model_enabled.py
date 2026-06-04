"""Add enabled field to model table

为 model 表新增 enabled 字段，支持在管理后台启用/禁用模型。
禁用的模型不会出现在前端模型选择器中。

Revision ID: 20260604_model_enabled
Revises: 20260604_gemini35flash
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260604_model_enabled'
down_revision: Union[str, None] = '20260604_gemini35flash'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table"""
    result = conn.execute(text(
        f"SELECT COUNT(*) FROM information_schema.COLUMNS "
        f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column"
    ), {"table": table, "column": column})
    return result.scalar() > 0


def upgrade() -> None:
    """为 model 表添加 enabled 字段"""
    conn = op.get_bind()

    if not _column_exists(conn, 'model', 'enabled'):
        conn.execute(text("""
            ALTER TABLE `model`
            ADD COLUMN `enabled` TINYINT(1) DEFAULT 1 COMMENT '是否启用(1=启用, 0=禁用)'
            AFTER `supports_vl`
        """))
        logger.info("[Migration] Added enabled column to model table")
    else:
        logger.info("[Migration] enabled column already exists, skipped")


def downgrade() -> None:
    """移除 model 表的 enabled 字段"""
    conn = op.get_bind()

    if _column_exists(conn, 'model', 'enabled'):
        conn.execute(text("ALTER TABLE `model` DROP COLUMN `enabled`"))
        logger.info("[Migration] Removed enabled column from model table")
    else:
        logger.info("[Migration] enabled column does not exist, skipped")
