"""
LLMMessageAdapter - 将 chat_messages 记录转换为不同供应商的 API 消息格式

支持 OpenAI 兼容（含 DeepSeek reasoning_content）和 Gemini（含 thought_signature）。
"""
from typing import Any, Optional, Dict
import json
import logging

from model.chat_messages import ChatMessageEntity

logger = logging.getLogger(__name__)


class LLMMessageAdapter:
    """消息适配器基类"""

    def to_api_message(self, message: ChatMessageEntity) -> Optional[Dict[str, Any]]:
        """
        将 ChatMessageEntity 转为供应商 API 格式。
        返回 None 表示跳过此消息。
        """
        raise NotImplementedError


class OpenAICompatibleAdapter(LLMMessageAdapter):
    """
    OpenAI 兼容适配器。
    覆盖 OpenAI、DeepSeek 等使用 OpenAI Chat API 格式的供应商。
    """

    def to_api_message(self, message: ChatMessageEntity) -> Optional[Dict[str, Any]]:
        # verification_request 不进 LLM 上下文
        if message.message_type == 'verification_request':
            return None

        # 优先从 provider_payload 恢复
        if message.provider_payload and isinstance(message.provider_payload, dict):
            return self._restore_from_payload(message)

        # 备选：从统一字段构建
        return self._build_from_fields(message)

    def _restore_from_payload(self, message: ChatMessageEntity) -> Dict[str, Any]:
        """从 provider_payload 恢复原始结构"""
        payload = dict(message.provider_payload)
        # 确保 role 正确
        payload['role'] = message.role
        # tool 消息必须有顶层 tool_call_id（旧 payload 可能缺少）
        if message.role == 'tool' and 'tool_call_id' not in payload:
            payload['tool_call_id'] = message.tool_call_id or ''
        # tool 消息的 content 必须是 string（API 要求），不能是 dict/list
        if message.role == 'tool' and 'content' in payload:
            c = payload['content']
            if isinstance(c, (dict, list)):
                payload['content'] = json.dumps(c, ensure_ascii=False)
            elif c is None:
                payload['content'] = ''
        # assistant 消息的 content 必须是 string/null/list（不能是裸 dict）
        if message.role == 'assistant' and 'content' in payload:
            c = payload['content']
            if isinstance(c, dict):
                # dict content 可能是内部格式 {"text": "...", "reasoning_content": "..."}
                # 提取 text 作为 content
                payload['content'] = c.get('text') if 'text' in c else json.dumps(c, ensure_ascii=False)
        return payload

    def _build_from_fields(self, message: ChatMessageEntity) -> Optional[Dict[str, Any]]:
        """从统一字段构建 API 消息"""
        role = message.role
        content = message.content

        if role == 'system':
            text = content.get('text', '') if isinstance(content, dict) else str(content)
            return {"role": "system", "content": text}

        if role == 'user':
            text = content.get('text', '') if isinstance(content, dict) else str(content)
            return {"role": "user", "content": text}

        if role == 'assistant':
            if message.message_type == 'tool_call' and isinstance(content, dict) and 'tool_calls' in content:
                result = {
                    "role": "assistant",
                    "content": content.get('text'),
                    "tool_calls": content['tool_calls'],
                }
                # DeepSeek: reasoning_content
                if 'reasoning_content' in content:
                    result['reasoning_content'] = content['reasoning_content']
                return result

            if message.message_type == 'context_summary':
                text = content.get('text', '') if isinstance(content, dict) else str(content)
                return {"role": "system", "content": f"[历史摘要]\n{text}"}

            # 普通 assistant 消息
            text = content.get('text', '') if isinstance(content, dict) else str(content)
            result = {"role": "assistant", "content": text}
            # DeepSeek: 补充空 reasoning_content（某些模型要求）
            if isinstance(content, dict) and 'reasoning_content' in content:
                result['reasoning_content'] = content['reasoning_content']
            return result

        if role == 'tool':
            tool_content = json.dumps(content, ensure_ascii=False) if isinstance(content, (dict, list)) else str(content)
            return {
                "role": "tool",
                "tool_call_id": message.tool_call_id or '',
                "content": tool_content,
            }

        if role == 'summary':
            text = content.get('text', '') if isinstance(content, dict) else str(content)
            return {"role": "system", "content": f"[历史摘要]\n{text}"}

        # 未知 role，跳过
        return None


class GeminiAdapter(LLMMessageAdapter):
    """
    Gemini 适配器。
    主要区别：需要恢复 thought_signature。
    """

    def to_api_message(self, message: ChatMessageEntity) -> Optional[Dict[str, Any]]:
        if message.message_type == 'verification_request':
            return None

        if message.provider_payload and isinstance(message.provider_payload, dict):
            payload = dict(message.provider_payload)
            payload['role'] = message.role
            # Gemini: 确保 thought_signature 存在于 active tool_call 消息中
            return payload

        # 备选构建（复用 OpenAI 逻辑）
        return OpenAICompatibleAdapter().to_api_message(message)


class DeepSeekAdapter(OpenAICompatibleAdapter):
    """
    DeepSeek 适配器。
    主要区别：历史 assistant 消息可能需要补充空 reasoning_content。
    """

    def to_api_message(self, message: ChatMessageEntity) -> Optional[Dict[str, Any]]:
        result = super().to_api_message(message)
        if result is None:
            return None

        # DeepSeek: assistant 消息如果没有 reasoning_content，补充空字符串
        if result.get('role') == 'assistant' and 'reasoning_content' not in result:
            # 只有 tool_call 消息和纯文本消息需要补充
            if 'tool_calls' in result or result.get('content'):
                result['reasoning_content'] = ''

        return result


class LLMMessageAdapterRegistry:
    """适配器注册表"""

    # 模型名称前缀到供应商的映射
    _VENDOR_PREFIXES = {
        'gemini': 'gemini',
        'gemini-': 'gemini',
    }

    _DEEPSEEK_PREFIXES = {
        'deepseek',
        'doubao-seed',
    }

    def get_adapter(
        self,
        model: str,
        vendor_id: Optional[int] = None,
        api_format: Optional[str] = None,
    ) -> LLMMessageAdapter:
        """根据模型和供应商信息返回合适的适配器"""
        model_lower = (model or '').lower()

        # DeepSeek 系列
        for prefix in self._DEEPSEEK_PREFIXES:
            if model_lower.startswith(prefix):
                return DeepSeekAdapter()

        # Gemini 系列
        if 'gemini' in model_lower:
            return GeminiAdapter()

        # 默认：OpenAI 兼容
        return OpenAICompatibleAdapter()
