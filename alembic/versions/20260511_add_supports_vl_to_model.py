"""Add supports_vl field to model table

为 model 表新增 supports_vl 字段，标记模型是否支持视觉语言（Vision-Language）。

Revision ID: 20260511_add_supports_vl
Revises: 20260511_add_session_type
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260511_add_supports_vl'
down_revision: Union[str, None] = '20260511_add_session_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add supports_vl column and update existing VL models"""
    # 1. 添加字段
    op.add_column('model', sa.Column(
        'supports_vl',
        sa.Boolean(),
        nullable=False,
        server_default=sa.text('0'),
        comment='是否支持视觉语言（Vision-Language）'
    ))
    logger.info("[Migration] Added supports_vl column to model table")

    # 2. 批量更新已知支持 VL 的模型
    vl_models = [
        'gemini-3-flash-preview',
        'gemini-3.1-pro-preview',
        'gemini-3.1-flash-lite-preview',
        'qwen3.6-plus',
        'doubao-seed-2-0-pro',
        'doubao-seed-2-0-lite',
        'claude-haiku-4-5',
        'qwen3.6:35b-a3b',
        'gpt-5.5'
    ]
    for model_name in vl_models:
        # 使用转义的单引号确保 SQL 正确
        escaped_name = model_name.replace("'", "\\'")
        op.execute(sa.text(
            f"UPDATE `model` SET supports_vl = 1 WHERE model_name = '{escaped_name}'"
        ))
    logger.info("[Migration] Updated VL models to support vision-language")


def downgrade() -> None:
    """Remove supports_vl column"""
    op.drop_column('model', 'supports_vl')
    logger.info("[Migration] Removed supports_vl column from model table")
