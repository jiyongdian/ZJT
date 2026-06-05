"""
VEO3 多米供应商 v1 版本驱动单元测试
纯单元测试，不依赖数据库，使用 mock 替代所有外部依赖

测试结构：
- Veo3DuomiV1Driver 初始化测试
- 响应格式验证测试
- 请求构建测试
- 任务提交测试
- 状态检查测试
"""
import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock 外部依赖（必须在 import driver 之前）
sys.modules['utils.sentry_util'] = MagicMock()
sys.modules['utils.image_upload_utils'] = MagicMock()


def _create_veo3_driver(token='test_duomi_token'):
    """创建 Veo3DuomiV1Driver 实例（mock 所有外部依赖）"""
    from task.visual_drivers.veo3_duomi_v1_driver import Veo3DuomiV1Driver

    with patch('task.visual_drivers.veo3_duomi_v1_driver.get_dynamic_config_value') as mock_config, \
         patch('task.visual_drivers.veo3_duomi_v1_driver.get_config', return_value={}):

        def side_effect(*keys, default=None):
            key_map = {
                ('duomi', 'token'): token,
                ('timeout', 'request_timeout'): 30,
                ('server', 'is_local'): False,
            }
            return key_map.get(keys, default)

        mock_config.side_effect = side_effect
        driver = Veo3DuomiV1Driver()
        return driver


def _make_ai_tool(prompt='测试提示词', ratio='9:16', image_path=None,
                  reference_images=None, duration=None):
    """创建模拟的 ai_tool 对象"""
    tool = MagicMock()
    tool.id = 1001
    tool.prompt = prompt
    tool.ratio = ratio
    tool.image_path = image_path
    tool.reference_images = reference_images or []
    tool.duration = duration
    return tool


class TestVeo3DuomiV1DriverInit(unittest.TestCase):
    """测试驱动初始化"""

    def test_driver_name(self):
        """驱动名称应为 veo3_duomi_v1"""
        driver = _create_veo3_driver()
        self.assertEqual(driver.driver_name, 'veo3_duomi_v1')

    def test_driver_type(self):
        """驱动类型应为 15"""
        driver = _create_veo3_driver()
        self.assertEqual(driver.driver_type, 15)

    def test_base_url_config(self):
        """验证 base_url 配置"""
        driver = _create_veo3_driver()
        self.assertEqual(driver._base_url, 'https://duomiapi.com')

    def test_token_config(self):
        """验证 token 配置"""
        custom_token = 'custom_duomi_token_123'
        driver = _create_veo3_driver(token=custom_token)
        self.assertEqual(driver._token, custom_token)

    def test_timeout_config(self):
        """验证 timeout 配置"""
        driver = _create_veo3_driver()
        self.assertEqual(driver._timeout, 30)


class TestVeo3ValidateSubmitResponse(unittest.TestCase):
    """测试 _validate_submit_response 方法"""

    def setUp(self):
        self.driver = _create_veo3_driver()

    def test_valid_response(self):
        """正确格式的响应"""
        result = {"id": "task_veo3_123456"}
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_missing_id_field(self):
        """缺少 id 字段"""
        result = {"state": "processing"}
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertFalse(is_valid)
        self.assertIn("id", error)

    def test_non_dict_response(self):
        """非 dict 类型"""
        is_valid, error = self.driver._validate_submit_response("not a dict")
        self.assertFalse(is_valid)
        self.assertIn("字典", error)

    def test_id_not_string(self):
        """id 字段类型错误"""
        result = {"id": 12345}
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertFalse(is_valid)
        self.assertIn("str", error)

    def test_empty_dict(self):
        """空 dict"""
        is_valid, error = self.driver._validate_submit_response({})
        self.assertFalse(is_valid)
        self.assertIn("id", error)


