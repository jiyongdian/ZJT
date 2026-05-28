"""
Pipeline 驱动抽象基类
所有 pipeline 步骤驱动都需要继承此基类并实现其抽象方法。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

from model import PipelineStep, AITool


logger = logging.getLogger(__name__)


class BasePipelineDriver(ABC):
    """
    Pipeline 驱动抽象基类

    所有 pipeline 步骤驱动必须继承此类并实现以下方法：
    - execute: 执行步骤（提交任务或直接处理）
    - check_status: 检查已提交步骤的状态（可选，仅当 execute 创建了 async_task 时需要）
    """

    def __init__(self, driver_name: str):
        """
        初始化 pipeline 驱动

        Args:
            driver_name: 驱动名称，如 "face_mask" 等
        """
        self.driver_name = driver_name
        self.logger = logging.getLogger(f"{__name__}.{driver_name}")

    @abstractmethod
    async def execute(self, step: PipelineStep, ai_tool: AITool) -> Dict[str, Any]:
        """
        执行 pipeline 步骤

        Args:
            step: PipelineStep 对象
            ai_tool: AITool 对象

        Returns:
            Dict[str, Any]: 返回结果字典
                直接完成时:
                    - success: True
                    - result_data: 步骤结果（可选，JSON 可序列化对象）
                创建 async_task 时:
                    - success: True
                    - async_task_id: 创建的 async_task ID
                失败时:
                    - success: False
                    - error: 错误信息
        """
        pass

    async def check_async_status(self, step: PipelineStep) -> Dict[str, Any]:
        """
        检查关联 async_task 的状态（可选实现）

        仅当 execute 创建了 async_task 时需要实现此方法。
        默认实现会查询 async_tasks 表状态。

        Args:
            step: PipelineStep 对象（已关联 async_task_id）

        Returns:
            Dict[str, Any]: 返回结果字典
                - status: "RUNNING" | "SUCCESS" | "FAILED"
                - result_data: 步骤结果（status 为 SUCCESS 时）
                - error: 错误信息（status 为 FAILED 时）
        """
        from model import AsyncTasksModel, AsyncTaskStatus

        if not step.async_task_id:
            return {'status': 'FAILED', 'error': '步骤未关联 async_task'}

        async_task = AsyncTasksModel.get_by_id(step.async_task_id)
        if not async_task:
            return {'status': 'FAILED', 'error': f'async_task {step.async_task_id} 不存在'}

        if async_task.status == AsyncTaskStatus.COMPLETED:
            result_data = {}
            if async_task.result_url:
                result_data['result_url'] = async_task.result_url
            if async_task.result_data:
                result_data.update(async_task.get_result_data_dict())
            return {'status': 'SUCCESS', 'result_data': result_data}
        elif async_task.status in (AsyncTaskStatus.FAILED, AsyncTaskStatus.TIMEOUT):
            return {'status': 'FAILED', 'error': async_task.error_message or 'async_task 失败'}
        else:
            return {'status': 'RUNNING'}
