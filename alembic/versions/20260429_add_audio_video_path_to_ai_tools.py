"""add_audio_video_path_to_ai_tools

Revision ID: 20260429_audio_video_path
Revises: 20260428_zjt_api_gpt55
Create Date: 2026-04-29

为 ai_tools 表添加 audio_path 和 video_path 字段，用于存储参考音频和参考视频路径
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260429_audio_video_path'
down_revision: Union[str, None] = '20260428_zjt_api_gpt55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库：为 ai_tools 表添加 audio_path 和 video_path 字段"""

    # 添加 audio_path 字段
    op.execute("""
        ALTER TABLE `ai_tools`
        ADD COLUMN `audio_path` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT '参考音频路径'
    """)

    # 添加 video_path 字段
    op.execute("""
        ALTER TABLE `ai_tools`
        ADD COLUMN `video_path` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT '参考视频路径'
    """)


def downgrade() -> None:
    """回滚数据库：删除 audio_path 和 video_path 字段"""

    op.execute("ALTER TABLE `ai_tools` DROP COLUMN `audio_path`")
    op.execute("ALTER TABLE `ai_tools` DROP COLUMN `video_path`")
