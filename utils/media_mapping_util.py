"""
媒体文件映射工具 - 为角色/场景/道具主图自动创建 CDN mapping

策略：
- 只对 reference_image（主图）创建 mapping，reference_images（多角度图）不处理
- 使用 (CHARACTER/LOCATION/PROPS, entity_db_id) 实体关联
- 替换主图时：删旧 mapping → 建新 mapping
"""
import logging
import os
from typing import Optional
from urllib.parse import urlparse

from utils.project_path import get_project_root

logger = logging.getLogger(__name__)


def extract_local_path_from_url(url: str) -> Optional[str]:
    """
    从图片 URL 中提取本地路径

    Examples:
        "http://localhost:8000/upload/character/pic/abc.png" → "upload/character/pic/abc.png"
        "/upload/character/pic/abc.png" → "upload/character/pic/abc.png"
        "https://external-cdn.com/image.png" → None

    Returns:
        本地相对路径（无前导 /），外部 URL 返回 None
    """
    if not url or not isinstance(url, str):
        return None

    parsed = urlparse(url)
    path = parsed.path

    if not path.startswith("/upload/"):
        return None

    return path.lstrip("/")


def ensure_entity_image_mapping(
    user_id,
    image_url: str,
    entity_type: int,
    entity_id: int
) -> Optional[int]:
    """
    为实体的主图创建 CDN mapping（删旧建新）

    Args:
        user_id: 用户 ID（str 或 int）
        image_url: 主图 URL
        entity_type: MediaFileEntity.CHARACTER / LOCATION / PROPS
        entity_id: 实体数据库 ID

    Returns:
        mapping_id，跳过或失败返回 None
    """
    from config.config_util import get_config
    from config.media_file_policy import MediaFilePolicy
    from model.media_file_mapping import MediaFileMappingModel
    from utils.cdn_util import CDNUtil
    from utils.mime_type import get_mime_type_from_extension

    # 检查 CDN 是否启用
    if not get_config().get("server", {}).get("auto_upload_to_cdn", False):
        return None

    # 提取本地路径
    local_path = extract_local_path_from_url(image_url)
    if not local_path:
        return None

    # 删除旧的 mapping（处理 UNIQUE 约束）
    existing_mappings = MediaFileMappingModel.get_by_entity(entity_type, entity_id)
    for old in existing_mappings:
        try:
            MediaFileMappingModel.delete_by_local_path(old.local_path)
        except Exception as e:
            logger.warning(f"Failed to delete old mapping {old.local_path}: {e}")

    # 确定用户 ID
    try:
        uid = int(user_id) if user_id else None
    except (ValueError, TypeError):
        uid = None

    # MIME 类型
    ext = os.path.splitext(local_path)[1].lower()
    media_type = get_mime_type_from_extension(ext)

    # 文件大小（best-effort）
    file_size = None
    try:
        abs_path = os.path.join(get_project_root(), local_path)
        if os.path.exists(abs_path):
            file_size = os.path.getsize(abs_path)
    except Exception:
        pass

    # 创建 mapping
    mapping_id = MediaFileMappingModel.create(
        user_id=uid,
        local_path=local_path,
        cloud_path=None,
        policy_code=MediaFilePolicy.NEVER_EXPIRE,
        entity_type=entity_type,
        source_id=entity_id,
        media_type=media_type,
        original_url=image_url,
        file_size=file_size
    )

    # 触发异步 CDN 上传
    CDNUtil.trigger_cdn_upload(mapping_id, local_path)
    logger.info(f"Created CDN mapping {mapping_id} for entity ({entity_type}, {entity_id}): {local_path}")

    return mapping_id


def ensure_character_image_mapping(user_id, world_id, character_name: str, image_url: str) -> Optional[int]:
    """为角色主图创建 CDN mapping"""
    from model.character import CharacterModel
    from model.media_file_mapping import MediaFileEntity

    try:
        world_id_int = int(world_id)
    except (ValueError, TypeError):
        return None

    char = CharacterModel.get_by_name(world_id_int, character_name)
    if not char or not char.id:
        logger.debug(f"Character '{character_name}' not found in DB, skip CDN mapping")
        return None

    return ensure_entity_image_mapping(user_id, image_url, MediaFileEntity.CHARACTER, char.id)


def ensure_location_image_mapping(user_id, world_id, location_name: str, image_url: str) -> Optional[int]:
    """为场景主图创建 CDN mapping"""
    from model.location import LocationModel
    from model.media_file_mapping import MediaFileEntity

    try:
        world_id_int = int(world_id)
    except (ValueError, TypeError):
        return None

    loc = LocationModel.get_by_name(world_id_int, location_name)
    if not loc or not loc.id:
        logger.debug(f"Location '{location_name}' not found in DB, skip CDN mapping")
        return None

    return ensure_entity_image_mapping(user_id, image_url, MediaFileEntity.LOCATION, loc.id)


def ensure_prop_image_mapping(user_id, world_id, prop_name: str, image_url: str) -> Optional[int]:
    """为道具主图创建 CDN mapping"""
    from model.props import PropsModel
    from model.media_file_mapping import MediaFileEntity

    try:
        world_id_int = int(world_id)
    except (ValueError, TypeError):
        return None

    prop = PropsModel.get_by_name(world_id_int, prop_name)
    if not prop or not prop.id:
        logger.debug(f"Prop '{prop_name}' not found in DB, skip CDN mapping")
        return None

    return ensure_entity_image_mapping(user_id, image_url, MediaFileEntity.PROPS, prop.id)
