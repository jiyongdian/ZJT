"""
BaseAsyncDriver 脱敏方法单元测试

测试 _mask_sensitive_headers、_mask_sensitive_payload、_truncate_base64_in_response。
"""
import sys
import unittest
from unittest.mock import MagicMock

# Mock 依赖
sys.modules['utils.logger_config'] = MagicMock()

from task.async_drivers.base_async_driver import BaseAsyncDriver


class _ConcreteDriver(BaseAsyncDriver):
    """测试用具体驱动"""
    async def submit_task(self, **kwargs):
        return {}

    async def check_status(self, project_id):
        return {}


class TestMaskSensitiveHeaders(unittest.TestCase):
    """测试 _mask_sensitive_headers()"""

    def setUp(self):
        self.driver = _ConcreteDriver("test_driver")

    def test_authorization_masked(self):
        """Authorization 头被脱敏"""
        headers = {"Authorization": "Bearer sk-1234567890abcdefghij"}
        result = self.driver._mask_sensitive_headers(headers)
        self.assertEqual(result["Authorization"], "Bearer sk-***ghij")

    def test_x_api_key_masked(self):
        """X-API-Key 头被脱敏（短值 <=20 字符直接替换为 ***）"""
        headers = {"X-API-Key": "ak-1234567890xyz"}  # 16 chars <= 20
        result = self.driver._mask_sensitive_headers(headers)
        self.assertEqual(result["X-API-Key"], "***")

    def test_api_key_masked(self):
        """api-key 头被脱敏（大小写不敏感）"""
        headers = {"api-key": "short"}
        result = self.driver._mask_sensitive_headers(headers)
        self.assertEqual(result["api-key"], "***")

    def test_normal_headers_unchanged(self):
        """普通头不脱敏"""
        headers = {"Content-Type": "application/json", "Accept": "*/*"}
        result = self.driver._mask_sensitive_headers(headers)
        self.assertEqual(result["Content-Type"], "application/json")
        self.assertEqual(result["Accept"], "*/*")

    def test_none_headers(self):
        """None 输入返回空 dict"""
        result = self.driver._mask_sensitive_headers(None)
        self.assertEqual(result, {})

    def test_empty_headers(self):
        """空 dict 返回空 dict"""
        result = self.driver._mask_sensitive_headers({})
        self.assertEqual(result, {})

    def test_original_not_modified(self):
        """脱敏不修改原始 dict"""
        headers = {"Authorization": "Bearer token123456"}
        self.driver._mask_sensitive_headers(headers)
        self.assertEqual(headers["Authorization"], "Bearer token123456")


class TestMaskSensitivePayload(unittest.TestCase):
    """测试 _mask_sensitive_payload()"""

    def setUp(self):
        self.driver = _ConcreteDriver("test_driver")

    def test_apikey_masked(self):
        """apikey 字段被脱敏"""
        payload = {"apikey": "sk-1234567890abcdef"}
        result = self.driver._mask_sensitive_payload(payload)
        self.assertEqual(result["apikey"], "sk-1***cdef")

    def test_api_key_masked(self):
        """api_key 字段被脱敏"""
        payload = {"api_key": "short_val"}
        result = self.driver._mask_sensitive_payload(payload)
        self.assertEqual(result["api_key"], "***")

    def test_nested_dict_masked(self):
        """嵌套 dict 中的敏感字段也被脱敏（前4+后4）"""
        payload = {
            "config": {
                "secret": "my_secret_value_123",  # 18 chars > 10
                "normal": "visible"
            }
        }
        result = self.driver._mask_sensitive_payload(payload)
        self.assertEqual(result["config"]["secret"], "my_s***_123")
        self.assertEqual(result["config"]["normal"], "visible")

    def test_list_with_dicts(self):
        """list 中的 dict 也被递归处理"""
        payload = {
            "items": [
                {"token": "tok_12345678"},  # 12 chars > 10 → tok_***5678
                {"name": "safe_value"}
            ]
        }
        result = self.driver._mask_sensitive_payload(payload)
        self.assertEqual(result["items"][0]["token"], "tok_***5678")
        self.assertEqual(result["items"][1]["name"], "safe_value")

    def test_normal_fields_unchanged(self):
        """非敏感字段不脱敏"""
        payload = {"prompt": "hello", "model": "gpt-4", "count": 10}
        result = self.driver._mask_sensitive_payload(payload)
        self.assertEqual(result, payload)

    def test_none_payload(self):
        """None 输入返回空 dict"""
        result = self.driver._mask_sensitive_payload(None)
        self.assertEqual(result, {})

    def test_empty_payload(self):
        """空 dict 返回空 dict"""
        result = self.driver._mask_sensitive_payload({})
        self.assertEqual(result, {})

    def test_all_sensitive_keys(self):
        """所有已知的敏感 key 都被处理"""
        payload = {
            "apikey": "a",
            "api_key": "b",
            "secret": "c",
            "password": "d",
            "token": "e",
            "key": "f"
        }
        result = self.driver._mask_sensitive_payload(payload)
        for key in payload:
            self.assertEqual(result[key], "***")


