"""
Pipeline 驱动工厂及驱动实现单元测试

测试 PipelineDriverFactory.create_driver()、FaceMaskPipelineDriver.execute()、
ImplementationRetryPipelineDriver.execute()。

只 mock model.database（不 mock model 包），避免跨测试污染。
使用 @patch 装饰器模拟 execute() 中的外部依赖。
"""
import asyncio
import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# 保存原始模块引用，防止污染后续测试
_saved_modules = {
    'model.database': sys.modules.get('model.database'),
    'api.clients.runninghub_client': sys.modules.get('api.clients.runninghub_client'),
    'config.config_util': sys.modules.get('config.config_util'),
    'utils.file_storage': sys.modules.get('utils.file_storage'),
}

# 只 mock database 层，不 mock model 包本身
sys.modules['model.database'] = MagicMock()

# Mock 需要外部连接的依赖（不影响 model 和 utils.logger_config）
sys.modules['api.clients.runninghub_client'] = MagicMock()
sys.modules['config.config_util'] = MagicMock()
sys.modules['utils.file_storage'] = MagicMock()

# 如果模块已被加载（可能被其他测试用不同 mock 加载过），reload 以使用当前 mock
for _mod in [
    'model.ai_tool_pipeline_steps', 'model.ai_tools', 'model.runninghub_slots',
    'task.pipeline_drivers.base_pipeline_driver',
    'task.pipeline_drivers.face_mask_driver',
    'task.pipeline_drivers.implementation_retry_driver',
    'task.pipeline_drivers',
]:
    if _mod in sys.modules:
        importlib.reload(sys.modules[_mod])

from task.pipeline_drivers import PipelineDriverFactory
from task.pipeline_drivers.face_mask_driver import FaceMaskPipelineDriver
from task.pipeline_drivers.implementation_retry_driver import ImplementationRetryPipelineDriver

# 恢复所有被 mock 的 sys.modules 条目，防止污染后续测试
for _key, _orig in _saved_modules.items():
    if _orig is not None:
        sys.modules[_key] = _orig
    else:
        sys.modules.pop(_key, None)


class TestPipelineDriverFactoryCreateDriver(unittest.TestCase):
    """测试 PipelineDriverFactory.create_driver 方法"""

    def test_face_mask_returns_driver(self):
        """face_mask 类型应返回 FaceMaskPipelineDriver 实例"""
        driver = PipelineDriverFactory.create_driver('face_mask')
        self.assertIsNotNone(driver)
        self.assertIsInstance(driver, FaceMaskPipelineDriver)

    def test_implementation_retry_returns_driver(self):
        """implementation_retry 类型应返回 ImplementationRetryPipelineDriver 实例"""
        driver = PipelineDriverFactory.create_driver('implementation_retry')
        self.assertIsNotNone(driver)
        self.assertIsInstance(driver, ImplementationRetryPipelineDriver)

    def test_unknown_type_returns_none(self):
        """未知类型应返回 None"""
        driver = PipelineDriverFactory.create_driver('unknown_type')
        self.assertIsNone(driver)


