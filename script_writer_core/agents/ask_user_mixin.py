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

from model.agent_verifications import AgentVerificationsModel

logger = logging.getLogger(__name__)


class AskUserMixin:
    """向用户提问并等待回答的 Mixin"""

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

        logger.info(f"{self.agent_id}: Creating user verification request: {question}")

        try:
            # 防重复机制：检查是否已有已完成的 ask_user
            existing = AgentVerificationsModel.get_latest_completed_by_task(self.task_id)
            if existing and existing.result:
                user_input = existing.result.get("user_input", "")
                logger.info(f"{self.agent_id}: Reusing existing ask_user result: {user_input}")
                return {
                    "success": True,
                    "user_input": user_input,
                    "message": f"用户已回答: {user_input}",
                    "reused": True
                }

            # 防重复机制：检查是否已有 pending 的 ask_user，避免创建重复 verification
            pending = AgentVerificationsModel.get_pending_by_task(self.task_id)
            if pending:
                logger.info(f"{self.agent_id}: Found pending verification {pending.verification_id}, waiting instead of creating new")
                result = self.task_manager.wait_for_verification(
                    verification=pending,
                    timeout=300
                )
                if result.get("success"):
                    return {
                        "success": True,
                        "user_input": result.get("user_input", ""),
                        "message": f"用户已回答: {result.get('user_input', '')}"
                    }
                return {
                    "error": result.get("error", "验证失败"),
                    "user_input": None
                }

            # 创建验证请求
            verification = self.task_manager.create_verification(
                task_id=self.task_id,
                verification_type="ask_user",
                title="需要用户输入",
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

            # 返回用户的回答
            return {
                "success": True,
                "user_input": result.get("user_input", ""),
                "message": f"用户已回答: {result.get('user_input', '')}"
            }

        except Exception as e:
            error_msg = f"ask_user 处理失败: {str(e)}"
            logger.error(f"{self.agent_id}: {error_msg}", exc_info=True)
            return {"error": error_msg}
