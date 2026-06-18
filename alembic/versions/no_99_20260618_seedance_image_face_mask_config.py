"""Add Seedance image face mask pipeline config

Revision ID: 20260618_seed_img_mask
Revises: 20260616_withdraw_method
Create Date: 2026-06-18
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20260618_seed_img_mask'
down_revision: Union[str, None] = '20260616_withdraw_method'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 配置项通过 config/default_configs.py 中的 DEFAULT_CONFIGS 自动初始化。
    # 应用启动时 init_default_configs() 会自动插入缺失的配置项。
    pass


def downgrade() -> None:
    op.execute("DELETE FROM system_config WHERE config_key = 'pipeline.seedance_image_face_mask_enabled'")
