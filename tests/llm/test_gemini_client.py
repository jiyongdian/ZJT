"""
GeminiClient 单元测试

测试 _convert_to_gemini_format 的多模态分支。
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from llm.gemini_client import GeminiClient


class TestConvertToGeminiFormat(unittest.TestCase):
    """测试 OpenAI 格式消息转换为 Gemini 格式"""

    def setUp(self):
        with patch.object(GeminiClient, '_refresh_config'):
            self.client = GeminiClient()

    def test_system_message(self):
        messages = [{"role": "system", "content": "You are helpful"}]
        result = self.client._convert_to_gemini_format(messages)
        self.assertEqual(result["systemInstruction"], {"parts": [{"text": "You are helpful"}]})
        self.assertEqual(result["contents"], [])

    def test_simple_user_text(self):
        messages = [{"role": "user", "content": "hello"}]
        result = self.client._convert_to_gemini_format(messages)
        self.assertEqual(len(result["contents"]), 1)
        self.assertEqual(result["contents"][0]["role"], "user")
        self.assertEqual(result["contents"][0]["parts"], [{"text": "hello"}])

    def test_multimodal_base64_image(self):
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "describe this"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,ABC123"}}
            ]
        }]
        result = self.client._convert_to_gemini_format(messages)
        parts = result["contents"][0]["parts"]
        self.assertEqual(parts[0], {"text": "describe this"})
        self.assertEqual(parts[1], {
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": "ABC123"
            }
        })

    def test_multimodal_external_url(self):
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "https://example.com/img.jpg"}}
            ]
        }]
        result = self.client._convert_to_gemini_format(messages)
        parts = result["contents"][0]["parts"]
        self.assertEqual(parts[0], {
            "fileData": {
                "mimeType": "image/jpeg",
                "fileUri": "https://example.com/img.jpg"
            }
        })

    def test_tool_message(self):
        messages = [{
            "role": "tool",
            "name": "my_tool",
            "content": '{"result": "ok"}'
        }]
        result = self.client._convert_to_gemini_format(messages)
        self.assertEqual(result["contents"][0]["role"], "function")
        self.assertEqual(result["contents"][0]["parts"][0], {
            "functionResponse": {
                "name": "my_tool",
                "response": {"result": "ok"}
            }
        })

    def test_tool_message_with_dict_content(self):
        messages = [{
            "role": "tool",
            "name": "my_tool",
            "content": {"result": "ok", "data": 123}
        }]
        result = self.client._convert_to_gemini_format(messages)
        self.assertEqual(result["contents"][0]["parts"][0]["functionResponse"]["response"], {"result": "ok", "data": 123})

    def test_tools_conversion(self):
        messages = [{"role": "user", "content": "hi"}]
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取天气",
                "parameters": {"type": "object", "properties": {}}
            }
        }]
        result = self.client._convert_to_gemini_format(messages, tools=tools)
        self.assertIn("tools", result)
        self.assertEqual(result["tools"][0]["functionDeclarations"][0]["name"], "get_weather")

    def test_assistant_with_tool_calls(self):
        messages = [{
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "function": {
                    "name": "get_weather",
                    "arguments": '{"city": "Beijing"}'
                }
            }]
        }]
        result = self.client._convert_to_gemini_format(messages)
        parts = result["contents"][0]["parts"]
        self.assertEqual(parts[0]["functionCall"]["name"], "get_weather")
        self.assertEqual(parts[0]["functionCall"]["args"], {"city": "Beijing"})

    def test_assistant_text_with_thought_signature(self):
        messages = [{
            "role": "assistant",
            "content": "result",
            "thought_signature": "sig123"
        }]
        result = self.client._convert_to_gemini_format(messages)
        parts = result["contents"][0]["parts"]
        self.assertEqual(parts[0]["text"], "result")
        self.assertEqual(parts[0]["thoughtSignature"], "sig123")

    def test_consecutive_tool_messages_grouped(self):
        """测试连续 tool 消息是否被正确分组"""
        messages = [
            {"role": "tool", "name": "tool_a", "content": "result_a"},
            {"role": "tool", "name": "tool_b", "content": "result_b"},
        ]
        result = self.client._convert_to_gemini_format(messages)
        contents = result["contents"]
        # 第二个 tool 消息应该追加到同一个 function role 中
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]["role"], "function")
        self.assertEqual(len(contents[0]["parts"]), 2)

    def test_empty_messages(self):
        result = self.client._convert_to_gemini_format([])
        self.assertEqual(result["contents"], [])

    def test_unknown_role_ignored(self):
        """测试未知角色被忽略"""
        messages = [{"role": "unknown", "content": "test"}]
        result = self.client._convert_to_gemini_format(messages)
        self.assertEqual(result["contents"], [])


if __name__ == '__main__':
    unittest.main()
