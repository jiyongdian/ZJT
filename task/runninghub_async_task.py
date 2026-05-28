"""
RunningHub 异步任务处理
在 scheduler 进程中定时轮询 RunningHub 任务状态并更新数据库

使用通用 async_tasks 表，通过 implementation 字段区分不同的任务类型：
- RUNNINGHUB_AUDIO: 音频生成
- RUNNINGHUB_FACE_MASK: 人脸遮盖视频生成
"""
import asyncio
import logging
from datetime import datetime
from typing import Any

from model import AsyncTasksModel, AsyncTaskStatus, RunningHubSlotsModel
from model.runninghub_slots import RunningHubSlot
from config.unified_config import AsyncTaskImplementationId
from task.async_drivers.runninghub_audio_driver import RunningHubAudioDriver
from task.async_drivers.runninghub_face_mask_driver import RunningHubFaceMaskDriver

logger = logging.getLogger(__name__)

DRIVER_MAP = {
    AsyncTaskImplementationId.RUNNINGHUB_AUDIO: RunningHubAudioDriver,
    AsyncTaskImplementationId.RUNNINGHUB_FACE_MASK: RunningHubFaceMaskDriver,
}


def _setup_cdn_mapping(task: Any, local_path: str, original_url: str, character_id: int):
    """
    创建或替换 CDN mapping 记录，触发异步上传
    复用 ensure_entity_image_mapping，传入 label="voice"

    Args:
        task: AsyncTask 对象
        local_path: 本地相对路径（如 "upload/character/voice/rh_voice_xxx.wav"）
        original_url: 原始远程 URL
        character_id: 角色 ID
    """
    from utils.media_mapping_util import ensure_entity_image_mapping
    from model.media_file_mapping import MediaFileEntity

    ensure_entity_image_mapping(
        user_id=task.user_id,
        image_url=f"/{local_path}",
        entity_type=MediaFileEntity.CHARACTER,
        entity_id=character_id,
        label="voice"
    )


def _handle_audio_task_success(task: Any, result_url: str):
    """
    处理音频任务成功的情况：
    1. 下载音频到本地 upload/character/voice/
    2. 如果开启图床，创建 CDN mapping 并触发上传
    3. 更新角色的 default_voice 为本地路径

    Args:
        task: AsyncTask 对象
        result_url: RunningHub 远程音频 URL
    """
    from datetime import datetime

    params = task.get_params_dict()
    character_id = params.get('character_id')
    character_name = params.get('character_name')

    # Step 1: 下载音频到本地
    voice_url = result_url  # 默认使用远程 URL（下载失败时回退）
    local_path = None

    try:
        from utils.audio_utils import download_and_save_character_voice
        local_path = download_and_save_character_voice(
            remote_url=result_url,
            filename_prefix="rh_voice"
        )
        if local_path:
            voice_url = f"/{local_path}"
            logger.info(f"Audio saved locally, voice_url: {voice_url}")
        else:
            logger.warning(f"Failed to download audio, using remote URL: {result_url}")
    except Exception as e:
        logger.error(f"Download audio failed: {e}", exc_info=True)

    # Step 2: 如果开启 CDN 且有 character_id，创建 mapping 并触发上传
    if local_path and character_id:
        try:
            from config.config_util import get_config
            enable_cdn = get_config().get("server", {}).get("auto_upload_to_cdn", False)
            if enable_cdn:
                _setup_cdn_mapping(task, local_path, result_url, character_id)
        except Exception as e:
            logger.error(f"CDN mapping setup failed: {e}", exc_info=True)

    # Step 3: 更新角色的 default_voice
    # 优先通过 character_id 更新数据库
    if character_id:
        try:
            from model.character import CharacterModel
            CharacterModel.update(character_id, default_voice=voice_url)
            logger.info(f"Updated character {character_id} default_voice: {voice_url}")
            return
        except Exception as e:
            logger.error(f"Failed to update character default_voice by id: {e}")

    # 通过 character_name 更新角色 JSON 文件
    if character_name and task.user_id:
        try:
            from script_writer_core.file_manager import FileManager
            file_manager = FileManager()
            uid = str(task.user_id)
            world_id = params.get('world_id', uid)
            character_data = file_manager.get_character_json(character_name, uid, world_id)
            if character_data:
                character_data['default_voice'] = voice_url
                character_data['updated_at'] = datetime.now().isoformat()
                from script_writer_core.mcp_tool import _sanitize_filename
                filename = f"character_{_sanitize_filename(character_name)}.json"
                file_manager.save_json_content(uid, world_id, "characters", filename, character_data)
                logger.info(f"Updated character '{character_name}' default_voice via FileManager: {voice_url}")
            else:
                logger.warning(f"Character '{character_name}' not found in FileManager")
        except Exception as e:
            logger.error(f"Failed to update character default_voice by name: {e}")
    else:
        logger.warning(f"No character_id or character_name in task params, skipping update")

    return local_path


