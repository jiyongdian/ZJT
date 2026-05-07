"""create_agent_verifications_table

Revision ID: 20260427_agent_verifications
Revises: 20260424_cleanup_qwen_stale
Create Date: 2026-04-27

Create agent_verifications table for cross-process verification sharing.
Replaces in-memory VerificationRequest + threading.Event with database-backed approach.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20260427_agent_verifications'
down_revision: Union[str, None] = '20260424_cleanup_qwen_stale'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_verifications table"""
    op.execute("""
        CREATE TABLE IF NOT EXISTS `agent_verifications` (
          `id` int NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
          `verification_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'UUID verification identifier',
          `task_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Associated task ID',
          `verification_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ask_user' COMMENT 'Type: ask_user',
          `title` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '' COMMENT 'Verification title',
          `description` text COLLATE utf8mb4_unicode_ci COMMENT 'Verification description / question',
          `options` text COLLATE utf8mb4_unicode_ci COMMENT 'Options list (JSON array)',
          `context` text COLLATE utf8mb4_unicode_ci COMMENT 'Extra context (JSON object)',
          `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'Status: pending/approved/rejected/cancelled',
          `result` longtext COLLATE utf8mb4_unicode_ci COMMENT 'Result (JSON: {action, user_input})',
          `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Creation time',
          PRIMARY KEY (`id`),
          UNIQUE KEY `uk_verification_id` (`verification_id`),
          KEY `idx_task_id` (`task_id`),
          KEY `idx_status` (`status`),
          KEY `idx_created_at` (`created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent verification requests for cross-process sharing'
    """)
    print("[Migration] Created agent_verifications table")


def downgrade() -> None:
    """Drop agent_verifications table"""
    op.execute("DROP TABLE IF EXISTS `agent_verifications`")
    print("[Migration] Dropped agent_verifications table")
