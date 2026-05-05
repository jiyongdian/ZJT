"""
AskUserMixin - 向用户提问并等待回答的共享功能

使用方式：
    class MyAgent(BaseAgent, AskUserMixin):
        def __init__(self, ...):
            self.task_manager = ...
            self.task_id = ...

要求子类具备以下属性：
    - self.task_manager: TaskManager 实例
    - self.task_id: str，当前任务 ID
    - self.agent_id: str，智能体标识（用于日志）
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class AskUserMixin:
    """向用户提问并等待回答的 Mixin"""

    # agent_id → 中文显示名映射
    _DISPLAY_NAME_MAP = {
        "pm_agent": "剧本编排",
        "expert_story-writer": "故事写手",
        "expert_character-creator": "角色设计",
        "expert_location-creator": "场景设计",
        "expert_plot-analyzer": "剧情分析",
        "expert_content-compliance-checker": "内容审核",
        "expert_novel-episode-splitter": "剧集拆分",
        "expert_character-image-designer": "角色形象设计",
        "expert_location-prop-image-designer": "场景道具设计",
    }

    def _get_agent_display_name(self) -> str:
        """获取当前智能体的中文显示名"""
        agent_id = getattr(self, 'agent_id', '')
        if agent_id in self._DISPLAY_NAME_MAP:
            return self._DISPLAY_NAME_MAP[agent_id]
        # 兜底：从 agent_id 提取 skill 名称
        if agent_id.startswith("expert_"):
            return agent_id[len("expert_"):]
        return agent_id or "AI"

    def _handle_ask_user(self, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """处理 ask_user 工具调用 - 向用户提问并等待响应

        Args:
            tool_args: LLM 传入的工具参数，包含 question, options, context

        Returns:
            成功: {"success": True, "user_input": "...", "message": "用户已回答: ..."}
            超时/失败: {"error": "...", "user_input": None}
        """
        # 检查必要依赖
        if not getattr(self, 'task_manager', None) or not getattr(self, 'task_id', None):
            error_msg = "ask_user 工具未配置 task_manager 或 task_id"
            logger.error(f"{self.agent_id}: {error_msg}")
            return {"error": error_msg}

        # 提取参数
        question = tool_args.get("question", "")
        options = tool_args.get("options", [])
        context = tool_args.get("context", {})

        if not question:
            return {"error": "question 参数不能为空"}

        if not options or not isinstance(options, list) or len(options) == 0:
            return {"error": "options 参数不能为空，必须提供至少一个选项供用户选择"}

        logger.info(f"{self.agent_id}: Creating user verification request: {question}")

        try:
            # 创建验证请求
            agent_name = self._get_agent_display_name()
            verification = self.task_manager.create_verification(
                task_id=self.task_id,
                verification_type="ask_user",
                title=f"{agent_name} 向您提问",
                description=question,
                options=options,
                context=context
            )

            # 阻塞等待用户响应（最多5分钟）
            result = self.task_manager.wait_for_verification(
                verification=verification,
                timeout=300
            )

            logger.info(f"{self.agent_id}: User responded: {result}")

            # 检查是否超时或出错
            if not result.get("success"):
                return {
                    "error": result.get("error", "验证失败"),
                    "user_input": None
                }

            # 返回用户的回答（附带 verification 元数据，用于写入 conversation_history）
            return {
                "success": True,
                "user_input": result.get("user_input", ""),
                "message": f"用户已回答: {result.get('user_input', '')}",
                "_verification_meta": {
                    "verification_id": verification.verification_id,
                    "question": question,
                    "options": options
                }
            }

        except Exception as e:
            error_msg = f"ask_user 处理失败: {str(e)}"
            logger.error(f"{self.agent_id}: {error_msg}", exc_info=True)
            return {"error": error_msg}