def _handle_face_mask_task_success(task: Any, result_url: str):
    """
    处理人脸遮盖视频任务成功的情况：
    1. 从 task.params 获取原视频路径
    2. 下载 RunningHub 返回的遮罩视频到本地缓存
    3. 将遮罩视频与原视频融合生成最终的人脸遮盖视频
    4. 返回融合后的视频路径（供 pipeline_processor 写入 step.result_url）

    Args:
        task: AsyncTask 对象
        result_url: RunningHub 远程遮罩视频 URL

    Returns:
        融合后的本地相对路径（无前导 /），失败返回 None
    """
    try:
        from utils.media_cache import download_and_cache
        from utils.face_mask_util import overlay_face_mask
        from utils.project_path import get_project_root
        from datetime import datetime

        params = task.get_params_dict()
        original_video = params.get('video_path')  # 原视频路径

        if not original_video:
            logger.error("缺少 video_path 参数，无法融合视频")
            return None

        # Step 1: 下载遮罩视频到本地缓存
        loop = asyncio.new_event_loop()
        try:
            mask_video_local = loop.run_until_complete(
                download_and_cache(result_url, task.id, "video")
            )
        finally:
            loop.close()

        if not mask_video_local:
            logger.error("下载遮罩视频失败")
            return None

        # 转换为本地绝对路径
        import os
        from utils.project_path import resolve_upload_url_to_local_path
        project_root = get_project_root()

        mask_video_abs = os.path.join(project_root, mask_video_local.lstrip('/'))

        if original_video.startswith('http://') or original_video.startswith('https://'):
            original_abs = resolve_upload_url_to_local_path(original_video)
        else:
            original_abs = os.path.join(project_root, original_video.lstrip('/'))
        if not os.path.exists(original_abs):
            logger.error(f"原视频不存在: {original_abs}")
            return None

        # Step 2: 生成输出路径
        output_dir = os.path.join(project_root, "upload", "cache", datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"face_mask_{task.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
        output_video = os.path.join(output_dir, output_filename)

        # Step 3: 融合视频（原视频 + 遮罩 -> 最终视频）
        success, final_video, error = overlay_face_mask(
            original_video=original_abs,
            mask_video=mask_video_abs,
            output_video=output_video,
            mask_color=(0, 0, 0),  # 黑色遮罩
            mask_alpha=1.0,
            threshold=128
        )

        if not success or not final_video:
            logger.error(f"融合视频失败: {error}")
            return None

        # Step 4: 返回融合后的视频相对路径（如 upload/cache/2026-05-27/face_mask_xxx.mp4）
        rel_path = os.path.relpath(final_video, project_root).replace("\\", "/")
        logger.info(f"人脸遮盖视频融合成功: /{rel_path}")
        return rel_path

    except Exception as e:
        logger.error(f"处理人脸遮盖视频失败: {e}", exc_info=True)
        return None


SUCCESS_HANDLER_MAP = {
    AsyncTaskImplementationId.RUNNINGHUB_AUDIO: _handle_audio_task_success,
    AsyncTaskImplementationId.RUNNINGHUB_FACE_MASK: _handle_face_mask_task_success,
}


def process_runninghub_async_tasks(app=None):
    """
    处理 RunningHub 异步任务（在 scheduler 进程中定时执行）

    流程：
    1. 遍历所有已注册的 RunningHub 实现（音频、人脸遮盖视频等）
    2. 对每个实现，获取 QUEUED/PROCESSING 状态的任务
    3. 调用对应 driver 的 check_status() 查询远程状态
    4. 根据结果更新数据库
    """
    import asyncio

    for impl_id, driver_class in DRIVER_MAP.items():
        try:
            pending_tasks = AsyncTasksModel.get_pending_tasks(
                implementation=impl_id,
                limit=50
            )

            if not pending_tasks:
                continue

            logger.info(f"开始处理 {len(pending_tasks)} 个 RunningHub 异步任务 (implementation={impl_id})")

            driver = driver_class()
            success_handler = SUCCESS_HANDLER_MAP.get(impl_id)

            loop = asyncio.new_event_loop()
            try:
                for task in pending_tasks:
                    try:
                        # 跳过尚未提交到外部 API 的任务（由调度器的提交流程负责）
                        if not task.external_task_id:
                            continue

                        AsyncTasksModel.increment_try_count(task.id)
                        task.try_count += 1

                        if task.try_count > task.max_attempts:
                            logger.error(f"RunningHub 异步任务超时: {task.id}, 尝试次数: {task.try_count}/{task.max_attempts}")
                            AsyncTasksModel.update_status(
                                record_id=task.id,
                                status=AsyncTaskStatus.TIMEOUT,
                                error_message=f"超过最大尝试次数 {task.max_attempts}"
                            )
                            RunningHubSlotsModel.release_slot(task.id, source=RunningHubSlot.SOURCE_ASYNC)
                            continue

                        if task.try_count == 1:
                            AsyncTasksModel.update_status(
                                record_id=task.id,
                                status=AsyncTaskStatus.PROCESSING
                            )

                        status_result = loop.run_until_complete(driver.check_status(task.external_task_id))

                        if status_result.get('status') == 'SUCCESS':
                            result_url = status_result.get('result_url')

                            local_path = None
                            if success_handler:
                                local_path = success_handler(task, result_url)

                            async_result_url = f"/{local_path}" if local_path else result_url
                            AsyncTasksModel.update_status(
                                record_id=task.id,
                                status=AsyncTaskStatus.COMPLETED,
                                result_url=async_result_url
                            )
                            RunningHubSlotsModel.release_slot(task.id, source=RunningHubSlot.SOURCE_ASYNC)
                            logger.info(f"RunningHub 异步任务完成: {task.id}, result: {async_result_url}")

                        elif status_result.get('status') == 'FAILED':
                            error_message = status_result.get('error', '任务失败')
                            AsyncTasksModel.update_status(
                                record_id=task.id,
                                status=AsyncTaskStatus.FAILED,
                                error_message=error_message
                            )
                            RunningHubSlotsModel.release_slot(task.id, source=RunningHubSlot.SOURCE_ASYNC)
                            logger.error(f"RunningHub 异步任务失败: {task.id}, error: {error_message}")

                    except Exception as e:
                        logger.error(f"处理 RunningHub 异步任务异常: {task.id}, error: {str(e)}")
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"处理 RunningHub 异步任务失败 (implementation={impl_id}): {e}")
