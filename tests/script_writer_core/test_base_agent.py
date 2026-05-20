"""
BaseAgent 及 check_computing_power_sync 单元测试

测试 script_writer_core/agents/base_agent.py 中的新增逻辑和基类方法。
"""
import os
import sys
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from script_writer_core.agents.base_agent import (
    InsufficientComputingPowerError,
    check_computing_power_sync,
    BaseAgent,
)


class TestInsufficientComputingPowerError(unittest.TestCase):
    """测试 InsufficientComputingPowerError 异常"""

    def test_default_message(self):
        err = InsufficientComputingPowerError(computing_power=0)
        self.assertEqual(err.message, "算力不足，任务已停止")
        self.assertEqual(err.computing_power, 0)
        self.assertIn("算力不足", str(err))

    def test_custom_message(self):
        err = InsufficientComputingPowerError(
            computing_power=5,
            message="自定义消息"
        )
        self.assertEqual(err.message, "自定义消息")
        self.assertEqual(err.computing_power, 5)

    def test_is_exception(self):
        err = InsufficientComputingPowerError(computing_power=0)
        self.assertIsInstance(err, Exception)


class TestCheckComputingPowerSync(unittest.TestCase):
    """测试 check_computing_power_sync"""

    def test_no_auth_token_returns_high_value(self):
        """无 token 时返回 999999"""
        result = check_computing_power_sync(auth_token="", agent_id="test")
        self.assertEqual(result, 999999)

    @patch('script_writer_core.agents.base_agent.make_perseids_request')
    def test_api_failure_returns_high_value(self, mock_api):
        """API 请求失败时不阻断，返回 999999"""
        mock_api.return_value = (False, "timeout", None)
        result = check_computing_power_sync(auth_token="token", agent_id="test")
        self.assertEqual(result, 999999)

    @patch('script_writer_core.agents.base_agent.make_perseids_request')
    def test_sufficient_power(self, mock_api):
        """算力充足时返回算力值"""
        mock_api.return_value = (True, "", {"computing_power": 100})
        result = check_computing_power_sync(auth_token="token", agent_id="test", threshold=1)
        self.assertEqual(result, 100)

    @patch('script_writer_core.agents.base_agent.make_perseids_request')
    def test_insufficient_power_raises(self, mock_api):
        """算力不足时抛出 InsufficientComputingPowerError"""
        mock_api.return_value = (True, "", {"computing_power": 0})
        with self.assertRaises(InsufficientComputingPowerError) as ctx:
            check_computing_power_sync(auth_token="token", agent_id="test", threshold=1)
        self.assertEqual(ctx.exception.computing_power, 0)

    @patch('script_writer_core.agents.base_agent.make_perseids_request')
    def test_non_dict_response(self, mock_api):
        """非 dict 响应视为 computing_power=0"""
        mock_api.return_value = (True, "", "not a dict")
        with self.assertRaises(InsufficientComputingPowerError):
            check_computing_power_sync(auth_token="token", agent_id="test", threshold=1)

    @patch('script_writer_core.agents.base_agent.make_perseids_request')
    def test_missing_computing_power_key(self, mock_api):
        """缺少 computing_power 键视为 0"""
        mock_api.return_value = (True, "", {"other_key": 123})
        with self.assertRaises(InsufficientComputingPowerError):
            check_computing_power_sync(auth_token="token", agent_id="test", threshold=1)

    @patch('script_writer_core.agents.base_agent.make_perseids_request', side_effect=Exception("network"))
    def test_generic_exception_returns_high_value(self, mock_api):
        """通用异常不阻断，返回 999999"""
        result = check_computing_power_sync(auth_token="token", agent_id="test")
        self.assertEqual(result, 999999)

    @patch('script_writer_core.agents.base_agent.make_perseids_request')
    def test_insufficient_error_not_caught_by_generic(self, mock_api):
        """InsufficientComputingPowerError 不被通用异常捕获"""
        mock_api.return_value = (True, "", {"computing_power": 0})
        with self.assertRaises(InsufficientComputingPowerError):
            check_computing_power_sync(auth_token="token", agent_id="test", threshold=1)

    @patch('script_writer_core.agents.base_agent.make_perseids_request')
    def test_power_exactly_at_threshold(self, mock_api):
        """算力恰好等于阈值时不抛异常"""
        mock_api.return_value = (True, "", {"computing_power": 5})
        result = check_computing_power_sync(auth_token="token", agent_id="test", threshold=5)
        self.assertEqual(result, 5)


