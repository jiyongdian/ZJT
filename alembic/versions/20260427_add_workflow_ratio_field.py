"""add_workflow_ratio_field

Revision ID: 20260427_workflow_ratio
Revises: 20260424_cleanup_qwen_stale_single_tier_billing
Create Date: 2026-04-27 12:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260427_workflow_ratio'
down_revision: Union[str, None] = '20260424_cleanup_qwen_stale'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库：为 video_workflow 表添加 workflow_ratio 字段"""

    # 为 video_workflow 表添加 workflow_ratio 字段
    op.execute("""
        ALTER TABLE `video_workflow`
        ADD COLUMN `workflow_ratio` VARCHAR(10) DEFAULT NULL COMMENT '工作流宽高比: 16:9 (横屏) | 9:16 (竖屏)'
        AFTER `style_reference_image`
    """)


def downgrade() -> None:
    """回滚数据库：删除 workflow_ratio 字段"""

    # 删除字段
    op.execute("ALTER TABLE `video_workflow` DROP COLUMN `workflow_ratio`")