class TestTruncateBase64InResponse(unittest.TestCase):
    """测试 _truncate_base64_in_response()"""

    def setUp(self):
        self.driver = _ConcreteDriver("test_driver")

    def test_inline_data_masked(self):
        """inlineData 中的 base64 图片数据被遮盖"""
        data = {
            "inlineData": {
                "mimeType": "image/png",
                "data": "iVBORw0KGgo..." * 100
            }
        }
        result = self.driver._truncate_base64_in_response(data)
        self.assertEqual(result["inlineData"]["mimeType"], "image/png")
        self.assertEqual(result["inlineData"]["data"], "[base64 image data masked]")

    def test_long_base64_data_masked(self):
        """长 data 字段（base64 格式）被截断"""
        base64_str = "aBcDeFgHiJkLmNoPqRsTuVwXyZ" * 50  # > 50 chars, all alphanumeric
        data = {"data": base64_str}
        result = self.driver._truncate_base64_in_response(data)
        self.assertIn("base64 data", result["data"])
        self.assertIn("masked", result["data"])

    def test_short_data_unchanged(self):
        """短 data 字段不被截断"""
        data = {"data": "short value"}
        result = self.driver._truncate_base64_in_response(data)
        self.assertEqual(result["data"], "short value")

    def test_b64_json_masked(self):
        """b64_json 字段被遮盖"""
        data = {"b64_json": "a" * 100}
        result = self.driver._truncate_base64_in_response(data)
        self.assertEqual(result["b64_json"], "[b64_json masked]")

    def test_thought_signature_removed(self):
        """thoughtSignature 字段被移除"""
        data = {"thoughtSignature": "abc123", "other": "keep"}
        result = self.driver._truncate_base64_in_response(data)
        self.assertNotIn("thoughtSignature", result)
        self.assertEqual(result["other"], "keep")

    def test_nested_dict_truncated(self):
        """嵌套 dict 递归处理"""
        data = {
            "outer": {
                "b64_json": "x" * 100
            }
        }
        result = self.driver._truncate_base64_in_response(data)
        self.assertEqual(result["outer"]["b64_json"], "[b64_json masked]")

    def test_list_truncated(self):
        """list 中的元素递归处理"""
        data = [
            {"b64_json": "a" * 100},
            {"normal": "value"}
        ]
        result = self.driver._truncate_base64_in_response(data)
        self.assertEqual(result[0]["b64_json"], "[b64_json masked]")
        self.assertEqual(result[1]["normal"], "value")

    def test_scalar_values_unchanged(self):
        """标量值不变"""
        self.assertEqual(self.driver._truncate_base64_in_response("hello"), "hello")
        self.assertEqual(self.driver._truncate_base64_in_response(42), 42)
        self.assertIsNone(self.driver._truncate_base64_in_response(None))

    def test_empty_dict(self):
        """空 dict 返回空 dict"""
        result = self.driver._truncate_base64_in_response({})
        self.assertEqual(result, {})

    def test_data_with_non_base64_content(self):
        """data 字段内容非 base64 格式时保留"""
        data = {"data": "This is a normal text with spaces and punctuation!"}
        result = self.driver._truncate_base64_in_response(data)
        # 这个字符串包含空格和标点，不是纯 base64，所以保留原样
        self.assertEqual(result["data"], "This is a normal text with spaces and punctuation!")


if __name__ == '__main__':
    unittest.main()
