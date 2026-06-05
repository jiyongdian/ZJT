"""Add implementation_attempts table

新建 implementation_attempts 表，记录每次实现方尝试的成功/失败，
用于准确统计各实现方的成功率和平均耗时。

Revision ID: 20260605_impl_attempts
Revises: 20260604_image_retry
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260605_impl_attempts'
down_revision: Union[str, None] = '20260604_image_retry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table: str) -> bool:
    """Check if a table exists"""
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
    ), {"table": table})
    return result.scalar() > 0


def upgrade() -> None:
    """Create implementation_attempts table"""
    conn = op.get_bind()

    if _table_exists(conn, 'implementation_attempts'):
        logger.info("Table implementation_attempts already exists, skipping")
        return

    conn.execute(text("""
        CREATE TABLE `implementation_attempts` (
          `id` int NOT NULL AUTO_INCREMENT,
          `ai_tool_id` int NOT NULL COMMENT '关联 ai_tools.id',
          `implementation` int NOT NULL COMMENT '尝试的实现方 ID',
          `attempt_number` tinyint NOT NULL DEFAULT 1 COMMENT '第几次尝试 (1=首次)',
          `status` tinyint NOT NULL COMMENT '2=成功, -1=失败',
          `error_message` text DEFAULT NULL COMMENT '失败原因',
          `started_at` datetime DEFAULT NULL COMMENT '开始时间',
          `completed_at` datetime DEFAULT NULL COMMENT '完成时间',
          `create_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`),
          KEY `idx_ai_tool_id` (`ai_tool_id`),
          KEY `idx_impl_status_created` (`implementation`, `status`, `create_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实现方尝试记录'
    """))
    logger.info("Created table implementation_attempts")


def downgrade() -> None:
    """Drop implementation_attempts table"""
    conn = op.get_bind()

    if _table_exists(conn, 'implementation_attempts'):
        conn.execute(text("DROP TABLE `implementation_attempts`"))
        logger.info("Dropped table implementation_attempts")
