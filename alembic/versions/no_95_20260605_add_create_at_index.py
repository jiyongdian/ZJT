"""Add index on create_at for implementation_attempts

为 implementation_attempts.create_at 添加独立索引，
优化按时间范围查询成功率统计的性能。

Revision ID: 20260605_create_at_idx
Revises: 20260605_impl_attempts
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260605_create_at_idx'
down_revision: Union[str, None] = '20260605_impl_attempts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(conn, table: str, index: str) -> bool:
    """Check if an index exists on a table"""
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND INDEX_NAME = :index"
    ), {"table": table, "index": index})
    return result.scalar() > 0


def upgrade() -> None:
    """Add idx_create_at index"""
    conn = op.get_bind()

    if _index_exists(conn, 'implementation_attempts', 'idx_create_at'):
        logger.info("Index idx_create_at already exists, skipping")
        return

    conn.execute(text(
        "ALTER TABLE `implementation_attempts` ADD INDEX `idx_create_at` (`create_at`)"
    ))
    logger.info("Added index idx_create_at on implementation_attempts.create_at")


def downgrade() -> None:
    """Drop idx_create_at index"""
    conn = op.get_bind()

    if _index_exists(conn, 'implementation_attempts', 'idx_create_at'):
        conn.execute(text(
            "ALTER TABLE `implementation_attempts` DROP INDEX `idx_create_at`"
        ))
        logger.info("Dropped index idx_create_at")
