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
_reloaded_modules = [
    'model.ai_tool_pipeline_steps', 'model.ai_tools', 'model.runninghub_slots',
    'task.pipeline_drivers.base_pipeline_driver',
    'task.pipeline_drivers.face_mask_driver',
    'task.pipeline_drivers.implementation_retry_driver',
    'task.pipeline_drivers',
]
for _mod in _reloaded_modules:
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

# 清除被 reload 过的模块缓存，它们在 mock 环境下导入，需强制重新导入
for _mod in _reloaded_modules:
    sys.modules.pop(_mod, None)


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


# ==================== 新增：PipelineDriverFactory.create_param_prepare_steps 测试 ====================

class TestCreateParamPrepareSteps(unittest.TestCase):
    """测试 PipelineDriverFactory.create_param_prepare_steps()"""

    @patch('task.pipeline_drivers.AIToolsModel')
    @patch('task.pipeline_drivers.UnifiedConfigRegistry')
    def test_unknown_task_type_returns_empty(self, MockRegistry, MockAITools):
        """未知任务类型返回空列表"""
        MockRegistry.get_by_id.return_value = None

        result = PipelineDriverFactory.create_param_prepare_steps(ai_tool_id=1, ai_tool_type=999)
        self.assertEqual(result, [])

    @patch('task.pipeline_drivers.AIToolsModel')
    @patch('task.pipeline_drivers.UnifiedConfigRegistry')
    def test_no_rule_for_key_returns_empty(self, MockRegistry, MockAITools):
        """没有匹配的规则返回空列表"""
        mock_config = MagicMock()
        mock_config.key = 'some_unknown_key'
        MockRegistry.get_by_id.return_value = mock_config

        result = PipelineDriverFactory.create_param_prepare_steps(ai_tool_id=1, ai_tool_type=1)
        self.assertEqual(result, [])

    @patch('task.pipeline_drivers.AIToolsModel')
    @patch('task.pipeline_drivers.UnifiedConfigRegistry')
    def test_ai_tool_not_found_returns_empty(self, MockRegistry, MockAITools):
        """ai_tool 不存在返回空列表"""
        mock_config = MagicMock()
        mock_config.key = 'seedance_2_0_image_to_video'
        MockRegistry.get_by_id.return_value = mock_config
        MockAITools.get_by_id.return_value = None

        result = PipelineDriverFactory.create_param_prepare_steps(ai_tool_id=999, ai_tool_type=1)
        self.assertEqual(result, [])


# ==================== 新增：PipelineDriverFactory.create_before_finish_steps 测试 ====================

class TestCreateBeforeFinishSteps(unittest.TestCase):
    """测试 PipelineDriverFactory.create_before_finish_steps()"""

    @patch('task.pipeline_drivers.UnifiedConfigRegistry')
    def test_no_task_config_returns_empty(self, MockRegistry):
        """无任务配置返回空列表"""
        MockRegistry.get_by_id.return_value = None

        result = PipelineDriverFactory.create_before_finish_steps(
            ai_tool_id=1, ai_tool_type=999,
            failed_implementation=1, failure_reason='timeout'
        )
        self.assertEqual(result, [])

    @patch('task.pipeline_drivers.UnifiedConfigRegistry')
    def test_no_implementations_returns_empty(self, MockRegistry):
        """任务配置无实现方返回空列表"""
        mock_config = MagicMock()
        mock_config.implementations = None
        MockRegistry.get_by_id.return_value = mock_config

        result = PipelineDriverFactory.create_before_finish_steps(
            ai_tool_id=1, ai_tool_type=1,
            failed_implementation=1, failure_reason='error'
        )
        self.assertEqual(result, [])

    @patch('task.pipeline_drivers.VideoDriverFactory')
    @patch('task.pipeline_drivers.ImplementationAttemptModel')
    @patch('task.pipeline_drivers.UnifiedConfigRegistry')
    def test_no_alternatives_returns_empty(self, MockRegistry, MockAttemptModel, MockDriverFactory):
        """无可用替代实现方返回空列表"""
        mock_config = MagicMock()
        mock_config._get_implementations_info.return_value = [
            {'name': 'impl_a', 'sort_order': 100},
            {'name': 'impl_b', 'sort_order': 200},
        ]
        MockRegistry.get_by_id.return_value = mock_config

        # 所有实现方都已尝试过
        MockAttemptModel.get_attempted_implementations.return_value = {1, 2}

        from config.unified_config import get_implementation_name
        with patch('task.pipeline_drivers.get_implementation_name', return_value='impl_a'):
            result = PipelineDriverFactory.create_before_finish_steps(
                ai_tool_id=1, ai_tool_type=1,
                failed_implementation=1, failure_reason='error'
            )
        self.assertEqual(result, [])

    @patch('task.pipeline_drivers.VideoDriverFactory')
    @patch('task.pipeline_drivers.ImplementationAttemptModel')
    @patch('task.pipeline_drivers.UnifiedConfigRegistry')
    @patch('task.pipeline_drivers.PipelineStepModel')
    def test_creates_retry_steps_for_alternatives(
        self, MockStepModel, MockRegistry, MockAttemptModel, MockDriverFactory
    ):
        """为可用替代方创建重试步骤"""
        mock_config = MagicMock()
        mock_config._get_implementations_info.return_value = [
            {'name': 'impl_a', 'sort_order': 100},
            {'name': 'impl_b', 'sort_order': 200},
        ]
        MockRegistry.get_by_id.return_value = mock_config

        # 只尝试过 impl_a
        MockAttemptModel.get_attempted_implementations.return_value = {1}

        # impl_b 的驱动可用
        MockRegistry.get_implementation.return_value = MagicMock(is_enabled=MagicMock(return_value=True))
        MockDriverFactory.create_driver_by_implementation.return_value = MagicMock()

        MockStepModel.create.return_value = 42

        with patch('task.pipeline_drivers.get_implementation_name', side_effect=lambda x: 'impl_a' if x == 1 else 'impl_b'):
            with patch('task.pipeline_drivers.get_implementation_id', return_value=2):
                result = PipelineDriverFactory.create_before_finish_steps(
                    ai_tool_id=1, ai_tool_type=1,
                    failed_implementation=1, failure_reason='error'
                )
        # 应创建了至少一个重试步骤
        self.assertGreater(len(result), 0)
