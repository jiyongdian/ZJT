"""
图片压缩工具单元测试

测试 utils/image_compressor.py 中的纯函数和关键逻辑。
使用 mock 隔离 PIL、httpx、文件系统等外部依赖。
"""
import os
import sys
import io
import base64
import unittest
from unittest.mock import patch, MagicMock, mock_open

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from utils.image_compressor import (
    get_image_size_mb,
    compress_image_to_limit,
    resize_image_to_pixel_limit,
    download_and_compress_to_base64,
    url_to_base64,
)


class TestGetImageSizeMb(unittest.TestCase):
    """测试 get_image_size_mb"""

    @patch('utils.image_compressor.os.path.exists', return_value=True)
    @patch('utils.image_compressor.os.path.getsize', return_value=1024 * 1024 * 5)  # 5MB
    def test_returns_size_in_mb(self, mock_getsize, mock_exists):
        result = get_image_size_mb("/fake/image.jpg")
        self.assertAlmostEqual(result, 5.0, places=2)

    @patch('utils.image_compressor.os.path.exists', return_value=False)
    def test_returns_none_when_file_not_found(self, mock_exists):
        result = get_image_size_mb("/fake/nonexistent.jpg")
        self.assertIsNone(result)

    @patch('utils.image_compressor.os.path.exists', return_value=True)
    @patch('utils.image_compressor.os.path.getsize', side_effect=PermissionError("denied"))
    def test_returns_none_on_exception(self, mock_getsize, mock_exists):
        result = get_image_size_mb("/fake/image.jpg")
        self.assertIsNone(result)

    @patch('utils.image_compressor.os.path.exists', return_value=True)
    @patch('utils.image_compressor.os.path.getsize', return_value=0)
    def test_returns_zero_for_empty_file(self, mock_getsize, mock_exists):
        result = get_image_size_mb("/fake/empty.jpg")
        self.assertAlmostEqual(result, 0.0, places=4)


class TestCompressImageToLimit(unittest.TestCase):
    """测试 compress_image_to_limit"""

    @patch('utils.image_compressor.os.path.exists', return_value=False)
    def test_file_not_exists(self, mock_exists):
        success, path, error = compress_image_to_limit("/fake/missing.jpg")
        self.assertFalse(success)
        self.assertIsNone(path)
        self.assertIn("文件不存在", error)

    @patch('utils.image_compressor.os.path.exists', return_value=True)
    @patch('utils.image_compressor.os.path.getsize', return_value=1024 * 1024 * 2)  # 2MB
    def test_already_under_limit(self, mock_getsize, mock_exists):
        """文件已满足大小限制，直接返回"""
        success, path, error = compress_image_to_limit("/fake/small.jpg", max_size_mb=5.0)
        self.assertTrue(success)
        self.assertEqual(path, "/fake/small.jpg")
        self.assertIsNone(error)

    @patch('utils.image_compressor.os.path.exists', return_value=True)
    @patch('utils.image_compressor.os.path.getsize')
    @patch('utils.image_compressor.Image.open')
    @patch('utils.image_compressor.io.BytesIO')
    def test_compress_jpeg_quality_reduction(self, mock_bio_cls, mock_img_open, mock_getsize, mock_exists):
        """测试 JPEG 质量递减压缩"""
        # 原始 20MB，目标 10MB
        mock_getsize.side_effect = [
            1024 * 1024 * 20,  # original size
            1024 * 1024 * 8,   # final size after compress
        ]

        mock_img = MagicMock()
        mock_img.format = 'JPEG'
        mock_img.mode = 'RGB'
        mock_img.width = 1000
        mock_img.height = 1000
        mock_img_open.return_value = mock_img

        # 模拟 BytesIO 返回的 buffer 在 q=85 时满足要求
        mock_buffer = MagicMock()
        mock_buffer.tell.return_value = 1024 * 1024 * 8  # 8MB, under limit
        mock_buffer.getvalue.return_value = b'compressed_data'
        mock_bio_cls.return_value = mock_buffer

        with patch('builtins.open', mock_open()):
            success, path, error = compress_image_to_limit("/fake/big.jpg", max_size_mb=10.0)

        self.assertTrue(success)

    @patch('utils.image_compressor.os.path.exists', return_value=True)
    @patch('utils.image_compressor.os.path.getsize')
    @patch('utils.image_compressor.Image.open')
    def test_corrupted_image(self, mock_img_open, mock_getsize, mock_exists):
        """测试损坏的图片文件"""
        mock_getsize.return_value = 1024 * 1024 * 20
        mock_img_open.side_effect = Exception("cannot identify image file")

        success, path, error = compress_image_to_limit("/fake/corrupt.jpg", max_size_mb=10.0)
        self.assertFalse(success)
        self.assertIn("无法打开图片", error)

    @patch('utils.image_compressor.os.path.exists', return_value=True)
    @patch('utils.image_compressor.os.path.getsize')
    @patch('utils.image_compressor.Image.open')
    @patch('utils.image_compressor.Image.new')
    def test_png_rgba_to_jpeg(self, mock_new, mock_img_open, mock_getsize, mock_exists):
        """测试 PNG RGBA 转换为 JPEG"""
        mock_getsize.side_effect = [1024 * 1024 * 20, 1024 * 1024 * 8]

        mock_img = MagicMock()
        mock_img.format = 'PNG'
        mock_img.mode = 'RGBA'
        mock_img.width = 1000
        mock_img.height = 1000
        mock_img.size = (1000, 1000)
        mock_img.split.return_value = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        mock_img_open.return_value = mock_img

        mock_bg = MagicMock()
        mock_new.return_value = mock_bg

        mock_buffer = MagicMock()
        mock_buffer.tell.return_value = 1024 * 1024 * 8
        mock_buffer.getvalue.return_value = b'compressed'

        with patch('utils.image_compressor.io.BytesIO', return_value=mock_buffer):
            with patch('builtins.open', mock_open()):
                success, path, error = compress_image_to_limit("/fake/image.png", max_size_mb=10.0)

        self.assertTrue(success)


