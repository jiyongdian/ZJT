"""
MarketingPMAgent 单元测试

测试 script_writer_core/agents/marketing_pm_agent.py。
使用 mock 隔离 PMAgent 父类和其他依赖。
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)


class TestMarketingPMAgentInit(unittest.TestCase):
    """测试 MarketingPMAgent 初始化"""

    @patch('script_writer_core.agents.marketing_pm_agent.PMAgent.__init__')
    def test_missing_base_prompt_raises(self, mock_super_init):
        """缺少 base_prompt 抛出 ValueError"""
        from script_writer_core.agents.marketing_pm_agent import MarketingPMAgent
        mock_sop = MagicMock()
        with self.assertRaises(ValueError) as ctx:
            MarketingPMAgent(
                model="gpt-4",
                allowed_tools=[],
                task_manager=MagicMock(),
                file_manager=MagicMock(),
                tool_executor=MagicMock(),
                agents_config={},
                user_id="1",
                world_id="1",
                auth_token="token",
                base_prompt="",  # empty
                sop_loader=mock_sop,
            )
        self.assertIn("base_prompt", str(ctx.exception))

    @patch('script_writer_core.agents.marketing_pm_agent.PMAgent.__init__')
    def test_missing_sop_loader_raises(self, mock_super_init):
        """缺少 sop_loader 抛出 ValueError"""
        from script_writer_core.agents.marketing_pm_agent import MarketingPMAgent
        with self.assertRaises(ValueError) as ctx:
            MarketingPMAgent(
                model="gpt-4",
                allowed_tools=[],
                task_manager=MagicMock(),
                file_manager=MagicMock(),
                tool_executor=MagicMock(),
                agents_config={},
                user_id="1",
                world_id="1",
                auth_token="token",
                base_prompt="marketing prompt",
                sop_loader=None,  # missing
            )
        self.assertIn("sop_loader", str(ctx.exception))

    @patch('script_writer_core.agents.marketing_pm_agent.PMAgent.__init__')
    def test_successful_init(self, mock_super_init):
        """正常初始化"""
        from script_writer_core.agents.marketing_pm_agent import MarketingPMAgent
        mock_sop = MagicMock()

        agent = MarketingPMAgent(
            model="gpt-4",
            allowed_tools=["tool-1"],
            task_manager=MagicMock(),
            file_manager=MagicMock(),
            tool_executor=MagicMock(),
            agents_config={},
            user_id="1",
            world_id="1",
            auth_token="token",
            base_prompt="marketing prompt",
            sop_loader=mock_sop,
        )

        # 验证调用了父类构造函数，且 skip_env_context=True
        mock_super_init.assert_called_once()
        call_kwargs = mock_super_init.call_args[1]
        self.assertTrue(call_kwargs.get('skip_env_context'))
        self.assertEqual(call_kwargs.get('skill_names'), [])
        self.assertEqual(call_kwargs.get('base_prompt'), "marketing prompt")
        self.assertEqual(agent.agent_id, "marketing_pm_agent")


class TestBuildSystemPrompt(unittest.TestCase):
    """测试 _build_system_prompt"""

    def _create_agent(self, base_prompt="test prompt"):
        from script_writer_core.agents.marketing_pm_agent import MarketingPMAgent
        with patch('script_writer_core.agents.marketing_pm_agent.PMAgent.__init__'):
            agent = MarketingPMAgent(
                model="gpt-4",
                allowed_tools=[],
                task_manager=MagicMock(),
                file_manager=MagicMock(),
                tool_executor=MagicMock(),
                agents_config={},
                user_id="1",
                world_id="1",
                auth_token="token",
                base_prompt=base_prompt,
                sop_loader=MagicMock(),
            )
        agent._custom_base_prompt = base_prompt
        return agent

    def test_missing_custom_prompt_raises(self):
        """_custom_base_prompt 为空时抛出 ValueError"""
        agent = self._create_agent(base_prompt="valid")
        agent._custom_base_prompt = ""
        with self.assertRaises(ValueError):
            agent._build_system_prompt([])

    def test_empty_skill_names_returns_base_prompt(self):
        """空 skill_names 直接返回 base_prompt"""
        agent = self._create_agent(base_prompt="my marketing prompt")
        result = agent._build_system_prompt([])
        expected = (
            "my marketing prompt\n\n"
            "**重要约束**：向用户提问时必须使用 ask_user 工具，"
            "禁止以纯文本方式提问（纯文本提问用户无法收到交互弹框）"
        )
        self.assertEqual(result, expected)

    def test_skill_loading_success(self):
        """成功加载 skill 时追加到 prompt"""
        agent = self._create_agent(base_prompt="base")
        mock_skill_loader = MagicMock()
        mock_skill_loader.get_skill_prompt.return_value = "skill content here"
        agent.skill_loader = mock_skill_loader

        result = agent._build_system_prompt(["my-skill"])
        self.assertIn("base", result)
        self.assertIn("skill content here", result)
        self.assertIn("my-skill", result)

    def test_skill_loading_failure_skips(self):
        """skill 加载失败时跳过"""
        agent = self._create_agent(base_prompt="base")
        mock_skill_loader = MagicMock()
        mock_skill_loader.get_skill_prompt.return_value = None
        agent.skill_loader = mock_skill_loader

        result = agent._build_system_prompt(["bad-skill"])
        expected = (
            "base\n\n"
            "**重要约束**：向用户提问时必须使用 ask_user 工具，"
            "禁止以纯文本方式提问（纯文本提问用户无法收到交互弹框）"
        )
        self.assertEqual(result, expected)


class TestBuildContextForExpert(unittest.TestCase):
    """测试 _build_context_for_expert"""

    def _create_agent(self, agents_config=None):
        from script_writer_core.agents.marketing_pm_agent import MarketingPMAgent
        with patch('script_writer_core.agents.marketing_pm_agent.PMAgent.__init__'):
            agent = MarketingPMAgent(
                model="gpt-4",
                allowed_tools=[],
                task_manager=MagicMock(),
                file_manager=MagicMock(),
                tool_executor=MagicMock(),
                agents_config=agents_config or {},
                user_id="1",
                world_id="1",
                auth_token="token",
                base_prompt="test prompt",
                sop_loader=MagicMock(),
            )
        agent.agents_config = agents_config or {}
        return agent

    def test_summary_only_mode(self):
        """summary_only=True 时提供摘要模式上下文"""
        agent = self._create_agent(agents_config={
            "expert_agents": {
                "image-designer": {"summary_only": True}
            }
        })
        result = agent._build_context_for_expert("image-designer", "user1", "world1")
        self.assertIn("image-designer", result)
        self.assertIn("摘要模式", result)

    def test_full_mode(self):
        """summary_only=False 时提供完整模式上下文"""
        agent = self._create_agent(agents_config={
            "expert_agents": {
                "video-gen": {"summary_only": False}
            }
        })
        result = agent._build_context_for_expert("video-gen", "user1", "world1")
        self.assertIn("完整模式", result)

    def test_default_is_full_mode(self):
        """默认 summary_only=False"""
        agent = self._create_agent(agents_config={
            "expert_agents": {
                "some-skill": {}
            }
        })
        result = agent._build_context_for_expert("some-skill")
        self.assertIn("完整模式", result)

    def test_missing_expert_config(self):
        """缺少专家配置时使用默认"""
        agent = self._create_agent(agents_config={})
        result = agent._build_context_for_expert("unknown-skill")
        self.assertIn("unknown-skill", result)
        self.assertIn("完整模式", result)


if __name__ == '__main__':
    unittest.main()