class TestBaseAgent(unittest.TestCase):
    """测试 BaseAgent 基类"""

    def _create_agent(self, **kwargs):
        """创建 BaseAgent 子类实例（实现抽象方法）"""
        defaults = {
            'agent_id': 'test-agent',
            'skill_names': ['skill-a'],
            'model': 'gpt-4',
            'allowed_tools': ['tool-1', 'tool-2'],
            'system_prompt': 'You are helpful',
        }
        defaults.update(kwargs)
        agent = BaseAgent(**defaults)
        # 手动实现抽象方法
        agent._execute_tool = lambda name, args: {"result": f"executed {name}"}
        return agent

    def test_initialization(self):
        agent = self._create_agent()
        self.assertEqual(agent.agent_id, 'test-agent')
        self.assertEqual(agent.skill_names, ['skill-a'])
        self.assertEqual(agent.skill_name, 'skill-a')  # backward compat
        self.assertEqual(agent.model, 'gpt-4')
        self.assertEqual(agent.allowed_tools, ['tool-1', 'tool-2'])
        self.assertIsInstance(agent.conversation_history, list)
        self.assertEqual(len(agent.conversation_history), 0)

    def test_empty_skill_names(self):
        agent = self._create_agent(skill_names=[])
        self.assertEqual(agent.skill_name, "unknown")

    def test_add_to_history_text(self):
        agent = self._create_agent()
        agent.add_to_history("user", "hello")
        self.assertEqual(len(agent.conversation_history), 1)
        self.assertEqual(agent.conversation_history[0]['role'], 'user')
        self.assertEqual(agent.conversation_history[0]['content'], 'hello')
        self.assertIn('timestamp', agent.conversation_history[0])

    def test_add_to_history_tool_dict(self):
        agent = self._create_agent()
        tool_content = {"name": "generate_image", "result": "ok"}
        agent.add_to_history("tool", tool_content)
        self.assertEqual(len(agent.conversation_history), 1)
        self.assertEqual(agent.conversation_history[0]['content'], tool_content)

    def test_add_to_history_tool_non_dict(self):
        """tool 角色的非 dict 内容也能正常添加"""
        agent = self._create_agent()
        agent.add_to_history("tool", "plain text")
        self.assertEqual(len(agent.conversation_history), 1)
        self.assertEqual(agent.conversation_history[0]['content'], "plain text")

    def test_clear_history(self):
        agent = self._create_agent()
        agent.add_to_history("user", "hello")
        agent.add_to_history("assistant", "hi")
        self.assertEqual(len(agent.conversation_history), 2)
        agent.clear_history()
        self.assertEqual(len(agent.conversation_history), 0)

    def test_get_history_summary(self):
        agent = self._create_agent()
        agent.add_to_history("user", "hello")
        summary = agent.get_history_summary()
        self.assertIn("1", summary)
        self.assertIn("test-agent", summary)

    def test_handle_tool_call_allowed(self):
        agent = self._create_agent()
        result = agent.handle_tool_call("tool-1", {"arg": "val"})
        self.assertEqual(result["result"], "executed tool-1")

    def test_handle_tool_call_not_allowed(self):
        agent = self._create_agent()
        result = agent.handle_tool_call("tool-unknown", {"arg": "val"})
        self.assertIn("error", result)
        self.assertIn("不在允许列表中", result["error"])

    def test_send_message_not_implemented(self):
        agent = self._create_agent()
        with self.assertRaises(NotImplementedError):
            agent.send_message("hello")


if __name__ == '__main__':
    unittest.main()
