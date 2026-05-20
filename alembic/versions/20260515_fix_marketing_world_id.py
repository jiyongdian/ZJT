"""fix_marketing_world_id

Revision ID: 20260515_mkt_world
Revises: 20260515_user_prefs
Create Date: 2026-05-15

将营销智能体(session_type=2)的所有会话 world_id 统一为 "1"，
解决因 world_id 不一致导致的历史记录无法显示的问题。
"""
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260515_mkt_world'
down_revision: str = '20260515_user_prefs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """将所有营销会话的 world_id 统一为固定值"""
    op.execute("""
        UPDATE chat_sessions
        SET world_id = '1'
        WHERE session_type = 2 AND world_id != '1'
    """)


def downgrade() -> None:
    """回滚：无法自动还原原始 world_id，仅记录日志"""
    pass
