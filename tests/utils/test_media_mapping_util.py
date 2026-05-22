"""
media_mapping_util 单元测试

测试 extract_local_path_from_url 的纯函数逻辑。
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

# Mock 依赖模块
sys.modules['utils.project_path'] = MagicMock()

from utils.media_mapping_util import extract_local_path_from_url


class TestExtractLocalPathFromUrl(unittest.TestCase):
    """测试 extract_local_path_from_url()"""

    def test_localhost_url(self):
        """本地 URL 提取路径"""
        result = extract_local_path_from_url("http://localhost:8000/upload/character/pic/abc.png")
        self.assertEqual(result, "upload/character/pic/abc.png")

    def test_ip_url(self):
        """IP 地址 URL 提取路径"""
        result = extract_local_path_from_url("http://192.168.1.1:9000/upload/character/voice/rh_voice.wav")
        self.assertEqual(result, "upload/character/voice/rh_voice.wav")

    def test_relative_path(self):
        """以 /upload/ 开头的相对路径"""
        result = extract_local_path_from_url("/upload/character/pic/abc.png")
        self.assertEqual(result, "upload/character/pic/abc.png")

    def test_external_cdn_url(self):
        """外部 CDN URL 返回 None"""
        result = extract_local_path_from_url("https://external-cdn.com/image.png")
        self.assertIsNone(result)

    def test_http_external_url(self):
        """HTTP 外部 URL（不含 /upload/ 前缀）返回 None"""
        result = extract_local_path_from_url("http://example.com/other/path/image.png")
        self.assertIsNone(result)

    def test_empty_string(self):
        """空字符串返回 None"""
        result = extract_local_path_from_url("")
        self.assertIsNone(result)

    def test_none_input(self):
        """None 输入返回 None"""
        result = extract_local_path_from_url(None)
        self.assertIsNone(result)

    def test_non_string_input(self):
        """非字符串输入返回 None"""
        result = extract_local_path_from_url(12345)
        self.assertIsNone(result)

    def test_url_with_query_params(self):
        """带查询参数的本地 URL"""
        result = extract_local_path_from_url("http://localhost:8000/upload/img/a.png?v=1&t=2")
        self.assertEqual(result, "upload/img/a.png")

    def test_upload_only_path(self):
        """只有 /upload/ 前缀但无后续路径"""
        result = extract_local_path_from_url("/upload/")
        self.assertEqual(result, "upload/")

    def test_path_not_starting_with_upload(self):
        """路径不以 /upload/ 开头返回 None"""
        result = extract_local_path_from_url("http://localhost:8000/static/image.png")
        self.assertIsNone(result)

    def test_deep_nested_path(self):
        """深层嵌套路径"""
        result = extract_local_path_from_url("http://localhost:8000/upload/a/b/c/d/file.jpg")
        self.assertEqual(result, "upload/a/b/c/d/file.jpg")


if __name__ == '__main__':
    unittest.main()
