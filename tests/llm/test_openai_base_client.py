"""
OpenAIBaseClient 单元测试

测试请求 payload 中的 base64 图片脱敏（截断）逻辑。
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from llm.openai_base_client import OpenAIBaseClient


class TestableOpenAIClient(OpenAIBaseClient):
    """测试用子类，不调用真实配置"""
    def _refresh_config(self):
        self.api_key = "sk-test12345678"
        self.base_url = "http://localhost:8080"
        self.vendor_name = "test"
        self.thinking_mode = None


class TestPayloadSanitization(unittest.TestCase):
    """测试日志脱敏逻辑"""

    def test_base64_image_truncated(self):
        """测试 base64 图片数据在日志中被截断"""
        with patch('llm.openai_base_client._get_llm_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            with patch('llm.openai_base_client.OpenAI') as mock_openai_cls:
                mock_client = MagicMock()
                mock_openai_cls.return_value = mock_client
                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = "hi"
                mock_completion.choices[0].message.tool_calls = None
                mock_completion.usage = None
                mock_client.chat.completions.create.return_value = mock_completion

                client = TestableOpenAIClient()
                base64_data = "data:image/jpeg;base64," + "A" * 500
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "describe this"},
                            {"type": "image_url", "image_url": {"url": base64_data}}
                        ]
                    }
                ]
                client.call_api("gpt-4", messages=messages)

                # 检查日志中是否包含截断标记
                found_truncated = False
                for call in mock_logger.info.call_args_list:
                    args = call[0]
                    if args and isinstance(args[0], str) and "base64 truncated" in args[0]:
                        found_truncated = True
                        break
                self.assertTrue(found_truncated, "base64 图片数据应在日志中被截断")

    def test_short_base64_not_truncated(self):
        """测试短 base64 数据不被截断"""
        with patch('llm.openai_base_client._get_llm_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            with patch('llm.openai_base_client.OpenAI') as mock_openai_cls:
                mock_client = MagicMock()
                mock_openai_cls.return_value = mock_client
                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = "hi"
                mock_completion.choices[0].message.tool_calls = None
                mock_completion.usage = None
                mock_client.chat.completions.create.return_value = mock_completion

                client = TestableOpenAIClient()
                base64_data = "data:image/jpeg;base64,SHORT"
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": base64_data}}
                        ]
                    }
                ]
                client.call_api("gpt-4", messages=messages)

                found_original = False
                for call in mock_logger.info.call_args_list:
                    args = call[0]
                    if args and isinstance(args[0], str) and "SHORT" in args[0] and "base64 truncated" not in args[0]:
                        found_original = True
                        break
                self.assertTrue(found_original, "短 base64 数据应保持原样")

    def test_long_text_truncated(self):
        """测试超长文本在日志中被截断"""
        with patch('llm.openai_base_client._get_llm_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            with patch('llm.openai_base_client.OpenAI') as mock_openai_cls:
                mock_client = MagicMock()
                mock_openai_cls.return_value = mock_client
                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = "hi"
                mock_completion.choices[0].message.tool_calls = None
                mock_completion.usage = None
                mock_client.chat.completions.create.return_value = mock_completion

                client = TestableOpenAIClient()
                long_text = "A" * 2500
                messages = [{"role": "user", "content": long_text}]
                client.call_api("gpt-4", messages=messages)

                found_truncated = False
                for call in mock_logger.info.call_args_list:
                    args = call[0]
                    if args and isinstance(args[0], str) and "truncated" in args[0] and "total 2500" in args[0]:
                        found_truncated = True
                        break
                self.assertTrue(found_truncated, "超长文本应在日志中被截断")

    def test_original_kwargs_unchanged(self):
        """测试原始 kwargs 不会被脱敏逻辑修改"""
        with patch('llm.openai_base_client._get_llm_logger'):
            with patch('llm.openai_base_client.OpenAI') as mock_openai_cls:
                mock_client = MagicMock()
                mock_openai_cls.return_value = mock_client
                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = "hi"
                mock_completion.choices[0].message.tool_calls = None
                mock_completion.usage = None
                mock_client.chat.completions.create.return_value = mock_completion

                client = TestableOpenAIClient()
                base64_data = "data:image/jpeg;base64," + "A" * 500
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": base64_data}}
                        ]
                    }
                ]
                client.call_api("gpt-4", messages=messages)

                call_kwargs = mock_client.chat.completions.create.call_args.kwargs
                original_url = call_kwargs["messages"][0]["content"][0]["image_url"]["url"]
                self.assertEqual(len(original_url), len(base64_data))
                self.assertTrue(original_url.endswith("A" * 500))

    def test_no_messages_no_crash(self):
        """测试空消息列表不崩溃"""
        with patch('llm.openai_base_client._get_llm_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            with patch('llm.openai_base_client.OpenAI') as mock_openai_cls:
                mock_client = MagicMock()
                mock_openai_cls.return_value = mock_client
                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = "hi"
                mock_completion.choices[0].message.tool_calls = None
                mock_completion.usage = None
                mock_client.chat.completions.create.return_value = mock_completion

                client = TestableOpenAIClient()
                client.call_api("gpt-4", messages=[])
                mock_client.chat.completions.create.assert_called_once()


    def test_agent_id_and_reasoning_content_logged(self):
        with patch('llm.openai_base_client._get_llm_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            with patch('llm.openai_base_client.OpenAI') as mock_openai_cls:
                mock_client = MagicMock()
                mock_openai_cls.return_value = mock_client
                mock_completion = MagicMock()
                mock_completion.choices = [MagicMock()]
                mock_completion.choices[0].message.content = "done"
                mock_completion.choices[0].message.tool_calls = None
                mock_completion.choices[0].message.reasoning_content = "expert private reasoning trace"
                mock_completion.usage = None
                mock_client.chat.completions.create.return_value = mock_completion

                client = TestableOpenAIClient()
                client.call_api(
                    "gpt-4",
                    messages=[{"role": "user", "content": "hello"}],
                    agent_id="expert_marketing-image",
                    agent_scope="expert",
                )

                logged = "\n".join(
                    str(call.args[0])
                    for call in mock_logger.info.call_args_list
                    if call.args
                )
                self.assertIn("Agent: expert_marketing-image", logged)
                self.assertIn("Agent scope: expert", logged)
                self.assertIn("expert private reasoning trace", logged)


if __name__ == '__main__':
    unittest.main()
