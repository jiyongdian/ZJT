"""Create chat_messages and chat_history_summaries tables

新建 chat_messages 表（逐条存储智能体对话消息，替代 conversation_history JSON 整体覆盖）和
chat_history_summaries 表（记录上下文压缩摘要元数据）。

Revision ID: 20260612_chat_messages
Revises: 20260605_create_at_idx
Create Date: 2026-06-12
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '20260612_chat_messages'
down_revision: Union[str, None] = '20260605_create_at_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _table_exists(conn, table: str) -> bool:
    """Check if a table exists"""
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
    ), {"table": table})
    return result.scalar() > 0


def upgrade() -> None:
    conn = op.get_bind()

    # --- chat_messages ---
    if not _table_exists(conn, 'chat_messages'):
        conn.execute(text("""
            CREATE TABLE `chat_messages` (
              `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'Primary key, global message order',
              `message_id` VARCHAR(64) NOT NULL COMMENT 'UUID message identifier',
              `session_id` VARCHAR(36) NOT NULL COMMENT 'Associated chat session ID',
              `task_id` VARCHAR(64) DEFAULT NULL COMMENT 'Associated agent task ID',
              `agent_id` VARCHAR(64) DEFAULT NULL COMMENT 'Agent identifier',
              `agent_scope` VARCHAR(16) NOT NULL DEFAULT 'pm' COMMENT 'pm/expert',

              `role` VARCHAR(32) NOT NULL COMMENT 'system/user/assistant/tool/summary/verification',
              `message_type` VARCHAR(32) NOT NULL COMMENT 'normal/tool_call/tool_result/verification_request/verification_answer/system_prompt/tool_definitions/context_summary',
              `content` LONGTEXT NOT NULL COMMENT 'Normalized content JSON for UI/system logic',

              `provider` VARCHAR(32) DEFAULT NULL COMMENT 'openai/gemini/deepseek/anthropic/litellm/etc',
              `api_format` VARCHAR(32) DEFAULT NULL COMMENT 'openai_chat/gemini_chat/anthropic_messages/etc',
              `provider_payload` LONGTEXT DEFAULT NULL COMMENT 'Original provider message JSON for active context reconstruction',
              `provider_meta` LONGTEXT DEFAULT NULL COMMENT 'Provider metadata JSON, tokens/reasoning_content/thought_signature/finish_reason/etc',

              `tool_call_id` VARCHAR(128) DEFAULT NULL COMMENT 'Tool call ID if this message belongs to a tool call group',
              `tool_name` VARCHAR(128) DEFAULT NULL COMMENT 'Tool name for tool call/result messages',
              `verification_id` VARCHAR(64) DEFAULT NULL COMMENT 'Verification ID for ask_user messages',

              `visibility` VARCHAR(16) NOT NULL DEFAULT 'both' COMMENT 'ui/llm/both/internal',
              `context_state` VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active/summarized/excluded/deleted',
              `generated_summary_id` VARCHAR(64) DEFAULT NULL COMMENT 'Only for summary messages: the summary_id this message represents',
              `covered_by_summary_id` VARCHAR(64) DEFAULT NULL COMMENT 'For summarized messages: which summary covers this message',

              `idempotency_key` VARCHAR(128) NOT NULL COMMENT 'Deduplication key',
              `source` VARCHAR(32) NOT NULL COMMENT 'agent/frontend/verification/system/compression',

              `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              `update_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

              PRIMARY KEY (`id`),
              UNIQUE KEY `uk_message_id` (`message_id`),
              UNIQUE KEY `uk_idempotency_key` (`idempotency_key`),
              KEY `idx_session_id_id` (`session_id`, `id`),
              KEY `idx_session_scope_id` (`session_id`, `agent_scope`, `id`),
              KEY `idx_session_context` (`session_id`, `context_state`, `id`),
              KEY `idx_task_id` (`task_id`),
              KEY `idx_verification_id` (`verification_id`),
              KEY `idx_generated_summary_id` (`generated_summary_id`),
              KEY `idx_covered_by_summary_id` (`covered_by_summary_id`),
              KEY `idx_create_at` (`create_at`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent chat messages, one row per message'
        """))
        logger.info("Created table chat_messages")
    else:
        logger.info("Table chat_messages already exists, skipping")

    # --- chat_history_summaries ---
    if not _table_exists(conn, 'chat_history_summaries'):
        conn.execute(text("""
            CREATE TABLE `chat_history_summaries` (
              `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT 'Primary key',
              `summary_id` VARCHAR(64) NOT NULL COMMENT 'UUID summary identifier',
              `session_id` VARCHAR(36) NOT NULL COMMENT 'Associated chat session ID',

              `from_message_id` BIGINT DEFAULT NULL COMMENT 'First normal message covered by this summary',
              `to_message_id` BIGINT DEFAULT NULL COMMENT 'Last normal message covered by this summary',
              `summary_message_id` BIGINT NOT NULL COMMENT 'chat_messages.id of the generated summary message',

              `summary_level` INT NOT NULL DEFAULT 1 COMMENT '1 for raw-message summary, 2+ for summary-of-summary',
              `parent_summary_ids` JSON DEFAULT NULL COMMENT 'Parent summaries absorbed by this summary',

              `summary_text` LONGTEXT NOT NULL COMMENT 'Summary text',
              `raw_message_count` INT NOT NULL DEFAULT 0 COMMENT 'Number of raw messages covered',

              `model_id` INT DEFAULT NULL COMMENT 'Model used to create summary',
              `vendor_id` INT DEFAULT NULL COMMENT 'Vendor used to create summary',

              `create_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

              PRIMARY KEY (`id`),
              UNIQUE KEY `uk_summary_id` (`summary_id`),
              KEY `idx_session_id` (`session_id`),
              KEY `idx_summary_message_id` (`summary_message_id`),
              KEY `idx_range` (`from_message_id`, `to_message_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Chat history compression summaries'
        """))
        logger.info("Created table chat_history_summaries")
    else:
        logger.info("Table chat_history_summaries already exists, skipping")


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, 'chat_history_summaries'):
        conn.execute(text("DROP TABLE `chat_history_summaries`"))
        logger.info("Dropped table chat_history_summaries")

    if _table_exists(conn, 'chat_messages'):
        conn.execute(text("DROP TABLE `chat_messages`"))
        logger.info("Dropped table chat_messages")