class TestFaceMaskPipelineDriverExecute(unittest.TestCase):
    """测试 FaceMaskPipelineDriver.execute 方法"""

    def setUp(self):
        self.driver = FaceMaskPipelineDriver()
        self.step = MagicMock()
        self.ai_tool = MagicMock()
        self.ai_tool.user_id = 42

    def test_missing_video_path_returns_error(self):
        """缺少 video_path 参数时返回失败"""
        self.step.get_params_dict.return_value = {}

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertFalse(result['success'])
        self.assertIn('缺少 video_path', result['error'])

    def test_none_video_path_returns_error(self):
        """video_path 为 None 时返回失败"""
        self.step.get_params_dict.return_value = {'video_path': None}

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertFalse(result['success'])
        self.assertIn('缺少 video_path', result['error'])

    @patch('task.async_drivers.runninghub_face_mask_driver.RunningHubFaceMaskDriver')
    def test_submit_success_returns_async_task_id(self, MockDriverClass):
        """提交成功时返回 async_task_id"""
        self.step.get_params_dict.return_value = {'video_path': '/tmp/test.mp4'}
        self.step.id = 100

        mock_driver = MagicMock()
        mock_driver.submit_with_slot_management = AsyncMock(return_value={
            'success': True,
            'async_task_id': 200,
            'project_id': 'rh-task-123',
        })
        MockDriverClass.return_value = mock_driver

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertTrue(result['success'])
        self.assertEqual(result['async_task_id'], 200)

    @patch('task.async_drivers.runninghub_face_mask_driver.RunningHubFaceMaskDriver')
    def test_slot_full_passes_through_error(self, MockDriverClass):
        """槽位满时透传 SLOT_FULL 错误"""
        self.step.get_params_dict.return_value = {'video_path': '/tmp/test.mp4'}
        self.step.id = 100

        mock_driver = MagicMock()
        mock_driver.submit_with_slot_management = AsyncMock(return_value={
            'success': False,
            'error': '槽位已满',
            'error_type': 'SLOT_FULL',
            'async_task_id': 201,
            'retry': True,
        })
        MockDriverClass.return_value = mock_driver

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'SLOT_FULL')
        self.assertTrue(result['retry'])

    @patch('task.async_drivers.runninghub_face_mask_driver.RunningHubFaceMaskDriver')
    def test_exception_returns_error(self, MockDriverClass):
        """提交异常时返回错误信息"""
        self.step.get_params_dict.return_value = {'video_path': '/tmp/test.mp4'}
        self.step.id = 100

        mock_driver = MagicMock()
        mock_driver.submit_with_slot_management = AsyncMock(
            side_effect=RuntimeError("unexpected crash")
        )
        MockDriverClass.return_value = mock_driver

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertFalse(result['success'])
        self.assertIn('提交人脸遮盖任务异常', result['error'])


class TestImplementationRetryPipelineDriverExecute(unittest.TestCase):
    """测试 ImplementationRetryPipelineDriver.execute 方法"""

    def setUp(self):
        self.driver = ImplementationRetryPipelineDriver()
        self.step = MagicMock()
        self.ai_tool = MagicMock()
        self.ai_tool.id = 50
        self.ai_tool.implementation = 1

    def test_missing_target_implementation_returns_error(self):
        """缺少 target_implementation 参数时返回失败"""
        self.step.get_params_dict.return_value = {}

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertFalse(result['success'])
        self.assertIn('缺少 target_implementation', result['error'])

    @patch('task.pipeline_drivers.implementation_retry_driver.get_implementation_id', return_value=0)
    def test_unknown_implementation_returns_error(self, mock_get_id):
        """未知的实现方名称（返回 0）时返回失败"""
        self.step.get_params_dict.return_value = {'target_implementation': 'unknown_impl'}

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertFalse(result['success'])
        self.assertIn('未知的实现方', result['error'])

    @patch('task.pipeline_drivers.implementation_retry_driver.get_implementation_id', return_value=2)
    @patch('task.pipeline_drivers.implementation_retry_driver.AIToolsModel')
    def test_success_updates_ai_tool(self, MockAIToolsModel, mock_get_id):
        """成功时更新 ai_tools 并返回成功结果"""
        self.step.get_params_dict.return_value = {'target_implementation': 'kling_duomi_v1'}

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertTrue(result['success'])
        self.assertIn('result_data', result)
        self.assertEqual(result['result_data']['new_implementation_name'], 'kling_duomi_v1')
        MockAIToolsModel.update.assert_called_once()

    @patch('task.pipeline_drivers.implementation_retry_driver.get_implementation_id', return_value=2)
    @patch('task.pipeline_drivers.implementation_retry_driver.AIToolsModel')
    def test_success_result_data_contains_old_and_new(self, MockAIToolsModel, mock_get_id):
        """成功返回的 result_data 应包含新旧实现方信息"""
        self.ai_tool.implementation = 1
        self.step.get_params_dict.return_value = {'target_implementation': 'kling_duomi_v1'}

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertTrue(result['success'])
        self.assertEqual(result['result_data']['old_implementation'], 1)
        self.assertEqual(result['result_data']['new_implementation'], 2)

    def test_exception_returns_error(self):
        """异常时返回失败"""
        self.step.get_params_dict = MagicMock(side_effect=RuntimeError("db error"))

        result = asyncio.run(self.driver.execute(self.step, self.ai_tool))

        self.assertFalse(result['success'])
        self.assertIn('实现方重试异常', result['error'])


if __name__ == '__main__':
    unittest.main()
