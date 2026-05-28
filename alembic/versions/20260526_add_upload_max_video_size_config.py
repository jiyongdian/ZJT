"""add upload max_video_size_mb config

Revision ID: 20260526_upload_max_video_size
Revises: 20260524_ds_v4_pro_cut
Create Date: 2026-05-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260526_upload_max_video_size'
down_revision = '20260524_ds_v4_pro_cut'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 配置项通过 config/default_configs.py 中的 DEFAULT_CONFIGS 自动初始化
    # 应用启动时 init_default_configs() 会自动插入缺失的配置项
    pass


def downgrade() -> None:
    op.execute("DELETE FROM system_config WHERE config_key = 'upload.max_video_size_mb'")
