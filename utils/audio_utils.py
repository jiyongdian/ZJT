"""
音频文件工具函数
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests

from config.constant import UploadPathConstants
from utils.project_path import get_upload_subdir, get_project_root

logger = logging.getLogger(__name__)

# 音频扩展名白名单
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'}


def download_and_save_character_voice(
    remote_url: str,
    filename_prefix: str = "rh_voice"
) -> Optional[str]:
    """
    下载远程音频文件并保存到 upload/character/voice/ 目录

    Args:
        remote_url: 远程音频 URL（如 RunningHub 结果 URL）
        filename_prefix: 文件名前缀

    Returns:
        相对路径（无前导 /），如 "upload/character/voice/rh_voice_20260522_143025_a1b2c3d4.wav"
        失败返回 None
    """
    try:
        # 推断扩展名
        parsed = urlparse(remote_url)
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext not in AUDIO_EXTENSIONS:
            ext = '.wav'  # 默认 wav

        # 生成唯一文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        uid = uuid.uuid4().hex[:8]
        filename = f"{filename_prefix}_{timestamp}_{uid}{ext}"

        # 获取目标目录
        voice_dir = get_upload_subdir(UploadPathConstants.CHARACTER_VOICE_DIR)
        file_path = os.path.join(voice_dir, filename)

        # 下载文件
        logger.info(f"开始下载音频: {remote_url} -> {file_path}")
        response = requests.get(remote_url, timeout=120, stream=True)
        response.raise_for_status()

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # 返回相对路径（相对于项目根目录）
        project_root = get_project_root()
        local_path = os.path.relpath(file_path, project_root)
        # 统一使用正斜杠（兼容 Windows）
        local_path = local_path.replace('\\', '/')

        logger.info(f"音频下载完成: {local_path}")
        return local_path

    except Exception as e:
        logger.error(f"下载音频失败: {e}", exc_info=True)
        return None
