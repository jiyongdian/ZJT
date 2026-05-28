"""
Pipeline 驱动工厂
根据 step_type 创建对应的 pipeline 驱动实例。
"""
import logging
from typing import Optional, List, Dict, Any

from model import PipelineStepType, PipelineStepModel, PipelineStage, AIToolsModel
from config.unified_config import (
    UnifiedConfigRegistry,
    get_implementation_id,
    get_implementation_name,
    DriverKey
)

from .base_pipeline_driver import BasePipelineDriver
from .face_mask_driver import FaceMaskPipelineDriver
from .implementation_retry_driver import ImplementationRetryPipelineDriver

logger = logging.getLogger(__name__)

# 驱动注册表
_DRIVER_MAP = {
    PipelineStepType.FACE_MASK: FaceMaskPipelineDriver,
    PipelineStepType.IMPLEMENTATION_RETRY: ImplementationRetryPipelineDriver,
}


class PipelineDriverFactory:
    """Pipeline 驱动工厂"""

    @staticmethod
    def create_driver(step_type: str) -> Optional[BasePipelineDriver]:
        """
        根据 step_type 创建驱动实例

        Args:
            step_type: 步骤类型（如 'face_mask', 'implementation_retry'）

        Returns:
            驱动实例，未找到返回 None
        """
        driver_class = _DRIVER_MAP.get(step_type)
        if driver_class:
            return driver_class()
        logger.warning(f"Unknown pipeline step type: {step_type}")
        return None

    # ==================== param_prepare 步骤创建规则 ====================

    # 需要人脸遮盖的任务类型（Seedance 2.0 带视频输入）
    # key 为 UnifiedTaskConfig.key，value 为步骤配置
    _PARAM_PREPARE_RULES = {
        DriverKey.SEEDANCE_2_0_IMAGE_TO_VIDEO: {
            'condition': lambda ai_tool: bool(getattr(ai_tool, 'video_path', None)),
            'steps': [
                {
                    'step_type': PipelineStepType.FACE_MASK,
                    'params_fn': lambda ai_tool: {'video_path': ai_tool.video_path}
                }
            ]
        },
        DriverKey.SEEDANCE_2_0_FAST_IMAGE_TO_VIDEO: {
            'condition': lambda ai_tool: bool(getattr(ai_tool, 'video_path', None)),
            'steps': [
                {
                    'step_type': PipelineStepType.FACE_MASK,
                    'params_fn': lambda ai_tool: {'video_path': ai_tool.video_path}
                }
            ]
        },
    }

    @classmethod
    def create_param_prepare_steps(
        cls,
        ai_tool_id: int,
        ai_tool_type: int
    ) -> List[int]:
        """
        根据任务类型自动创建 param_prepare 步骤

        Args:
            ai_tool_id: ai_tools.id
            ai_tool_type: ai_tools.type（任务类型 ID）

        Returns:
            创建的步骤 ID 列表，无步骤则返回空列表
        """
        task_config = UnifiedConfigRegistry.get_by_id(ai_tool_type)
        if not task_config:
            return []

        rule = cls._PARAM_PREPARE_RULES.get(task_config.key)
        if not rule:
            return []

        # 获取 ai_tool 对象用于条件判断
        ai_tool = AIToolsModel.get_by_id(ai_tool_id)
        if not ai_tool:
            return []

        # 检查条件
        if not rule['condition'](ai_tool):
            return []

        # 创建步骤
        step_ids = []
        for idx, step_cfg in enumerate(rule['steps']):
            params = step_cfg['params_fn'](ai_tool) if step_cfg.get('params_fn') else None
            step_id = PipelineStepModel.create(
                ai_tool_id=ai_tool_id,
                stage=PipelineStage.PARAM_PREPARE,
                step_type=step_cfg['step_type'],
                step_order=idx,
                params=params
            )
            step_ids.append(step_id)

        if step_ids:
            logger.info(
                f"Created {len(step_ids)} param_prepare steps for ai_tool {ai_tool_id} "
                f"(type={task_config.key}): {step_ids}"
            )

        return step_ids

    # ==================== before_finish 步骤创建 ====================

    # 最大重试次数（替代实现方数量上限）
    _MAX_RETRY_IMPLEMENTATIONS = 3

    @classmethod
    def create_before_finish_steps(
        cls,
        ai_tool_id: int,
        ai_tool_type: int,
        failed_implementation: int,
        failure_reason: str
    ) -> List[int]:
        """
        创建 before_finish 重试步骤（选择替代实现方）

        Args:
            ai_tool_id: ai_tools.id
            ai_tool_type: ai_tools.type
            failed_implementation: 刚失败的实现方 ID
            failure_reason: 失败原因

        Returns:
            创建的步骤 ID 列表，无可用替代则返回空列表
        """
        task_config = UnifiedConfigRegistry.get_by_id(ai_tool_type)
        if not task_config or not task_config.implementations:
            return []

        failed_impl_name = get_implementation_name(failed_implementation)

        # 收集替代实现方（排除已失败的）
        alternatives = []
        for impl_name in task_config.implementations:
            if impl_name != failed_impl_name:
                alternatives.append(impl_name)

        if not alternatives:
            logger.info(f"No alternative implementations for ai_tool {ai_tool_id}")
            return []

        # 限制重试数量
        alternatives = alternatives[:cls._MAX_RETRY_IMPLEMENTATIONS]

        # 创建重试步骤
        step_ids = []
        for idx, alt_impl_name in enumerate(alternatives):
            step_id = PipelineStepModel.create(
                ai_tool_id=ai_tool_id,
                stage=PipelineStage.BEFORE_FINISH,
                step_type=PipelineStepType.IMPLEMENTATION_RETRY,
                step_order=idx,
                params={
                    'target_implementation': alt_impl_name,
                    'original_failure': failure_reason,
                    'failed_implementation': failed_impl_name
                }
            )
            step_ids.append(step_id)

        if step_ids:
            logger.info(
                f"Created {len(step_ids)} before_finish retry steps for ai_tool {ai_tool_id}: "
                f"alternatives={[s for s in alternatives]}, failed={failed_impl_name}"
            )

        return step_ids
