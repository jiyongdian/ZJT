"""
实现方重试 Pipeline 驱动
用于 before_finish 阶段，切换不同的实现方（供应商）重新提交任务。
"""
import logging
from typing import Dict, Any

from .base_pipeline_driver import BasePipelineDriver
from model import PipelineStep, AITool, AIToolsModel, TasksModel
from config.constant import AI_TOOL_STATUS_PENDING, TASK_STATUS_QUEUED
from config.unified_config import get_implementation_id

logger = logging.getLogger(__name__)


class ImplementationRetryPipelineDriver(BasePipelineDriver):
    """
    实现方重试 Pipeline 驱动

    流程：
    1. 从 step.params 中获取 target_implementation（目标实现方名称）
    2. 更新 ai_tools.implementation 为目标实现方 ID
    3. 将 ai_tools 状态设回 PENDING
    4. 主流程会自动用新实现方重新提交任务

    此驱动不创建 async_task，直接完成步骤。
    """

    def __init__(self):
        super().__init__("implementation_retry")

    async def execute(self, step: PipelineStep, ai_tool: AITool) -> Dict[str, Any]:
        """
        切换实现方并将 ai_tool 设回 PENDING 状态

        Args:
            step: PipelineStep 对象，params 中应包含 target_implementation
            ai_tool: AITool 对象

        Returns:
            Dict 包含 success 和 result_data 或 error
        """
        try:
            params = step.get_params_dict()
            target_implementation = params.get('target_implementation')

            if not target_implementation:
                return {
                    'success': False,
                    'error': '缺少 target_implementation 参数'
                }

            # 获取目标实现方 ID
            target_impl_id = get_implementation_id(target_implementation)
            if not target_impl_id or target_impl_id == 0:
                return {
                    'success': False,
                    'error': f'未知的实现方: {target_implementation}'
                }

            # 在更新前保存旧的 implementation 值（用于 result_data 记录）
            old_implementation = ai_tool.implementation

            # 更新 ai_tools 实现方和状态
            AIToolsModel.update(
                ai_tool.id,
                implementation=target_impl_id,
                status=AI_TOOL_STATUS_PENDING,
                project_id=None,  # 清除旧的 project_id，让主流程重新提交
                message=None  # 清除旧的错误信息
            )

            # 同步更新 tasks 状态为 QUEUED，确保调度器能重新拾取
            TasksModel.update_by_task_id(ai_tool.id, status=TASK_STATUS_QUEUED)

            # 记录重试实现方尝试
            try:
                from model.implementation_attempts import ImplementationAttemptModel
                from datetime import datetime as dt
                attempt_number = step.step_order + 2  # step_order 从 0 开始，首次是 1
                ImplementationAttemptModel.create(
                    ai_tool_id=ai_tool.id,
                    implementation=target_impl_id,
                    attempt_number=attempt_number,
                    status=0,
                    started_at=dt.now()
                )
            except Exception as e:
                self.logger.warning(f"Failed to record retry attempt for ai_tool {ai_tool.id}: {e}")

            self.logger.info(
                f"Implementation retry: ai_tool_id={ai_tool.id}, "
                f"old_impl={old_implementation}, new_impl={target_impl_id} ({target_implementation})"
            )

            return {
                'success': True,
                'result_data': {
                    'old_implementation': old_implementation,
                    'new_implementation': target_impl_id,
                    'new_implementation_name': target_implementation
                }
            }

        except Exception as e:
            self.logger.error(f"Implementation retry error: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'实现方重试异常: {str(e)}'
            }
