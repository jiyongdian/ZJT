"""
优化 ai_tools 表索引

删除与 idx_user_id_type_create_time 重复的 idx_user_id_create_time 索引，
新增 idx_status_create_time (status, create_time) 索引优化模型分析查询。

Revision ID: 20260509_opt_ai_tools_idx
Revises: 20260508_create_notifications
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260509_opt_ai_tools_idx'
down_revision = '20260508_create_notifications'
branch_labels = None
depends_on = None


def _index_exists(conn, table_name, index_name):
    """检查索引是否存在"""
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = :table AND index_name = :idx"
    ), {"table": table_name, "idx": index_name})
    return result.scalar() > 0


def upgrade():
    conn = op.get_bind()

    # 删除重复索引（idx_user_id_type_create_time 已覆盖 user_id + create_time 查询）
    if _index_exists(conn, 'ai_tools', 'idx_user_id_create_time'):
        op.execute("DROP INDEX idx_user_id_create_time ON ai_tools")

    # 新增 status + create_time 索引，优化模型分析查询
    if not _index_exists(conn, 'ai_tools', 'idx_status_create_time'):
        op.execute("CREATE INDEX idx_status_create_time ON ai_tools (status, create_time)")


def downgrade():
    conn = op.get_bind()

    if _index_exists(conn, 'ai_tools', 'idx_status_create_time'):
        op.execute("DROP INDEX idx_status_create_time ON ai_tools")

    if not _index_exists(conn, 'ai_tools', 'idx_user_id_create_time'):
        op.execute("CREATE INDEX idx_user_id_create_time ON ai_tools (user_id, create_time)")
