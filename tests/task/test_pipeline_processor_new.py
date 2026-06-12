"""
PipelineProcessor 单元测试

测试 Pipeline 编排器的核心逻辑方法。
所有外部依赖（model、task.pipeline_drivers）均使用 mock。
"""
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Mock 外部依赖（import 前置）
_saved_modules = {
    'model': sys.modules.get('model'),
    'model.ai_tool_pipeline_steps': sys.modules.get('model.ai_tool_pipeline_steps'),
    'task.pipeline_drivers': sys.modules.get('task.pipeline_drivers'),
    'config.constant': sys.modules.get('config.constant'),
    'config.config_util': sys.modules.get('config.config_util'),
}

# 创建 mock 的 model 模块
mock_model = MagicMock()
mock_model.PipelineStepModel = MagicMock()
mock_model.PipelineStep = MagicMock()
mock_model.PipelineStepStatus = MagicMock()
mock_model.PipelineStepStatus.PENDING = 'PENDING'
mock_model.PipelineStepStatus.PROCESSING = 'PROCESSING'
mock_model.PipelineStepStatus.COMPLETED = 'COMPLETED'
mock_model.PipelineStepStatus.FAILED = 'FAILED'
mock_model.PipelineStage = MagicMock()
mock_model.PipelineStage.PARAM_PREPARE = 'param_prepare'
mock_model.PipelineStage.BEFORE_FINISH = 'before_finish'
mock_model.AIToolsModel = MagicMock()
mock_model.AITool = MagicMock()
sys.modules['model'] = mock_model

mock_pipeline_steps = MagicMock()
mock_pipeline_steps.PipelineStepStatus = mock_model.PipelineStepStatus
mock_pipeline_steps.PipelineStage = mock_model.PipelineStage
sys.modules['model.ai_tool_pipeline_steps'] = mock_pipeline_steps

mock_pipeline_drivers = MagicMock()
mock_pipeline_drivers.PipelineDriverFactory = MagicMock()
sys.modules['task.pipeline_drivers'] = mock_pipeline_drivers

mock_constant = MagicMock()
sys.modules['config.constant'] = mock_constant

mock_config_util = MagicMock()
sys.modules['config.config_util'] = mock_config_util

from task.pipeline_processor import PipelineProcessor


class TestCalculateRetryDelay(unittest.TestCase):
    """测试 PipelineProcessor._calculate_retry_delay()"""

    def test_retry_count_0(self):
        """重试次数 0 返回 30 秒"""
        result = PipelineProcessor._calculate_retry_delay(0)
        self.assertEqual(result, 30)

    def test_retry_count_1(self):
        """重试次数 1 返回 60 秒"""
        result = PipelineProcessor._calculate_retry_delay(1)
        self.assertEqual(result, 60)

    def test_retry_count_2(self):
        """重试次数 2 返回 120 秒"""
        result = PipelineProcessor._calculate_retry_delay(2)
        self.assertEqual(result, 120)

    def test_retry_count_3(self):
        """重试次数 3 返回 300 秒"""
        result = PipelineProcessor._calculate_retry_delay(3)
        self.assertEqual(result, 300)

    def test_retry_count_4(self):
        """重试次数 4 返回 300 秒（最大值）"""
        result = PipelineProcessor._calculate_retry_delay(4)
        self.assertEqual(result, 300)

    def test_retry_count_large(self):
        """重试次数超过数组长度返回 300 秒"""
        result = PipelineProcessor._calculate_retry_delay(10)
        self.assertEqual(result, 300)


class TestCreateParamPrepareSteps(unittest.TestCase):
    """测试 PipelineProcessor.create_param_prepare_steps()"""

    def test_delegates_to_factory(self):
        """委托给 PipelineDriverFactory"""
        mock_pipeline_drivers.PipelineDriverFactory.create_param_prepare_steps.return_value = [1, 2, 3]

        result = PipelineProcessor.create_param_prepare_steps(100, 'generate_video')

        self.assertEqual(result, [1, 2, 3])
        mock_pipeline_drivers.PipelineDriverFactory.create_param_prepare_steps.assert_called_once_with(100, 'generate_video')


