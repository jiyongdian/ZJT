"""Add image_urls field to agent_tasks table

为 agent_tasks 表新增 image_urls 字段，存储 VL 图片 base64 数据（JSON 数组）。

Revision ID: 20260512_add_image_urls
Revises: 20260511_add_supports_vl
Create Date: 2026-05-12
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260512_add_image_urls'
down_revision: Union[str, None] = '20260511_add_supports_vl'
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
    """Add image_urls column to agent_tasks table"""
    conn = op.get_bind()

    if not _column_exists(conn, 'agent_tasks', 'image_urls'):
        conn.execute(text("""
            ALTER TABLE `agent_tasks`
            ADD COLUMN `image_urls` longtext COLLATE utf8mb4_unicode_ci DEFAULT NULL
            COMMENT '图片URL列表（JSON数组，支持base64）'
            AFTER `thinking_effort`
        """))
        logger.info("[Migration] Added image_urls column to agent_tasks table")
    else:
        logger.info("[Migration] Column image_urls already exists, skipped")


def downgrade() -> None:
    """Remove image_urls column from agent_tasks table"""
    conn = op.get_bind()

    if _column_exists(conn, 'agent_tasks', 'image_urls'):
        conn.execute(text("ALTER TABLE `agent_tasks` DROP COLUMN `image_urls`"))
        logger.info("[Migration] Removed image_urls column from agent_tasks table")
