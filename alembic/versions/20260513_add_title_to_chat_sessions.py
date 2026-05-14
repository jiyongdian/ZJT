"""add_title_to_chat_sessions

Revision ID: 20260513_add_title
Revises: 20260513_fix_site_number
Create Date: 2026-05-13

Add title field to chat_sessions table for displaying conversation title in sidebar
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260513_add_title'
down_revision: str = '20260513_fix_site_number'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add title column to chat_sessions"""
    op.execute("""
        ALTER TABLE `chat_sessions`
        ADD COLUMN `title` VARCHAR(100) DEFAULT NULL COMMENT '会话标题（取自首条用户消息或用户自定义）'
        AFTER `session_type`
    """)
    print("[Migration] Added title column to chat_sessions")


def downgrade() -> None:
    """Remove title column from chat_sessions"""
    op.execute("""
        ALTER TABLE `chat_sessions` DROP COLUMN `title`
    """)
    print("[Migration] Removed title column from chat_sessions")
