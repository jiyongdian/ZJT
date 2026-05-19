from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from perseids_server.client import make_perseids_request
from config.unified_config import COMPUTING_POWER_CHECK_THRESHOLD

logger = logging.getLogger(__name__)


class InsufficientComputingPowerError(Exception):
    """算力不足异常 - 当用户算力降到阈值以下时抛出"""
    def __init__(self, computing_power: int, message: str = "算力不足，任务已停止"):
        self.computing_power = computing_power
        self.message = message
        super().__init__(self.message)


def check_computing_power_sync(auth_token: str, agent_id: str, threshold: int = COMPUTING_POWER_CHECK_THRESHOLD) -> int:
    """
    同步检查用户算力（在后台线程中使用）

    Args:
        auth_token: 认证令牌
        agent_id: 调用方 agent ID（用于日志）
        threshold: 算力阈值，默认 1

    Returns:
        int: 当前算力值

    Raises:
        InsufficientComputingPowerError: 算力低于阈值
    """
    if not auth_token:
        return 999999  # 无 token 时跳过检查

    try:
        headers = {'Authorization': f'Bearer {auth_token}'}
        success, message, response_data = make_perseids_request(
            endpoint='user/check_computing_power',
            method='GET',
            headers=headers
        )

        if not success:
            logger.warning(f"{agent_id}: 算力检查失败: {message}, 继续执行")
            return 999999  # 检查失败时不阻断任务

        computing_power = response_data.get('computing_power', 0) if isinstance(response_data, dict) else 0

        if computing_power < threshold:
            raise InsufficientComputingPowerError(
                computing_power=computing_power,
                message=f"算力不足（当前: {computing_power}），任务已停止"
            )

        return computing_power

    except InsufficientComputingPowerError:
        raise
    except Exception as e:
        logger.warning(f"{agent_id}: 算力检查异常: {e}, 继续执行")
        return 999999  # 异常时不阻断任务


class BaseAgent:
    """智能体基类"""
    
    def __init__(
        self, 
        agent_id: str, 
        skill_names: List[str], 
        model: str, 
        allowed_tools: List[str], 
        system_prompt: str
    ):
        self.agent_id = agent_id
        self.skill_names = skill_names
        # 保留 skill_name 用于向后兼容（使用第一个技能）
        self.skill_name = skill_names[0] if skill_names else "unknown"
        self.model = model
        self.allowed_tools = allowed_tools
        self.system_prompt = system_prompt
        self.conversation_history: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        
        logger.info(f"Initialized {self.__class__.__name__} - ID: {agent_id}, Skills: {', '.join(skill_names)}")
    
    def send_message(self, message: str, **kwargs) -> Dict[str, Any]:
        """发送消息并获取响应"""
        raise NotImplementedError("Subclasses must implement send_message()")
    
    def handle_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用"""
        if tool_name not in self.allowed_tools:
            error_msg = f"工具 {tool_name} 不在允许列表中"
            logger.warning(f"{self.agent_id}: {error_msg}")
            return {"error": error_msg}
        
        return self._execute_tool(tool_name, tool_args)
    
    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具调用 - 由子类实现具体逻辑"""
        raise NotImplementedError("Subclasses must implement _execute_tool()")
    
    def add_to_history(self, role: str, content: Any):
        """添加消息到对话历史"""
        logger.debug(f"{self.agent_id}: add_to_history called - role={role}, content type={type(content).__name__}")
        
        if role == "tool":
            logger.info(f"{self.agent_id}: Adding TOOL message to conversation_history:")
            logger.info(f"{self.agent_id}:   - content type: {type(content).__name__}")
            if isinstance(content, dict):
                logger.info(f"{self.agent_id}:   - content keys: {list(content.keys())}")
                logger.info(f"{self.agent_id}:   - content: {content}")
            else:
                logger.warning(f"{self.agent_id}:   - WARNING: content is not dict, it's {type(content).__name__}: {content}")
        
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.debug(f"{self.agent_id}: conversation_history now has {len(self.conversation_history)} messages")
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
        logger.info(f"{self.agent_id}: 对话历史已清空")
    
    def get_history_summary(self) -> str:
        """获取对话历史摘要"""
        return f"智能体: {self.agent_id}, 对话轮次: {len(self.conversation_history)}, 创建时间: {self.created_at}"
