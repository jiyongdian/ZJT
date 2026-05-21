"""
RunningHub 异步任务处理
在 scheduler 进程中定时轮询 RunningHub 任务状态并更新数据库
"""
import logging
from datetime import datetime
from typing import Any

from model import RunningHubAsyncTasksModel, RunningHubAsyncTaskStatus
from task.async_drivers.runninghub_audio_driver import RunningHubAudioDriver

logger = logging.getLogger(__name__)


def _handle_audio_task_success(task: Any, result_url: str):
    """
    处理音频任务成功的情况：更新角色的 default_voice

    Args:
        task: RunningHubAsyncTask 对象
        result_url: 生成的音频 URL
    """
    if not task.character_id:
        return

    try:
        from model.character import CharacterModel
        CharacterModel.update(task.character_id, default_voice=result_url)
        logger.info(f"Updated character {task.character_id} default_voice: {result_url}")
    except Exception as e:
        logger.error(f"Failed to update character default_voice: {e}")


def process_runninghub_async_tasks(app=None):
    """
    处理 RunningHub 异步任务（在 scheduler 进程中定时执行）

    流程：
    1. 从 runninghub_async_tasks 表获取 QUEUED/PROCESSING 状态的任务
    2. 调用 RunningHubAudioDriver.check_status() 查询远程状态
    3. 根据结果更新数据库
    """
    import asyncio

    try:
        pending_tasks = RunningHubAsyncTasksModel.get_pending_tasks(limit=50)

        if not pending_tasks:
            return

        logger.info(f"开始处理 {len(pending_tasks)} 个 RunningHub 异步任务")

        driver = RunningHubAudioDriver()

        for task in pending_tasks:
            try:
                # 增加尝试次数
                RunningHubAsyncTasksModel.increment_try_count(task.task_key)
                task.try_count += 1

                # 检查是否超过最大尝试次数
                if task.try_count > task.max_attempts:
                    logger.error(f"RunningHub 异步任务超时: {task.task_key}, 尝试次数: {task.try_count}/{task.max_attempts}")
                    RunningHubAsyncTasksModel.update_status(
                        task_key=task.task_key,
                        status=RunningHubAsyncTaskStatus.TIMEOUT,
                        error_message=f"超过最大尝试次数 {task.max_attempts}"
                    )
                    continue

                # 更新为处理中状态（仅在第一次尝试时）
                if task.try_count == 1:
                    RunningHubAsyncTasksModel.update_status(
                        task_key=task.task_key,
                        status=RunningHubAsyncTaskStatus.PROCESSING
                    )

                # 查询 RunningHub 任务状态
                status_result = asyncio.run(driver.check_status(task.runninghub_task_id))

                if status_result.get('status') == 'SUCCESS':
                    result_url = status_result.get('result_url')
                    RunningHubAsyncTasksModel.update_status(
                        task_key=task.task_key,
                        status=RunningHubAsyncTaskStatus.COMPLETED,
                        result_url=result_url
                    )
                    _handle_audio_task_success(task, result_url)
                    logger.info(f"RunningHub 异步任务完成: {task.task_key}, result: {result_url}")

                elif status_result.get('status') == 'FAILED':
                    error_message = status_result.get('error', '任务失败')
                    RunningHubAsyncTasksModel.update_status(
                        task_key=task.task_key,
                        status=RunningHubAsyncTaskStatus.FAILED,
                        error_message=error_message
                    )
                    logger.error(f"RunningHub 异步任务失败: {task.task_key}, error: {error_message}")

                # RUNNING 状态不做处理，等待下次轮询

            except Exception as e:
                logger.error(f"处理 RunningHub 异步任务异常: {task.task_key}, error: {str(e)}")

        # 清理旧任务（7天前）
        try:
            RunningHubAsyncTasksModel.cleanup_old_tasks(days=7)
        except Exception as e:
            logger.error(f"清理旧 RunningHub 异步任务失败: {e}")

    except Exception as e:
        logger.error(f"处理 RunningHub 异步任务失败: {e}")
