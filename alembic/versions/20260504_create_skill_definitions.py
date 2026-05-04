"""创建 skill_definitions 表（用户级技能配置）

Revision ID: 20260504_skill_definitions
Revises: 20260504_merge_heads
Create Date: 2026-05-04

创建 skill_definitions 表，支持每个用户自定义 AI 专家的 prompt 内容。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260504_skill_definitions'
down_revision: Union[str, Sequence[str], None] = '20260504_merge_heads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 skill_definitions 表"""
    op.execute("""
        CREATE TABLE IF NOT EXISTS `skill_definitions` (
            `id` INT NOT NULL AUTO_INCREMENT,
            `user_id` INT DEFAULT NULL COMMENT '用户ID，NULL=系统默认',
            `skill_name` VARCHAR(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '技能名称，如 script-orchestrator',
            `display_name` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '显示名称，如 剧本架构师',
            `description` VARCHAR(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '技能描述',
            `prompt_content` LONGTEXT COLLATE utf8mb4_unicode_ci COMMENT '用户自定义的 prompt 内容（Markdown）',
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_user_skill` (`user_id`, `skill_name`),
            KEY `idx_skill_name` (`skill_name`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='技能定义表（用户级）'
    """)
    logger.info("[Migration] Created skill_definitions table")


def downgrade() -> None:
    """回滚：删除 skill_definitions 表"""
    op.execute("DROP TABLE IF EXISTS `skill_definitions`")
    logger.info("[Migration] Dropped skill_definitions table")
