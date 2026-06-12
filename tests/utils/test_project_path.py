"""
project_path 单元测试

测试上传路径工具函数的纯逻辑方法。
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.project_path import (
    get_upload_dir,
    get_upload_subdir,
    get_upload_temp_dir,
    generate_upload_filename,
    build_upload_url,
    resolve_upload_url_to_local_path,
    UploadFilenameInfo,
)


class TestGetUploadDir(unittest.TestCase):
    """测试 get_upload_dir()"""

    @patch('utils.project_path.get_project_path')
    def test_returns_absolute_path(self, mock_get_project_path):
        """返回项目根目录下的 upload 目录绝对路径"""
        mock_get_project_path.return_value = '/project/upload'
        result = get_upload_dir()
        self.assertEqual(result, '/project/upload')
        mock_get_project_path.assert_called_once_with('upload')


class TestGetUploadSubdir(unittest.TestCase):
    """测试 get_upload_subdir()"""

    @patch('utils.project_path.get_upload_dir')
    @patch('os.makedirs')
    def test_single_part(self, mock_makedirs, mock_get_upload_dir):
        """单级子目录"""
        mock_get_upload_dir.return_value = '/project/upload'
        result = get_upload_subdir('temp')
        self.assertEqual(result, os.path.join('/project/upload', 'temp'))
        mock_makedirs.assert_called_once()

    @patch('utils.project_path.get_upload_dir')
    @patch('os.makedirs')
    def test_multiple_parts(self, mock_makedirs, mock_get_upload_dir):
        """多级子目录"""
        mock_get_upload_dir.return_value = '/project/upload'
        result = get_upload_subdir('temp', '20250501')
        expected = os.path.join('/project/upload', 'temp', '20250501')
        self.assertEqual(result, expected)
        mock_makedirs.assert_called_once()

    @patch('utils.project_path.get_upload_dir')
    @patch('os.makedirs')
    def test_ensure_false(self, mock_makedirs, mock_get_upload_dir):
        """ensure=False 时不创建目录"""
        mock_get_upload_dir.return_value = '/project/upload'
        result = get_upload_subdir('temp', ensure=False)
        self.assertEqual(result, os.path.join('/project/upload', 'temp'))
        mock_makedirs.assert_not_called()


class TestGetUploadTempDir(unittest.TestCase):
    """测试 get_upload_temp_dir()"""

    @patch('utils.project_path.get_upload_subdir')
    def test_default_date(self, mock_get_upload_subdir):
        """默认使用当天日期"""
        mock_get_upload_subdir.return_value = '/project/upload/temp/20250501'
        with patch('utils.project_path.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 5, 1, 14, 30, 0)
            mock_datetime.strftime = datetime.strftime
            result = get_upload_temp_dir()
        self.assertEqual(result, '/project/upload/temp/20250501')

    @patch('utils.project_path.get_upload_subdir')
    def test_custom_date(self, mock_get_upload_subdir):
        """指定日期"""
        mock_get_upload_subdir.return_value = '/project/upload/temp/20250601'
        result = get_upload_temp_dir('20250601')
        self.assertEqual(result, '/project/upload/temp/20250601')


class TestGenerateUploadFilename(unittest.TestCase):
    """测试 generate_upload_filename()"""

    def test_default_params(self):
        """默认参数生成文件名"""
        with patch('utils.project_path.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 5, 1, 14, 30, 25)
            mock_datetime.strftime = datetime.strftime
            result = generate_upload_filename()

        self.assertIsInstance(result, UploadFilenameInfo)
        self.assertTrue(result.filename.startswith('upload_20250501_143025_'))
        self.assertTrue(result.filename.endswith('.bin'))
        self.assertEqual(result.timestamp, '20250501_143025')
        self.assertEqual(len(result.unique_id), 8)

    def test_custom_prefix_and_extension(self):
        """自定义前缀和扩展名"""
        with patch('utils.project_path.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 5, 1, 14, 30, 25)
            mock_datetime.strftime = datetime.strftime
            result = generate_upload_filename(prefix='media', extension='.png')

        self.assertTrue(result.filename.startswith('media_20250501_143025_'))
        self.assertTrue(result.filename.endswith('.png'))

    def test_unique_id_length(self):
        """自定义 UUID 长度"""
        with patch('utils.project_path.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 5, 1, 14, 30, 25)
            mock_datetime.strftime = datetime.strftime
            result = generate_upload_filename(unique_id_len=12)

        self.assertEqual(len(result.unique_id), 12)


class TestBuildUploadUrl(unittest.TestCase):
    """测试 build_upload_url()"""

    def test_without_host(self):
        """不带 host 构建 URL"""
        result = build_upload_url('temp', '20250501', 'upload_xxx.png')
        self.assertEqual(result, '/upload/temp/20250501/upload_xxx.png')

    def test_with_host(self):
        """带 host 构建 URL"""
        result = build_upload_url('temp', '20250501', 'upload_xxx.png', host='https://example.com')
        self.assertEqual(result, 'https://example.com/upload/temp/20250501/upload_xxx.png')

    def test_host_with_trailing_slash(self):
        """host 末尾有斜杠"""
        result = build_upload_url('image.png', host='https://example.com/')
        self.assertEqual(result, 'https://example.com/upload/image.png')

    def test_parts_with_slashes(self):
        """路径段包含斜杠"""
        result = build_upload_url('/temp/', '/20250501/', '/upload_xxx.png')
        self.assertEqual(result, '/upload/temp/20250501/upload_xxx.png')


class TestResolveUploadUrlToLocalPath(unittest.TestCase):
    """测试 resolve_upload_url_to_local_path()"""

    @patch('utils.project_path.get_upload_dir')
    def test_full_url(self, mock_get_upload_dir):
        """完整 URL 解析"""
        mock_get_upload_dir.return_value = '/project/upload'
        result = resolve_upload_url_to_local_path('https://example.com/upload/temp/image.png')
        self.assertEqual(result, os.path.join('/project/upload', 'temp', 'image.png'))

    @patch('utils.project_path.get_upload_dir')
    def test_path_with_upload_prefix(self, mock_get_upload_dir):
        """以 /upload/ 开头的路径"""
        mock_get_upload_dir.return_value = '/project/upload'
        result = resolve_upload_url_to_local_path('/upload/temp/image.png')
        self.assertEqual(result, os.path.join('/project/upload', 'temp', 'image.png'))

    @patch('utils.project_path.get_upload_dir')
    def test_relative_path(self, mock_get_upload_dir):
        """相对于 upload/ 的路径"""
        mock_get_upload_dir.return_value = '/project/upload'
        result = resolve_upload_url_to_local_path('temp/image.png')
        self.assertEqual(result, os.path.join('/project/upload', 'temp', 'image.png'))

    @patch('utils.project_path.get_upload_dir')
    def test_url_with_query_params(self, mock_get_upload_dir):
        """带查询参数的 URL"""
        mock_get_upload_dir.return_value = '/project/upload'
        result = resolve_upload_url_to_local_path('https://example.com/upload/temp/image.png?v=123')
        # urlparse 会保留查询参数在 path 中，但我们的实现只取 path 部分
        self.assertIn('/project/upload', result)


if __name__ == '__main__':
    unittest.main()
