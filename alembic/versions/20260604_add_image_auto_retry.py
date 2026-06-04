"""Add auto-retry fields to grid_image_tasks table

为 grid_image_tasks 表新增自动重试相关字段，支持图片生成失败后自动重新提交。
新增字段：prompt, task_config_id, aspect_ratio, image_size, is_grid, retry_count, max_retries

Revision ID: 20260604_image_retry
Revises: 20260603_email_support
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260604_image_retry'
down_revision: Union[str, None] = '20260603_email_support'
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
    """Add auto-retry columns to grid_image_tasks table"""
    conn = op.get_bind()

    columns_to_add = [
        ("prompt", "text COMMENT '生图提示词（用于自动重试）' AFTER `update_success`"),
        ("task_config_id", "varchar(100) DEFAULT NULL COMMENT '生图模型配置ID（用于自动重试）' AFTER `prompt`"),
        ("aspect_ratio", "varchar(20) DEFAULT NULL COMMENT '图片宽高比（用于自动重试）' AFTER `task_config_id`"),
        ("image_size", "varchar(20) DEFAULT NULL COMMENT '图片尺寸（用于自动重试）' AFTER `aspect_ratio`"),
        ("is_grid", "tinyint DEFAULT '0' COMMENT '是否为宫格生成 (0-否, 1-是)' AFTER `image_size`"),
        ("retry_count", "int DEFAULT '0' COMMENT '已重试次数' AFTER `is_grid`"),
        ("max_retries", "int DEFAULT '0' COMMENT '最大重试次数（0=不重试）' AFTER `retry_count`"),
    ]

    for col_name, col_def in columns_to_add:
        if not _column_exists(conn, 'grid_image_tasks', col_name):
            conn.execute(text(f"ALTER TABLE `grid_image_tasks` ADD COLUMN `{col_name}` {col_def}"))
            logger.info(f"[Migration] Added column `{col_name}` to grid_image_tasks table")
        else:
            logger.info(f"[Migration] Column `{col_name}` already exists, skipped")


def downgrade() -> None:
    """Remove auto-retry columns from grid_image_tasks table"""
    conn = op.get_bind()

    columns_to_remove = ["max_retries", "retry_count", "is_grid", "image_size", 
                         "aspect_ratio", "task_config_id", "prompt"]

    for col_name in columns_to_remove:
        if _column_exists(conn, 'grid_image_tasks', col_name):
            conn.execute(text(f"ALTER TABLE `grid_image_tasks` DROP COLUMN `{col_name}`"))
            logger.info(f"[Migration] Removed column `{col_name}` from grid_image_tasks table")
