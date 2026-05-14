"""
MCP 工具校验函数单元测试

测试 validate_name_for_filename 和 validate_image_url 的纯函数逻辑。
"""
import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from script_writer_core.mcp_tool import validate_name_for_filename, validate_image_url


class TestValidateNameForFilename(unittest.TestCase):
    """测试 validate_name_for_filename"""

    def test_valid_chinese_name(self):
        result = validate_name_for_filename("张三")
        self.assertTrue(result['valid'])
        self.assertEqual(result['cleaned_name'], '张三')
        self.assertIsNone(result['error'])

    def test_valid_english_name(self):
        result = validate_name_for_filename("Alice")
        self.assertTrue(result['valid'])
        self.assertEqual(result['cleaned_name'], 'Alice')

    def test_valid_mixed_name(self):
        result = validate_name_for_filename("Alice_张三.v2")
        self.assertTrue(result['valid'])
        self.assertEqual(result['cleaned_name'], 'Alice_张三.v2')

    def test_valid_with_underscore(self):
        result = validate_name_for_filename("user_name_001")
        self.assertTrue(result['valid'])
        self.assertEqual(result['cleaned_name'], 'user_name_001')

    def test_empty_name(self):
        result = validate_name_for_filename("")
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], '名称不能为空')
        self.assertEqual(result['cleaned_name'], '')

    def test_whitespace_only(self):
        result = validate_name_for_filename("   ")
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], '名称不能为空')

    def test_none_name(self):
        result = validate_name_for_filename(None)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], '名称不能为空')

    def test_invalid_chars_with_suggestion(self):
        result = validate_name_for_filename("Alice@123")
        self.assertFalse(result['valid'])
        self.assertIn('只能包含中文', result['error'])
        self.assertEqual(result['cleaned_name'], 'Alice123')

    def test_all_invalid_chars(self):
        result = validate_name_for_filename("@#$%^")
        self.assertFalse(result['valid'])
        self.assertIn('必须包含至少一个', result['error'])
        self.assertEqual(result['cleaned_name'], '')

    def test_custom_field_name(self):
        result = validate_name_for_filename("", field_name="角色名称")
        self.assertIn('角色名称', result['error'])

    def test_space_in_name(self):
        result = validate_name_for_filename("Alice 123")
        self.assertFalse(result['valid'])
        self.assertEqual(result['cleaned_name'], 'Alice123')

    def test_number_only(self):
        result = validate_name_for_filename("12345")
        self.assertTrue(result['valid'])
        self.assertEqual(result['cleaned_name'], '12345')

    def test_chinese_number_mix(self):
        result = validate_name_for_filename("角色001")
        self.assertTrue(result['valid'])
        self.assertEqual(result['cleaned_name'], '角色001')


class TestValidateImageUrl(unittest.TestCase):
    """测试 validate_image_url"""

    def test_valid_http_url(self):
        result = validate_image_url("http://example.com/image.jpg")
        self.assertTrue(result['valid'])
        self.assertIsNone(result['error'])

    def test_valid_https_url(self):
        result = validate_image_url("https://cdn.example.com/path/to/image.png?v=123")
        self.assertTrue(result['valid'])

    def test_valid_localhost(self):
        result = validate_image_url("http://localhost:8080/image.jpg")
        self.assertTrue(result['valid'])

    def test_valid_ip(self):
        result = validate_image_url("http://192.168.1.1:9000/upload/abc.png")
        self.assertTrue(result['valid'])

    def test_missing_protocol(self):
        result = validate_image_url("example.com/image.jpg")
        self.assertFalse(result['valid'])
        self.assertIn('http://', result['error'])

    def test_ftp_protocol(self):
        result = validate_image_url("ftp://example.com/image.jpg")
        self.assertFalse(result['valid'])

    def test_empty_string(self):
        result = validate_image_url("")
        self.assertFalse(result['valid'])

    def test_none_value(self):
        result = validate_image_url(None)
        self.assertFalse(result['valid'])
        self.assertIn('字符串类型', result['error'])

    def test_non_string_value(self):
        result = validate_image_url(12345)
        self.assertFalse(result['valid'])
        self.assertIn('字符串类型', result['error'])

    def test_invalid_url_format(self):
        result = validate_image_url("http://")
        self.assertFalse(result['valid'])
        self.assertIn('URL格式不正确', result['error'])

    def test_custom_field_name(self):
        result = validate_image_url("invalid", field_name="reference_image")
        self.assertIn('reference_image', result['error'])

    def test_url_with_path_and_query(self):
        result = validate_image_url("https://example.com/images/photo.jpg?size=large&token=abc")
        self.assertTrue(result['valid'])

    def test_url_with_fragment(self):
        result = validate_image_url("https://example.com/image.png#section")
        self.assertTrue(result['valid'])


if __name__ == '__main__':
    unittest.main()
