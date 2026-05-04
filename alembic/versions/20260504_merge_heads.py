"""merge_heads: 合并 agent_verifications 与 audio_video_path 两个分支

Revision ID: 20260504_merge_heads
Revises: 20260427_agent_verifications, 20260429_audio_video_path
Create Date: 2026-05-04

合并以下两个 head 分支:
- 20260427_agent_verifications: 创建 agent_verifications 表
- 20260429_audio_video_path: 为 ai_tools 表添加 audio_path / video_path 字段

本迁移仅作分支合并使用，不涉及任何 schema 或数据变更。
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '20260504_merge_heads'
down_revision: Union[str, Sequence[str], None] = (
    '20260427_agent_verifications',
    '20260429_audio_video_path',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """合并迁移：无 schema 变更"""
    pass


def downgrade() -> None:
    """合并迁移：无回滚操作"""
    pass
