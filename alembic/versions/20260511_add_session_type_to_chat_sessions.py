"""add_session_type_to_chat_sessions

Revision ID: 20260511_add_session_type
Revises: 20260509_opt_ai_tools_idx
Create Date: 2026-05-11

Add session_type field to chat_sessions table for distinguishing
script writer sessions (1) from marketing agent sessions (2)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260511_add_session_type'
down_revision: str = '20260509_opt_ai_tools_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add session_type field to chat_sessions table"""
    op.execute("""
        ALTER TABLE chat_sessions
        ADD COLUMN session_type TINYINT NOT NULL DEFAULT 1
        COMMENT '会话类型: 1=剧本智能体, 2=营销智能体'
        AFTER world_id
    """)

    op.execute("""
        CREATE INDEX idx_user_world_type ON chat_sessions (user_id, world_id, session_type)
    """)

    print("[Migration] Added session_type field to chat_sessions table")


def downgrade() -> None:
    """Remove session_type field from chat_sessions table"""
    op.execute("DROP INDEX idx_user_world_type ON chat_sessions")
    op.execute("ALTER TABLE chat_sessions DROP COLUMN session_type")

    print("[Migration] Removed session_type field from chat_sessions table")
