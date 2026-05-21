"""
RunningHub 音频驱动测试
直接测试驱动方法，mock RunningHubClient 的异步调用
"""
import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Mock 第三方依赖模块
sys.modules['utils.sentry_util'] = MagicMock()
sys.modules['utils.file_storage'] = MagicMock()
sys.modules['qiniu'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()

from task.async_drivers.runninghub_audio_driver import RunningHubAudioDriver, RunningHubAudioConfig

import unittest


class TestRunningHubAudioDriver(unittest.TestCase):
    """RunningHub 音频驱动测试"""

    def setUp(self):
        """测试前准备"""
        self.driver = RunningHubAudioDriver()

    def test_driver_initialization(self):
        """测试驱动初始化"""
        self.assertIsNotNone(self.driver)
        self.assertEqual(self.driver.driver_name, 'runninghub_audio')
        self.assertIsNotNone(self.driver._client)

    def test_submit_task_success(self):
        """测试提交音频生成任务成功"""
        with patch.object(self.driver._client, 'run_ai_app_v2', new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = {
                "taskId": "audio_task_123456",
                "status": "RUNNING"
            }

            result = asyncio.run(self.driver.submit_task(
                style_prompt="声音自然清晰",
                text="大家好，我是测试角色"
            ))

            self.assertTrue(result['success'])
            self.assertEqual(result['project_id'], 'audio_task_123456')
            mock_submit.assert_called_once()

    def test_submit_task_no_task_id(self):
        """测试提交任务返回空 taskId"""
        with patch.object(self.driver._client, 'run_ai_app_v2', new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = {
                "taskId": "",
                "status": "FAILED",
                "errorMessage": "Invalid request"
            }

            result = asyncio.run(self.driver.submit_task(
                style_prompt="声音自然清晰",
                text="测试文本"
            ))

            self.assertFalse(result['success'])
            self.assertEqual(result['error_type'], 'SYSTEM')
            self.assertIn('Invalid request', result['error'])
            self.assertFalse(result['retry'])

    def test_submit_task_connection_error(self):
        """测试提交任务网络异常"""
        with patch.object(self.driver._client, 'run_ai_app_v2', new_callable=AsyncMock) as mock_submit:
            mock_submit.side_effect = ConnectionError("Connection refused")

            result = asyncio.run(self.driver.submit_task(
                style_prompt="声音自然清晰",
                text="测试文本"
            ))

            self.assertFalse(result['success'])
            self.assertEqual(result['error_type'], 'USER')
            self.assertTrue(result['retry'])

    def test_submit_task_timeout(self):
        """测试提交任务超时"""
        with patch.object(self.driver._client, 'run_ai_app_v2', new_callable=AsyncMock) as mock_submit:
            mock_submit.side_effect = TimeoutError("Request timed out")

            result = asyncio.run(self.driver.submit_task(
                style_prompt="声音自然清晰",
                text="测试文本"
            ))

            self.assertFalse(result['success'])
            self.assertEqual(result['error_type'], 'USER')
            self.assertTrue(result['retry'])

    def test_check_status_running(self):
        """测试查询状态 - 任务运行中"""
        with patch.object(self.driver._client, 'query_v2_task', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "status": "RUNNING"
            }

            result = asyncio.run(self.driver.check_status('test_task_id'))

            self.assertEqual(result['status'], 'RUNNING')

    def test_check_status_success(self):
        """测试查询状态 - 任务成功"""
        with patch.object(self.driver._client, 'query_v2_task', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "status": "SUCCESS",
                "results": [
                    {"url": "https://example.com/audio.wav"}
                ]
            }

            result = asyncio.run(self.driver.check_status('test_task_id'))

            self.assertEqual(result['status'], 'SUCCESS')
            self.assertEqual(result['result_url'], 'https://example.com/audio.wav')

    def test_check_status_success_no_url(self):
        """测试查询状态 - 成功但无 URL"""
        with patch.object(self.driver._client, 'query_v2_task', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "status": "SUCCESS",
                "results": []
            }

            result = asyncio.run(self.driver.check_status('test_task_id'))

            self.assertEqual(result['status'], 'FAILED')
            self.assertIn('未返回结果', result['error'])
            self.assertEqual(result['error_type'], 'SYSTEM')

    def test_check_status_failed(self):
        """测试查询状态 - 任务失败"""
        with patch.object(self.driver._client, 'query_v2_task', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "status": "FAILED",
                "errorMessage": "Audio generation failed"
            }

            result = asyncio.run(self.driver.check_status('test_task_id'))

            self.assertEqual(result['status'], 'FAILED')
            self.assertIn('Audio generation failed', result['error'])
            self.assertEqual(result['error_type'], 'USER')

    def test_check_status_connection_error(self):
        """测试查询状态 - 网络异常"""
        with patch.object(self.driver._client, 'query_v2_task', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = ConnectionError("Connection refused")

            result = asyncio.run(self.driver.check_status('test_task_id'))

            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['error_type'], 'USER')
            self.assertTrue(result.get('retry', False))

    def test_extract_result_url(self):
        """测试 URL 提取"""
        # 有 URL
        response = {"results": [{"url": "https://example.com/a.wav"}, {"url": "https://example.com/b.wav"}]}
        self.assertEqual(self.driver._extract_result_url(response), "https://example.com/a.wav")

        # 空 results
        self.assertIsNone(self.driver._extract_result_url({"results": []}))
        self.assertIsNone(self.driver._extract_result_url({}))
        self.assertIsNone(self.driver._extract_result_url({"results": [{"no_url": True}]}))

    def test_config_constants(self):
        """测试配置常量正确引用"""
        self.assertEqual(RunningHubAudioConfig.APP_ID, "2055657238609571841")
        self.assertEqual(RunningHubAudioConfig.STYLE_NODE_ID, "23")
        self.assertEqual(RunningHubAudioConfig.TEXT_NODE_ID, "24")
        self.assertIn("SUCCESS", RunningHubAudioConfig.FINAL_STATUSES)
        self.assertIn("FAILED", RunningHubAudioConfig.FINAL_STATUSES)


if __name__ == '__main__':
    unittest.main()
