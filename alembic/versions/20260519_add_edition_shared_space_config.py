"""add_edition_shared_space_config

Revision ID: 20260519_shared_space
Revises: 20260519_local_path_hash
Create Date: 2026-05-19

为 system_config 表新增 edition.shared_space 配置项，
允许商业版用户将空间设置为共享模式（所有用户共享数据）。
"""
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260519_shared_space'
down_revision: str = '20260519_local_path_hash'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """配置项由 init_default_configs() 从 YAML 初始化到数据库，此处无需操作"""
    pass


def downgrade() -> None:
    """删除 edition.shared_space 配置项"""
    op.execute("""
        DELETE FROM system_config WHERE config_key = 'edition.shared_space'
    """)
