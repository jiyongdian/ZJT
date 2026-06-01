"""Add video_urls and audio_urls fields to agent_tasks table

为 agent_tasks 表新增 video_urls 和 audio_urls 字段，用于存储视频和音频URL列表。
这些URL不传递给LLM，仅供后端视频生成使用。

Revision ID: 20260528_video_audio
Revises: 20260528_simplify_slots
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260528_video_audio'
down_revision: Union[str, None] = '20260528_simplify_slots'
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
    """Add video_urls and audio_urls columns to agent_tasks table"""
    conn = op.get_bind()

    if not _column_exists(conn, 'agent_tasks', 'video_urls'):
        conn.execute(text("""
            ALTER TABLE `agent_tasks`
            ADD COLUMN `video_urls` longtext COLLATE utf8mb4_unicode_ci DEFAULT NULL
            COMMENT '视频URL列表（JSON数组，不传递给LLM）'
            AFTER `image_urls`
        """))
        logger.info("[Migration] Added video_urls column to agent_tasks table")
    else:
        logger.info("[Migration] Column video_urls already exists, skipped")

    if not _column_exists(conn, 'agent_tasks', 'audio_urls'):
        conn.execute(text("""
            ALTER TABLE `agent_tasks`
            ADD COLUMN `audio_urls` longtext COLLATE utf8mb4_unicode_ci DEFAULT NULL
            COMMENT '音频URL列表（JSON数组，不传递给LLM）'
            AFTER `video_urls`
        """))
        logger.info("[Migration] Added audio_urls column to agent_tasks table")
    else:
        logger.info("[Migration] Column audio_urls already exists, skipped")


def downgrade() -> None:
    """Remove video_urls and audio_urls columns from agent_tasks table"""
    conn = op.get_bind()

    if _column_exists(conn, 'agent_tasks', 'audio_urls'):
        conn.execute(text("ALTER TABLE `agent_tasks` DROP COLUMN `audio_urls`"))
        logger.info("[Migration] Removed audio_urls column from agent_tasks table")

    if _column_exists(conn, 'agent_tasks', 'video_urls'):
        conn.execute(text("ALTER TABLE `agent_tasks` DROP COLUMN `video_urls`"))
        logger.info("[Migration] Removed video_urls column from agent_tasks table")