class TestVeo3ValidateStatusResponse(unittest.TestCase):
    """测试 _validate_status_response 方法"""

    def setUp(self):
        self.driver = _create_veo3_driver()

    def test_valid_processing_response(self):
        """处理中的有效响应"""
        result = {
            "code": 0,
            "msg": "processing",
            "data": {
                "status": 0,
                "mediaUrl": None
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_success_response(self):
        """成功的有效响应"""
        result = {
            "code": 0,
            "msg": "success",
            "data": {
                "status": 1,
                "mediaUrl": "https://example.com/video.mp4"
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_failed_response(self):
        """失败的有效响应"""
        result = {
            "code": 0,
            "msg": "failed",
            "data": {
                "status": 2,
                "mediaUrl": None,
                "reason": "内容违规"
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_missing_code_field(self):
        """缺少 code 字段"""
        result = {"msg": "success"}
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("code", error)

    def test_missing_msg_field(self):
        """缺少 msg 字段"""
        result = {"code": 0, "data": {}}
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("msg", error)

    def test_missing_data_field(self):
        """缺少 data 字段"""
        result = {"code": 0, "msg": "success"}
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("data", error)

    def test_missing_status_field(self):
        """data 缺少 status 字段"""
        result = {
            "code": 0,
            "msg": "success",
            "data": {"mediaUrl": None}
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("status", error)

    def test_invalid_status_value(self):
        """status 值无效"""
        result = {
            "code": 0,
            "msg": "success",
            "data": {
                "status": 99,
                "mediaUrl": None
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("status", error)

    def test_status_not_int(self):
        """status 字段类型错误"""
        result = {
            "code": 0,
            "msg": "success",
            "data": {
                "status": "completed",
                "mediaUrl": None
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("status", error)

    def test_success_missing_media_url(self):
        """成功状态但缺少 mediaUrl"""
        result = {
            "code": 0,
            "msg": "success",
            "data": {
                "status": 1
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("mediaUrl", error)

    def test_success_empty_media_url(self):
        """成功状态但 mediaUrl 为空"""
        result = {
            "code": 0,
            "msg": "success",
            "data": {
                "status": 1,
                "mediaUrl": None
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("mediaUrl", error)


class TestVeo3BuildCreateRequest(unittest.TestCase):
    """测试 build_create_request 方法"""

    def setUp(self):
        self.driver = _create_veo3_driver()

    def test_text_only_mode(self):
        """纯文本模式（无图片）"""
        tool = _make_ai_tool(prompt='生成一个美丽的日出')
        result = self.driver.build_create_request(tool)

        self.assertIn('/v1/videos/generations', result['url'])
        self.assertEqual(result['method'], 'POST')
        self.assertEqual(result['json']['model'], 'veo3.1-fast')
        self.assertEqual(result['json']['prompt'], '生成一个美丽的日出')
        self.assertEqual(result['json']['aspect_ratio'], '9:16')
        self.assertEqual(result['json']['duration'], 8)
        self.assertEqual(result['json']['generation_type'], 'FIRST&LAST')
        self.assertNotIn('image_urls', result['json'])

    def test_first_last_frame_mode_with_both_frames(self):
        """首尾帧模式 - 同时有首帧和尾帧"""
        tool = _make_ai_tool(
            ratio='16:9',
            image_path='http://example.com/first.jpg,http://example.com/last.jpg'
        )
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get, \
             patch.object(self.driver, 'ensure_public_urls', side_effect=lambda urls: urls):
            mock_get.return_value = {
                'mode': 'first_last_frame',
                'first_frame': 'http://example.com/first.jpg',
                'last_frame': 'http://example.com/last.jpg',
                'reference_images': []
            }
            result = self.driver.build_create_request(tool)

            self.assertEqual(result['json']['aspect_ratio'], '16:9')
            self.assertEqual(result['json']['generation_type'], 'FIRST&LAST')
            self.assertEqual(len(result['json']['image_urls']), 2)
            self.assertEqual(result['json']['image_urls'][0], 'http://example.com/first.jpg')
            self.assertEqual(result['json']['image_urls'][1], 'http://example.com/last.jpg')

    def test_multi_reference_mode(self):
        """多参考图模式"""
        tool = _make_ai_tool(
            reference_images=[
                'http://example.com/ref1.jpg',
                'http://example.com/ref2.jpg',
                'http://example.com/ref3.jpg'
            ]
        )
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get, \
             patch.object(self.driver, 'ensure_public_urls', side_effect=lambda urls: urls):
            mock_get.return_value = {
                'mode': 'multi_reference',
                'first_frame': None,
                'last_frame': None,
                'reference_images': [
                    'http://example.com/ref1.jpg',
                    'http://example.com/ref2.jpg',
                    'http://example.com/ref3.jpg'
                ]
            }
            result = self.driver.build_create_request(tool)

            self.assertEqual(result['json']['generation_type'], 'REFERENCE')
            self.assertEqual(len(result['json']['image_urls']), 3)

    def test_multi_reference_truncated_to_3(self):
        """多参考图超过3张时截取前3张"""
        reference_images = [f'http://example.com/ref{i}.jpg' for i in range(1, 6)]
        tool = _make_ai_tool(reference_images=reference_images)

        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get, \
             patch.object(self.driver, 'ensure_public_urls', side_effect=lambda urls: urls):
            mock_get.return_value = {
                'mode': 'multi_reference',
                'first_frame': None,
                'last_frame': None,
                'reference_images': reference_images
            }
            result = self.driver.build_create_request(tool)

            self.assertEqual(len(result['json']['image_urls']), 3)

    def test_headers_include_authorization(self):
        """验证 headers 包含 Authorization"""
        tool = _make_ai_tool()
        result = self.driver.build_create_request(tool)

        self.assertIn('Authorization', result['headers'])
        self.assertEqual(result['headers']['Authorization'], 'test_duomi_token')
        self.assertEqual(result['headers']['Content-Type'], 'application/json')


class TestVeo3BuildCheckQuery(unittest.TestCase):
    """测试 build_check_query 方法"""

    def setUp(self):
        self.driver = _create_veo3_driver()

    def test_check_query_structure(self):
        """检查查询请求结构"""
        result = self.driver.build_check_query('task_veo3_123')

        self.assertIn('/v1/videos/tasks/task_veo3_123', result['url'])
        self.assertEqual(result['method'], 'GET')
        self.assertIsNone(result['json'])
        self.assertIn('Authorization', result['headers'])

    def test_check_query_with_different_project_ids(self):
        """不同的 project_id"""
        project_ids = ['task_123', 'veo3_abc', 'project_xyz']
        for pid in project_ids:
            result = self.driver.build_check_query(pid)
            self.assertIn(pid, result['url'])


class TestVeo3SubmitTask(unittest.TestCase):
    """测试 submit_task 方法"""

    def setUp(self):
        self.driver = _create_veo3_driver()

    def test_submit_task_success(self):
        """提交任务成功"""
        tool = _make_ai_tool()
        self.driver._request = MagicMock(return_value={"id": "task_veo3_123"})

        result = self.driver.submit_task(tool)

        self.assertTrue(result['success'])
        self.assertEqual(result['project_id'], 'task_veo3_123')

    def test_submit_task_invalid_response_format(self):
        """提交任务 - 无效的响应格式"""
        tool = _make_ai_tool()
        self.driver._request = MagicMock(return_value={"error": "invalid"})

        result = self.driver.submit_task(tool)

        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'SYSTEM')
        self.assertFalse(result['retry'])

    def test_submit_task_network_error(self):
        """提交任务 - 网络错误"""
        tool = _make_ai_tool()
        self.driver._request = MagicMock(side_effect=ConnectionError('timeout'))

        result = self.driver.submit_task(tool)

        self.assertFalse(result['success'])
        self.assertTrue(result['retry'])
        self.assertIn('网络', result['error'])

    def test_submit_task_missing_project_id(self):
        """提交任务 - 响应缺少 id"""
        tool = _make_ai_tool()
        self.driver._request = MagicMock(return_value={})

        result = self.driver.submit_task(tool)

        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'SYSTEM')

    def test_submit_task_unexpected_exception(self):
        """提交任务 - 未预期的异常"""
        tool = _make_ai_tool()
        self.driver._request = MagicMock(side_effect=ValueError('unexpected error'))

        result = self.driver.submit_task(tool)

        self.assertFalse(result['success'])
        self.assertFalse(result['retry'])
        self.assertEqual(result['error_type'], 'SYSTEM')


class TestVeo3CheckStatus(unittest.TestCase):
    """测试 check_status 方法"""

    def setUp(self):
        self.driver = _create_veo3_driver()

    def test_check_status_succeeded(self):
        """任务成功"""
        self.driver._request = MagicMock(return_value={
            "state": "succeeded",
            "data": {
                "videos": [
                    {"url": "https://example.com/video.mp4"}
                ]
            }
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(result['result_url'], 'https://example.com/video.mp4')

    def test_check_status_error(self):
        """任务失败"""
        self.driver._request = MagicMock(return_value={
            "state": "error",
            "message": "内容违规"
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error'], '查询任务状态失败: 内容违规')
        self.assertEqual(result['error_type'], 'SYSTEM')

    def test_check_status_processing(self):
        """任务处理中"""
        self.driver._request = MagicMock(return_value={
            "state": "processing",
            "message": ""
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'RUNNING')

    def test_check_status_network_error(self):
        """网络错误"""
        self.driver._request = MagicMock(side_effect=ConnectionError('timeout'))

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'RUNNING')

    def test_check_status_invalid_response_format(self):
        """无效的响应格式"""
        self.driver._request = MagicMock(return_value="invalid")

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error_type'], 'SYSTEM')

    def test_check_status_succeeded_no_videos(self):
        """成功但无视频数据"""
        self.driver._request = MagicMock(return_value={
            "state": "succeeded",
            "data": {"videos": []}
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'FAILED')

    def test_check_status_succeeded_no_video_url(self):
        """成功但视频无 URL"""
        self.driver._request = MagicMock(return_value={
            "state": "succeeded",
            "data": {
                "videos": [{"id": "vid123"}]
            }
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'FAILED')


if __name__ == '__main__':
    unittest.main()
