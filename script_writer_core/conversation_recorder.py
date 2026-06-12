"""
ConversationRecorder - 逐条写入对话消息到数据库

纯同步类。Agent 后台线程中直接调用；async 路由中由调用方用 asyncio.to_thread() 包装。
写入失败仅记录 error 日志，不阻塞 Agent 主流程。
"""
import json
import hashlib
import uuid
from typing import Any, Optional
from datetime import datetime

from model.chat_messages import ChatMessageEntity, ChatMessagesModel
import logging

logger = logging.getLogger(__name__)


class ConversationRecorder:
    """逐条写入对话消息到 chat_messages 表"""

    def __init__(self):
        self._local_index = 0  # 用于 expert 内部消息的递增序号

    def append_message(
        self,
        session_id: str,
        role: str,
        content: Any,
        message_type: str = "normal",
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent_scope: str = "pm",
        provider: Optional[str] = None,
        api_format: Optional[str] = None,
        provider_payload: Optional[dict] = None,
        provider_meta: Optional[dict] = None,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        verification_id: Optional[str] = None,
        visibility: str = "both",
        context_state: str = "active",
        generated_summary_id: Optional[str] = None,
        covered_by_summary_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        source: str = "agent",
    ) -> Optional[ChatMessageEntity]:
        """
        写入一条消息到 chat_messages，幂等。

        Args:
            idempotency_key: 显式指定时跳过自动生成，用于路由和 Agent 之间的幂等对齐。
            generated_summary_id: 仅摘要消息使用。
            covered_by_summary_id: 被压缩覆盖的消息使用。
        """
        message_id = str(uuid.uuid4())
        timestamp_minute = datetime.now().strftime('%Y%m%d%H%M')

        # Expert 内部消息使用递增 local_index
        if agent_scope == 'expert':
            self._local_index += 1

        # 幂等键：显式指定时直接使用，否则自动生成
        if idempotency_key is None:
            idempotency_key = self._build_idempotency_key(
                session_id=session_id,
                agent_scope=agent_scope,
                agent_id=agent_id,
                role=role,
                content=content,
                message_type=message_type,
                task_id=task_id,
                verification_id=verification_id,
                tool_call_id=tool_call_id,
                local_index=self._local_index if agent_scope == 'expert' else None,
                timestamp_minute=timestamp_minute,
            )

        # content 统一序列化为 JSON
        content_json = json.dumps(content, ensure_ascii=False)

        # provider_payload / provider_meta 序列化
        pp_json = json.dumps(provider_payload, ensure_ascii=False) if provider_payload else None
        pm_json = json.dumps(provider_meta, ensure_ascii=False) if provider_meta else None

        try:
            entity = ChatMessagesModel.create(
                message_id=message_id,
                session_id=session_id,
                role=role,
                message_type=message_type,
                content=content_json,
                idempotency_key=idempotency_key,
                source=source,
                agent_scope=agent_scope,
                context_state=context_state,
                task_id=task_id,
                agent_id=agent_id,
                provider=provider,
                api_format=api_format,
                provider_payload=pp_json,
                provider_meta=pm_json,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                verification_id=verification_id,
                visibility=visibility,
                generated_summary_id=generated_summary_id,
                covered_by_summary_id=covered_by_summary_id,
            )
            if (
                entity
                and message_type in ("system_prompt", "tool_definitions")
                and entity.context_state != context_state
            ):
                ChatMessagesModel.update_context_state([entity.id], context_state)
                entity.context_state = context_state
            return entity
        except Exception as e:
            logger.error(f"ConversationRecorder: Failed to persist message: {e}")
            return None

    def _build_idempotency_key(
        self,
        session_id: str,
        agent_scope: str,
        agent_id: Optional[str],
        role: str,
        content: Any,
        message_type: str,
        task_id: Optional[str],
        verification_id: Optional[str],
        tool_call_id: Optional[str],
        local_index: Optional[int],
        timestamp_minute: str,
    ) -> str:
        """
        根据 idempotency_key 生成规则构建唯一键。

        规则对照设计文档：
        - system prompt:     session:{session_id}:system:{prompt_hash}
        - tool_definitions:  session:{session_id}:tool_definitions
        - user (initial):    task:{task_id}:user:initial
        - user (agent):      task:{task_id}:user:{content_hash}
        - verification req:  verification:{verification_id}:request
        - verification ans:  verification:{verification_id}:answer:{content_hash}
        - assistant tool_call: task:{task_id}:assistant:toolcall:{tool_call_ids_hash}
        - assistant normal:  task:{task_id}:assistant:{content_hash}:{timestamp_minute}
        - tool result:       task:{task_id}:tool:{tool_call_id}:result
        - expert internal:   expert:{agent_id}:{task_id}:{local_index}
        """
        content_hash = self._content_hash(content)

        # system prompt
        if message_type == "system_prompt":
            return f"session:{session_id}:system:{content_hash}"

        # tool_definitions
        if message_type == "tool_definitions":
            return f"session:{session_id}:tool_definitions"

        # context_summary
        if message_type == "context_summary":
            return f"session:{session_id}:summary:{content_hash}:{timestamp_minute}"

        # verification request
        if message_type == "verification_request" and verification_id:
            return f"verification:{verification_id}:request"

        # verification answer
        if message_type == "verification_answer" and verification_id:
            return f"verification:{verification_id}:answer:{content_hash}"

        # expert 内部消息
        if agent_scope == "expert":
            tid = task_id or "no_task"
            aid = agent_id or "unknown"
            idx = local_index or 0
            return f"expert:{aid}:{tid}:{idx}"

        # tool result
        if message_type == "tool_result" and task_id and tool_call_id:
            return f"task:{task_id}:tool:{tool_call_id}:result"

        # assistant tool_call
        if message_type == "tool_call" and task_id:
            # 从 content 中提取所有 tool_call ids 生成 hash
            call_ids_hash = self._tool_call_ids_hash(content)
            return f"task:{task_id}:assistant:toolcall:{call_ids_hash}"

        # assistant normal
        if role == "assistant" and task_id:
            return f"task:{task_id}:assistant:{content_hash}:{timestamp_minute}"

        # user message (agent 追加)
        if role == "user" and task_id:
            return f"task:{task_id}:user:{content_hash}"

        # fallback
        return f"{session_id}:{agent_scope}:{role}:{content_hash}:{timestamp_minute}"

    @staticmethod
    def _content_hash(content: Any) -> str:
        """SHA-256 hash of serialized content, first 16 chars"""
        raw = json.dumps(content, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

    @staticmethod
    def _tool_call_ids_hash(content: Any) -> str:
        """Extract all tool_call IDs from content and hash them"""
        ids = []
        if isinstance(content, dict) and "tool_calls" in content:
            for tc in content["tool_calls"]:
                if isinstance(tc, dict) and "id" in tc:
                    ids.append(tc["id"])
                elif hasattr(tc, 'id'):
                    ids.append(tc.id)
        raw = json.dumps(sorted(ids), ensure_ascii=False)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]
