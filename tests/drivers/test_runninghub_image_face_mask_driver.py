"""
RunningHubImageFaceMaskDriver 单元测试

测试图片人脸遮盖 RunningHub App 的配置、提交响应解析和结果 URL 提取。
"""
import sys
import unittest
from unittest.mock import MagicMock

sys.modules['api.clients.runninghub_client'] = MagicMock()
_saved_config_util = sys.modules.get('config.config_util')
sys.modules['config.config_util'] = MagicMock()
sys.modules['utils.file_storage'] = MagicMock()

from task.async_drivers.runninghub_image_face_mask_driver import (
    RunningHubImageFaceMaskDriver,
    RunningHubImageFaceMaskConfig,
)

if _saved_config_util is not None:
    sys.modules['config.config_util'] = _saved_config_util
else:
    sys.modules.pop('config.config_util', None)


class TestRunningHubImageFaceMaskConfig(unittest.TestCase):
    """测试 RunningHub 图片人脸遮盖配置常量"""

    def test_app_id(self):
        self.assertEqual(RunningHubImageFaceMaskConfig.APP_ID, "2067560129192620033")

    def test_image_node_mapping(self):
        self.assertEqual(RunningHubImageFaceMaskConfig.IMAGE_NODE_ID, "3")
        self.assertEqual(RunningHubImageFaceMaskConfig.IMAGE_FIELD_NAME, "image")


class TestParseSubmitResponse(unittest.TestCase):
    """测试提交响应解析"""

    def test_valid_response_with_task_id(self):
        result = RunningHubImageFaceMaskDriver._parse_submit_response({'taskId': 'rh-task-1'})

        self.assertTrue(result['success'])
        self.assertEqual(result['project_id'], 'rh-task-1')

    def test_missing_task_id(self):
        result = RunningHubImageFaceMaskDriver._parse_submit_response({'errorMessage': 'APP 不存在'})

        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'APP 不存在')
        self.assertEqual(result['error_type'], 'SYSTEM')


class TestExtractResultUrl(unittest.TestCase):
    """测试查询结果 URL 提取"""

    def test_png_result_url(self):
        response = {
            'results': [
                {'url': 'https://example.com/masked.png', 'outputType': 'png', 'nodeId': '2'}
            ]
        }

        result = RunningHubImageFaceMaskDriver._extract_result_url(response)

        self.assertEqual(result, 'https://example.com/masked.png')

    def test_no_result_url_returns_none(self):
        self.assertIsNone(RunningHubImageFaceMaskDriver._extract_result_url({'results': []}))


if __name__ == '__main__':
    unittest.main()
