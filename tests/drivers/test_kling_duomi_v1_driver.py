"""
Kling 多米供应商 v1 版本驱动单元测试
纯单元测试，不依赖数据库，使用 mock 替代所有外部依赖

测试结构：
- KlingDuomiV1Driver 初始化测试
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


def _create_kling_driver(token='test_duomi_token'):
    """创建 KlingDuomiV1Driver 实例（mock 所有外部依赖）"""
    from task.visual_drivers.kling_duomi_v1_driver import KlingDuomiV1Driver

    with patch('task.visual_drivers.kling_duomi_v1_driver.get_dynamic_config_value') as mock_config, \
         patch('task.visual_drivers.kling_duomi_v1_driver.get_config', return_value={}):

        def side_effect(*keys, default=None):
            key_map = {
                ('duomi', 'token'): token,
                ('timeout', 'request_timeout'): 30,
                ('server', 'is_local'): False,
            }
            return key_map.get(keys, default)

        mock_config.side_effect = side_effect
        driver = KlingDuomiV1Driver()
        return driver


def _make_ai_tool(prompt='测试提示词', image_path='http://example.com/test.jpg',
                  duration=5, reference_images=None, extra_config=None):
    """创建模拟的 ai_tool 对象"""
    tool = MagicMock()
    tool.id = 1002
    tool.prompt = prompt
    tool.image_path = image_path
    tool.duration = duration
    tool.reference_images = reference_images or []
    tool.extra_config = extra_config
    return tool


class TestKlingDuomiV1DriverInit(unittest.TestCase):
    """测试驱动初始化"""

    def test_driver_name(self):
        """驱动名称应为 kling_duomi_v1"""
        driver = _create_kling_driver()
        self.assertEqual(driver.driver_name, 'kling_duomi_v1')

    def test_driver_type(self):
        """驱动类型应为 12"""
        driver = _create_kling_driver()
        self.assertEqual(driver.driver_type, 12)

    def test_base_url_config(self):
        """验证 base_url 配置"""
        driver = _create_kling_driver()
        self.assertEqual(driver._base_url, 'https://duomiapi.com')

    def test_token_config(self):
        """验证 token 配置"""
        custom_token = 'custom_kling_token_456'
        driver = _create_kling_driver(token=custom_token)
        self.assertEqual(driver._token, custom_token)

    def test_timeout_config(self):
        """验证 timeout 配置"""
        driver = _create_kling_driver()
        self.assertEqual(driver._timeout, 30)


class TestKlingValidateSubmitResponse(unittest.TestCase):
    """测试 _validate_submit_response 方法"""

    def setUp(self):
        self.driver = _create_kling_driver()

    def test_valid_response_code_0(self):
        """正确格式的响应 (code=0)"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123456"
            }
        }
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_response_code_non_zero(self):
        """业务错误响应 (code != 0) 格式仍有效"""
        result = {
            "code": 1,
            "message": "API额度已用尽"
        }
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_missing_code_field(self):
        """缺少 code 字段"""
        result = {"message": "success"}
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertFalse(is_valid)
        self.assertIn("code", error)

    def test_missing_data_field_when_code_0(self):
        """code=0 时缺少 data 字段"""
        result = {
            "code": 0,
            "message": "success"
        }
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertFalse(is_valid)
        self.assertIn("data", error)

    def test_data_not_dict(self):
        """data 不是 dict 类型"""
        result = {
            "code": 0,
            "message": "success",
            "data": "task_id_string"
        }
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertFalse(is_valid)
        self.assertIn("dict", error)

    def test_missing_task_id_field(self):
        """data 缺少 task_id 字段"""
        result = {
            "code": 0,
            "message": "success",
            "data": {}
        }
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertFalse(is_valid)
        self.assertIn("task_id", error)

    def test_task_id_not_string(self):
        """task_id 字段类型错误"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": 123456
            }
        }
        is_valid, error = self.driver._validate_submit_response(result)
        self.assertFalse(is_valid)
        self.assertIn("str", error)

    def test_non_dict_response(self):
        """非 dict 类型"""
        is_valid, error = self.driver._validate_submit_response("not a dict")
        self.assertFalse(is_valid)
        self.assertIn("字典", error)


class TestKlingValidateStatusResponse(unittest.TestCase):
    """测试 _validate_status_response 方法"""

    def setUp(self):
        self.driver = _create_kling_driver()

    def test_valid_processing_response(self):
        """处理中的有效响应"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123",
                "task_status": "processing"
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_succeed_response(self):
        """成功的有效响应"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123",
                "task_status": "succeed",
                "task_result": {
                    "videos": [
                        {
                            "id": "video_123",
                            "url": "https://example.com/video.mp4",
                            "duration": "5"
                        }
                    ]
                }
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_valid_failed_response(self):
        """失败的有效响应"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123",
                "task_status": "failed"
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_business_error_response(self):
        """业务错误响应 (code != 0) 格式仍有效"""
        result = {
            "code": 1,
            "message": "查询失败"
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_missing_code_field(self):
        """缺少 code 字段"""
        result = {"message": "success"}
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("code", error)

    def test_missing_data_field_when_code_0(self):
        """code=0 时缺少 data 字段"""
        result = {
            "code": 0,
            "message": "success"
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("data", error)

    def test_data_not_dict(self):
        """data 不是 dict 类型"""
        result = {
            "code": 0,
            "message": "success",
            "data": "task_data"
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("dict", error)

    def test_missing_task_status_field(self):
        """data 缺少 task_status 字段"""
        result = {
            "code": 0,
            "message": "success",
            "data": {"task_id": "task_123"}
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("task_status", error)

    def test_succeed_missing_task_result(self):
        """成功状态但缺少 task_result"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_123",
                "task_status": "succeed"
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("task_result", error)

    def test_succeed_task_result_not_dict(self):
        """task_result 不是 dict 类型"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_123",
                "task_status": "succeed",
                "task_result": "not_dict"
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("task_result", error)

    def test_succeed_missing_videos(self):
        """成功状态但 task_result 缺少 videos"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_123",
                "task_status": "succeed",
                "task_result": {}
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("videos", error)

    def test_succeed_videos_empty(self):
        """成功状态但 videos 为空"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_123",
                "task_status": "succeed",
                "task_result": {"videos": []}
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("videos", error)

    def test_succeed_video_missing_url(self):
        """视频对象缺少 url 字段"""
        result = {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_123",
                "task_status": "succeed",
                "task_result": {
                    "videos": [{"id": "video_123"}]
                }
            }
        }
        is_valid, error = self.driver._validate_status_response(result)
        self.assertFalse(is_valid)
        self.assertIn("url", error)


class TestKlingBuildCreateRequest(unittest.TestCase):
    """测试 build_create_request 方法"""

    def setUp(self):
        self.driver = _create_kling_driver()

    def test_first_last_frame_with_first_frame_only(self):
        """首尾帧模式 - 仅有首帧"""
        tool = _make_ai_tool(
            image_path='http://example.com/first.jpg',
            duration=5
        )
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get:
            mock_get.return_value = {
                'mode': 'first_last_frame',
                'first_frame': 'http://example.com/first.jpg',
                'last_frame': None,
                'reference_images': []
            }
            result = self.driver.build_create_request(tool)

            self.assertEqual(result['json']['model_name'], 'kling-v2-5-turbo')
            self.assertEqual(result['json']['image'], 'http://example.com/first.jpg')
            self.assertEqual(result['json']['prompt'], '测试提示词')
            self.assertEqual(result['json']['mode'], 'std')
            self.assertEqual(result['json']['duration'], 5)
            self.assertNotIn('image_tail', result['json'])

    def test_first_last_frame_with_both_frames(self):
        """首尾帧模式 - 有首帧和尾帧"""
        tool = _make_ai_tool(
            image_path='http://example.com/first.jpg,http://example.com/last.jpg',
            duration=10
        )
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get:
            mock_get.return_value = {
                'mode': 'first_last_frame',
                'first_frame': 'http://example.com/first.jpg',
                'last_frame': 'http://example.com/last.jpg',
                'reference_images': []
            }
            result = self.driver.build_create_request(tool)

            self.assertEqual(result['json']['image'], 'http://example.com/first.jpg')
            self.assertEqual(result['json']['mode'], 'pro')
            self.assertEqual(result['json']['duration'], 10)
            self.assertEqual(result['json']['image_tail'], 'http://example.com/last.jpg')

    def test_multi_reference_mode(self):
        """多参考图模式 - 使用第一张参考图"""
        tool = _make_ai_tool(
            reference_images=[
                'http://example.com/ref1.jpg',
                'http://example.com/ref2.jpg'
            ]
        )
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get:
            mock_get.return_value = {
                'mode': 'multi_reference',
                'first_frame': None,
                'last_frame': None,
                'reference_images': [
                    'http://example.com/ref1.jpg',
                    'http://example.com/ref2.jpg'
                ]
            }
            result = self.driver.build_create_request(tool)

            self.assertEqual(result['json']['image'], 'http://example.com/ref1.jpg')
            self.assertEqual(result['json']['mode'], 'std')

    def test_first_last_with_ref_mode(self):
        """首尾帧+参考图模式 - 优先使用首帧"""
        tool = _make_ai_tool(
            image_path='http://example.com/first.jpg',
            reference_images=['http://example.com/ref.jpg']
        )
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get:
            mock_get.return_value = {
                'mode': 'first_last_with_ref',
                'first_frame': 'http://example.com/first.jpg',
                'last_frame': None,
                'reference_images': ['http://example.com/ref.jpg']
            }
            result = self.driver.build_create_request(tool)

            self.assertEqual(result['json']['image'], 'http://example.com/first.jpg')

    def test_request_headers(self):
        """验证请求 headers"""
        tool = _make_ai_tool()
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get:
            mock_get.return_value = {
                'mode': 'first_last_frame',
                'first_frame': 'http://example.com/first.jpg',
                'last_frame': None,
                'reference_images': []
            }
            result = self.driver.build_create_request(tool)

            self.assertIn('Authorization', result['headers'])
            self.assertEqual(result['headers']['Authorization'], 'test_duomi_token')
            self.assertEqual(result['headers']['Content-Type'], 'application/json')

    def test_request_url(self):
        """验证请求 URL"""
        tool = _make_ai_tool()
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get:
            mock_get.return_value = {
                'mode': 'first_last_frame',
                'first_frame': 'http://example.com/first.jpg',
                'last_frame': None,
                'reference_images': []
            }
            result = self.driver.build_create_request(tool)

            self.assertIn('/api/video/kling/v1/videos/image2video', result['url'])
            self.assertEqual(result['method'], 'POST')

    def test_no_image_raises_error(self):
        """无图片时抛出异常"""
        tool = _make_ai_tool(image_path=None, reference_images=[])
        with patch.object(self.driver, 'get_all_images_by_mode') as mock_get:
            mock_get.return_value = {
                'mode': 'first_last_frame',
                'first_frame': None,
                'last_frame': None,
                'reference_images': []
            }
            with self.assertRaises(ValueError) as ctx:
                self.driver.build_create_request(tool)
            self.assertIn('至少1张图片', str(ctx.exception))


class TestKlingBuildCheckQuery(unittest.TestCase):
    """测试 build_check_query 方法"""

    def setUp(self):
        self.driver = _create_kling_driver()

    def test_check_query_structure(self):
        """检查查询请求结构"""
        result = self.driver.build_check_query('task_kling_123')

        self.assertIn('/api/video/kling/v1/videos/image2video/task_kling_123', result['url'])
        self.assertEqual(result['method'], 'GET')
        self.assertIsNone(result['json'])
        self.assertIn('Authorization', result['headers'])

    def test_check_query_with_different_project_ids(self):
        """不同的 project_id"""
        project_ids = ['task_123', 'kling_abc', 'project_xyz']
        for pid in project_ids:
            result = self.driver.build_check_query(pid)
            self.assertIn(pid, result['url'])


class TestKlingSubmitTask(unittest.TestCase):
    """测试 submit_task 方法"""

    def setUp(self):
        self.driver = _create_kling_driver()

    def test_submit_task_success(self):
        """提交任务成功"""
        tool = _make_ai_tool()
        self.driver._request = MagicMock(return_value={
            "code": 0,
            "message": "success",
            "data": {"task_id": "task_kling_123"}
        })

        result = self.driver.submit_task(tool)

        self.assertTrue(result['success'])
        self.assertEqual(result['project_id'], 'task_kling_123')

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

    def test_submit_task_business_error(self):
        """提交任务 - 业务错误 (code != 0)"""
        tool = _make_ai_tool()
        self.driver._request = MagicMock(return_value={
            "code": 1,
            "message": "API额度已用尽"
        })

        result = self.driver.submit_task(tool)

        self.assertFalse(result['success'])
        self.assertIn('API额度已用尽', result['error'])
        self.assertEqual(result['error_type'], 'USER')

    def test_submit_task_missing_task_id(self):
        """提交任务 - 响应缺少 task_id"""
        tool = _make_ai_tool()
        self.driver._request = MagicMock(return_value={
            "code": 0,
            "message": "success",
            "data": {}
        })

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


class TestKlingCheckStatus(unittest.TestCase):
    """测试 check_status 方法"""

    def setUp(self):
        self.driver = _create_kling_driver()

    def test_check_status_succeed(self):
        """任务成功"""
        self.driver._request = MagicMock(return_value={
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123",
                "task_status": "succeed",
                "task_result": {
                    "videos": [
                        {
                            "id": "video_123",
                            "url": "https://example.com/video.mp4",
                            "duration": "5"
                        }
                    ]
                }
            }
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(result['result_url'], 'https://example.com/video.mp4')

    def test_check_status_failed(self):
        """任务失败"""
        self.driver._request = MagicMock(return_value={
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123",
                "task_status": "failed",
                "fail_reason": "内容违规"
            }
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error'], '内容违规')
        self.assertEqual(result['error_type'], 'USER')

    def test_check_status_processing(self):
        """任务处理中"""
        self.driver._request = MagicMock(return_value={
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123",
                "task_status": "processing"
            }
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

    def test_check_status_business_error(self):
        """业务错误 (code != 0)"""
        self.driver._request = MagicMock(return_value={
            "code": 1,
            "message": "查询失败"
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'FAILED')
        self.assertIn('查询失败', result['error'])

    def test_check_status_succeed_no_videos(self):
        """成功但无视频数据"""
        self.driver._request = MagicMock(return_value={
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123",
                "task_status": "succeed",
                "task_result": {"videos": []}
            }
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'FAILED')

    def test_check_status_failed_no_fail_reason(self):
        """失败但无失败原因"""
        self.driver._request = MagicMock(return_value={
            "code": 0,
            "message": "success",
            "data": {
                "task_id": "task_kling_123",
                "task_status": "failed"
            }
        })

        result = self.driver.check_status('task_123')

        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error'], '任务失败')


if __name__ == '__main__':
    unittest.main()