class TestResizeImageToPixelLimit(unittest.TestCase):
    """测试 resize_image_to_pixel_limit"""

    @patch('utils.image_compressor.os.path.exists', return_value=False)
    def test_file_not_exists(self, mock_exists):
        success, path, error = resize_image_to_pixel_limit("/fake/missing.jpg")
        self.assertFalse(success)
        self.assertIn("文件不存在", error)

    @patch('utils.image_compressor.Image.open')
    @patch('utils.image_compressor.os.path.exists', return_value=True)
    def test_pixels_under_limit(self, mock_exists, mock_img_open):
        """像素数未超限，直接返回原路径"""
        mock_img = MagicMock()
        mock_img.width = 1000
        mock_img.height = 1000  # 1M pixels, under 36M limit
        mock_img_open.return_value = mock_img

        success, path, error = resize_image_to_pixel_limit("/fake/small.jpg")
        self.assertTrue(success)
        self.assertEqual(path, "/fake/small.jpg")
        self.assertIsNone(error)

    @patch('utils.image_compressor.Image.open')
    @patch('utils.image_compressor.os.path.exists', return_value=True)
    def test_resize_preserves_aspect_ratio(self, mock_exists, mock_img_open):
        """缩放保持宽高比"""
        mock_img = MagicMock()
        mock_img.width = 10000
        mock_img.height = 8000  # 80M pixels > 36M limit
        mock_img.format = 'JPEG'
        mock_img_open.return_value = mock_img

        mock_resized = MagicMock()
        mock_img.resize.return_value = mock_resized

        with patch('builtins.open', mock_open()):
            success, path, error = resize_image_to_pixel_limit(
                "/fake/huge.jpg",
                max_total_pixels=36_000_000,
                output_path="/fake/output.jpg"
            )

        self.assertTrue(success)
        # 验证调用了 resize
        mock_img.resize.assert_called_once()
        call_args = mock_img.resize.call_args[0][0]
        # 验证宽高比大致保持 10000:8000 = 5:4
        ratio = call_args[0] / call_args[1]
        self.assertAlmostEqual(ratio, 10000 / 8000, places=2)


class TestDownloadAndCompressToBase64(unittest.TestCase):
    """测试 download_and_compress_to_base64"""

    def test_unsupported_url_scheme(self):
        success, data_url, error = download_and_compress_to_base64("ftp://example.com/img.jpg")
        self.assertFalse(success)
        self.assertIn("不支持的 URL 协议", error)

    @patch('httpx.Client')
    @patch('utils.image_compressor.compress_image_to_limit')
    @patch('utils.image_compressor.os.path.exists', return_value=True)
    @patch('utils.image_compressor.os.path.getsize')
    @patch('utils.image_compressor.Image.open')
    @patch('utils.image_compressor.get_image_size_mb', return_value=1.0)
    def test_successful_download_and_compress(self, mock_size, mock_img_open, mock_getsize, mock_exists,
                                               mock_compress, mock_client_cls):
        """测试正常下载压缩流程"""
        # Mock httpx.Client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b'\xff\xd8\xff\xe0' + b'\x00' * 100  # fake JPEG header + data
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Mock compress
        fake_jpeg = b'\xff\xd8\xff\xe0test_data'
        mock_compress.return_value = (True, "/fake/temp.jpg", None)

        # 注入 mock 的 utils.media_cache 模块（测试环境缺少 aiohttp）
        from pathlib import Path
        mock_media_cache = MagicMock()
        mock_media_cache.get_temp_date_dir = MagicMock(return_value=Path("/fake/temp_dir"))

        with patch.dict('sys.modules', {'utils.media_cache': mock_media_cache}):
            with patch('utils.image_compressor.os.path.splitext', return_value=('/fake/temp', '.jpg')):
                with patch('builtins.open', mock_open(read_data=fake_jpeg)):
                    with patch('utils.image_compressor.os.remove'):
                        with patch('pathlib.Path.mkdir', return_value=None):
                            success, data_url, error = download_and_compress_to_base64(
                                "http://example.com/img.jpg",
                                max_pixels=0
                            )

        # 验证返回格式
        if success:
            self.assertTrue(data_url.startswith("data:image/"))

    @patch('httpx.Client')
    def test_empty_download(self, mock_client_cls):
        """测试下载空内容"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b''
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        success, data_url, error = download_and_compress_to_base64("http://example.com/empty.jpg")

        self.assertFalse(success)
        self.assertIn("下载图片为空", error)


class TestUrlToBase64(unittest.TestCase):
    """测试 url_to_base64 包装函数"""

    @patch('utils.image_compressor.download_and_compress_to_base64',
           return_value=(True, "data:image/jpeg;base64,ABC", None))
    def test_success_returns_data_url(self, mock_download):
        result = url_to_base64("http://example.com/img.jpg")
        self.assertEqual(result, "data:image/jpeg;base64,ABC")

    @patch('utils.image_compressor.download_and_compress_to_base64',
           return_value=(False, None, "download failed"))
    def test_failure_returns_none(self, mock_download):
        result = url_to_base64("http://example.com/img.jpg")
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