class TestCreateBeforeFinishSteps(unittest.TestCase):
    """测试 PipelineProcessor.create_before_finish_steps()"""

    def test_delegates_to_factory(self):
        """委托给 PipelineDriverFactory"""
        mock_pipeline_drivers.PipelineDriverFactory.create_before_finish_steps.return_value = [4, 5]

        result = PipelineProcessor.create_before_finish_steps(100, 'generate_video', 1, 'timeout')

        self.assertEqual(result, [4, 5])
        mock_pipeline_drivers.PipelineDriverFactory.create_before_finish_steps.assert_called_once_with(
            100, 'generate_video', 1, 'timeout'
        )


class TestGetPendingSteps(unittest.TestCase):
    """测试 PipelineProcessor.get_pending_steps()"""

    def test_delegates_to_model(self):
        """委托给 PipelineStepModel"""
        mock_steps = [MagicMock(), MagicMock()]
        mock_model.PipelineStepModel.get_pending_steps.return_value = mock_steps

        result = PipelineProcessor.get_pending_steps(100, 'param_prepare')

        self.assertEqual(result, mock_steps)
        mock_model.PipelineStepModel.get_pending_steps.assert_called_once_with(100, 'param_prepare')


class TestGetAllSteps(unittest.TestCase):
    """测试 PipelineProcessor.get_all_steps()"""

    def test_delegates_to_model(self):
        """委托给 PipelineStepModel"""
        mock_steps = [MagicMock(), MagicMock()]
        mock_model.PipelineStepModel.get_by_ai_tool_and_stage.return_value = mock_steps

        result = PipelineProcessor.get_all_steps(100, 'param_prepare')

        self.assertEqual(result, mock_steps)
        mock_model.PipelineStepModel.get_by_ai_tool_and_stage.assert_called_once_with(100, 'param_prepare')


class TestHasSteps(unittest.TestCase):
    """测试 PipelineProcessor.has_steps()"""

    def test_returns_true_when_steps_exist(self):
        """存在步骤时返回 True"""
        mock_model.PipelineStepModel.has_steps.return_value = True

        result = PipelineProcessor.has_steps(100, 'param_prepare')

        self.assertTrue(result)

    def test_returns_false_when_no_steps(self):
        """不存在步骤时返回 False"""
        mock_model.PipelineStepModel.has_steps.return_value = False

        result = PipelineProcessor.has_steps(100, 'param_prepare')

        self.assertFalse(result)


class TestApplyResults(unittest.TestCase):
    """测试 PipelineProcessor.apply_results()"""

    def setUp(self):
        """每个测试前重置 mock 状态"""
        mock_model.AIToolsModel.reset_mock()
        mock_model.PipelineStepModel.reset_mock()

    def test_apply_face_mask_result(self):
        """应用 face_mask 步骤结果到 ai_tool"""
        mock_step = MagicMock()
        mock_step.status = 'COMPLETED'
        mock_step.step_type = 'face_mask'
        mock_step.result_url = 'http://example.com/masked_video.mp4'

        mock_model.PipelineStepModel.get_by_ai_tool_and_stage.return_value = [mock_step]

        mock_ai_tool = MagicMock()
        mock_ai_tool.id = 100

        PipelineProcessor.apply_results(mock_ai_tool, 'param_prepare')

        mock_model.AIToolsModel.update.assert_called_once_with(100, video_path='http://example.com/masked_video.mp4')

    def test_skip_non_completed_steps(self):
        """跳过未完成的步骤"""
        mock_step = MagicMock()
        mock_step.status = 'PENDING'
        mock_step.step_type = 'face_mask'

        mock_model.PipelineStepModel.get_by_ai_tool_and_stage.return_value = [mock_step]

        mock_ai_tool = MagicMock()
        mock_ai_tool.id = 100

        PipelineProcessor.apply_results(mock_ai_tool, 'param_prepare')

        mock_model.AIToolsModel.update.assert_not_called()

    def test_skip_non_face_mask_steps(self):
        """跳过非 face_mask 步骤"""
        mock_step = MagicMock()
        mock_step.status = 'COMPLETED'
        mock_step.step_type = 'other_type'

        mock_model.PipelineStepModel.get_by_ai_tool_and_stage.return_value = [mock_step]

        mock_ai_tool = MagicMock()
        mock_ai_tool.id = 100

        PipelineProcessor.apply_results(mock_ai_tool, 'param_prepare')

        mock_model.AIToolsModel.update.assert_not_called()


if __name__ == '__main__':
    unittest.main()
