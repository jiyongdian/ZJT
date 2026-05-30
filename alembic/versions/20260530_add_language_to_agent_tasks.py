"""Add language field to agent_tasks table

为 agent_tasks 表新增 language 字段，用于存储用户界面语言设置。
使智能体对话语言与UI语言保持同步。

Revision ID: 20260530_language
Revises: 20260528_video_audio
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260530_language'
down_revision: Union[str, None] = '20260528_video_audio'
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
    """Add language column to agent_tasks table"""
    conn = op.get_bind()

    if not _column_exists(conn, 'agent_tasks', 'language'):
        conn.execute(text("""
            ALTER TABLE `agent_tasks`
            ADD COLUMN `language` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT 'zh-CN'
            COMMENT '用户界面语言设置（如 zh-CN, en）'
            AFTER `audio_urls`
        """))
        logger.info("[Migration] Added language column to agent_tasks table")
    else:
        logger.info("[Migration] Column language already exists, skipped")


def downgrade() -> None:
    """Remove language column from agent_tasks table"""
    conn = op.get_bind()

    if _column_exists(conn, 'agent_tasks', 'language'):
        conn.execute(text("ALTER TABLE `agent_tasks` DROP COLUMN `language`"))
        logger.info("[Migration] Removed language column from agent_tasks table")
