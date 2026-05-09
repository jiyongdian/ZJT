"""创建 notifications 通知表

Revision ID: 20260508_create_notifications
Revises: 20260504_skill_definitions
Create Date: 2026-05-08

存储从远程服务器拉取的通知消息（版本更新、系统公告等）。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260508_create_notifications'
down_revision: Union[str, Sequence[str], None] = '20260504_skill_definitions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 notifications 表"""
    op.execute("""
        CREATE TABLE IF NOT EXISTS `notifications` (
            `id` int NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
            `remote_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Remote notification ID (for dedup)',
            `notification_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'announcement' COMMENT 'Type: announcement/maintenance/feature/security',
            `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Notification title',
            `content` text COLLATE utf8mb4_unicode_ci COMMENT 'Notification content',
            `level` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'info' COMMENT 'Level: info/warning/error/success',
            `extra_data` text COLLATE utf8mb4_unicode_ci COMMENT 'Extra data JSON (link, link_text, etc)',
            `is_read` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Whether read by admin',
            `start_time` datetime DEFAULT NULL COMMENT 'Effective start time',
            `end_time` datetime DEFAULT NULL COMMENT 'Expiration time',
            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
            `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Update time',
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_remote_id` (`remote_id`),
            KEY `idx_is_read` (`is_read`),
            KEY `idx_created_at` (`created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Remote server notifications'
    """)
    logger.info("[Migration] Created notifications table")


def downgrade() -> None:
    """回滚：删除 notifications 表"""
    op.execute("DROP TABLE IF EXISTS `notifications`")
    logger.info("[Migration] Dropped notifications table")
