"""
NotificationService - 从远程服务器拉取通知，存储到本地数据库
类似 WordPress 检查 wp.org 更新的机制
"""
import asyncio
import hashlib
import json
import logging
import platform
import socket
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

import aiohttp

from config.constant import NotificationConstants
from config.version import get_app_version
from config.config_util import get_current_env

logger = logging.getLogger(__name__)


class NotificationService:
    """从远程服务器拉取通知，存入数据库"""

    _client_id: Optional[str] = None
    _local_version: Optional[str] = None
    _version_status: Dict[str, Any] = {}
    _required_binaries: List[Dict[str, Any]] = []
    _task: Optional[asyncio.Task] = None
    _check_interval: int = NotificationConstants.CHECK_INTERVAL
    _initialized: bool = False

    @classmethod
    async def initialize(cls, project_dir: Path = None):
        """服务器启动时调用"""
        if cls._initialized:
            return

        cls._client_id = cls._generate_client_id(project_dir)
        cls._local_version = get_app_version()
        cls._initialized = True

        logger.info(
            f"[Notification] Initialized: client_id={cls._client_id}, "
            f"version={cls._local_version}, env={get_current_env()}"
        )

        # 首次检查（延迟 5 秒，等服务器完全启动）
        await asyncio.sleep(5)
        await cls._check_remote()

        # 启动后台定时任务
        cls._task = asyncio.create_task(cls._periodic_check())

    @classmethod
    def _generate_client_id(cls, project_dir: Path = None) -> str:
        """生成客户端唯一标识（单向hash，不可逆）

        组合: 主机名 + 主机IP + 安装路径
        效果:
        - 不同服务器 → 不同 ID
        - 同一服务器不同目录 → 不同 ID
        - 不可反推出原始信息
        """
        try:
            hostname = platform.node()
        except Exception:
            hostname = "unknown"

        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "0.0.0.0"

        if project_dir is None:
            project_dir = Path(__file__).parent.parent
        install_path = str(project_dir.resolve())

        raw = f"{hostname}|{ip}|{install_path}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @classmethod
    async def _periodic_check(cls):
        """后台定时检查任务"""
        while True:
            try:
                await asyncio.sleep(cls._check_interval)
                await cls._check_remote()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[Notification] Periodic check failed: {e}")

    @classmethod
    async def _check_remote(cls):
        """调用远程 API，获取通知并存入 DB"""
        api_base = NotificationConstants.REMOTE_API_BASE
        url = f"{api_base}/notifications/check"

        headers = {
            "X-Client-Version": cls._local_version or "0.0.0",
            "X-Client-Env": get_current_env(),
            "X-Client-ID": cls._client_id or "unknown",
            "Accept": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.warning(f"[Notification] Remote API returned {resp.status}")
                        return

                    data = await resp.json()
                    if data.get("code") != 0:
                        logger.warning(f"[Notification] Remote API error: {data}")
                        return

                    result = data.get("data", {})
                    await asyncio.to_thread(cls._process_response, result)

        except aiohttp.ClientError as e:
            logger.debug(f"[Notification] Remote API unreachable: {e}")
        except Exception as e:
            logger.warning(f"[Notification] Check failed: {e}")

    @classmethod
    def _process_response(cls, data: Dict[str, Any]):
        """处理远程 API 响应"""
        # 1. 更新版本状态（内存缓存）
        version_update = data.get("version_update")
        if version_update:
            cls._version_status = {
                "has_update": version_update.get("has_update", False),
                "current_version": cls._local_version,
                "latest_version": version_update.get("latest_version", ""),
                "release_notes": version_update.get("release_notes", ""),
                "changelog_url": version_update.get("changelog_url"),
                "required_binaries": version_update.get("required_binaries", []),
            }
            cls._required_binaries = version_update.get("required_binaries", [])
            if cls._version_status["has_update"]:
                logger.info(
                    f"[Notification] New version available: "
                    f"{cls._local_version} -> {cls._version_status['latest_version']}"
                )

        # 2. 更新检查间隔
        check_interval = data.get("check_interval")
        if check_interval and isinstance(check_interval, int) and check_interval > 0:
            cls._check_interval = check_interval

        # 3. 存储公告通知到数据库
        announcements = data.get("announcements", [])
        if announcements:
            cls._save_announcements(announcements)

    @classmethod
    def _save_announcements(cls, announcements: List[Dict[str, Any]]):
        """将公告存入数据库（按 remote_id 去重）"""
        from model.notifications import NotificationsModel

        saved_count = 0
        for ann in announcements:
            remote_id = ann.get("id")
            if not remote_id:
                continue

            # 构建 extra_data
            extra_data = {}
            if ann.get("link"):
                extra_data["link"] = ann["link"]
            if ann.get("link_text"):
                extra_data["link_text"] = ann["link_text"]

            try:
                record_id = NotificationsModel.create(
                    remote_id=remote_id,
                    notification_type=ann.get("type", "announcement"),
                    title=ann.get("title", ""),
                    content=ann.get("content", ""),
                    level=ann.get("level", "info"),
                    extra_data=extra_data if extra_data else None,
                    start_time=ann.get("start_time"),
                    end_time=ann.get("end_time"),
                )
                if record_id > 0:
                    saved_count += 1
            except Exception as e:
                logger.warning(f"[Notification] Failed to save {remote_id}: {e}")

        if saved_count > 0:
            logger.info(f"[Notification] Saved {saved_count} new announcements")

    @classmethod
    def get_version_status(cls) -> Dict[str, Any]:
        """返回版本升级状态"""
        return cls._version_status.copy()

    @classmethod
    def get_missing_binaries(cls) -> List[Dict[str, Any]]:
        """检查本地缺失的二进制依赖

        从 config/required_binaries.yml 读取配置，检查本地文件是否存在。
        返回缺失的二进制列表，每项包含: name, description, download_url, check_path
        """
        project_dir = Path(__file__).parent.parent
        config_file = project_dir / "config" / "required_binaries.yml"

        if not config_file.exists():
            return []

        try:
            import yaml
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"[Notification] Failed to read required_binaries.yml: {e}")
            return []

        binaries_config = config.get("binaries")
        if not binaries_config:
            return []

        # 平台映射
        platform_map = {
            "win32": "windows",
            "linux": "linux",
            "darwin": "macos",
        }
        current_platform = platform_map.get(sys.platform, "linux")

        # 获取当前版本
        current_version = cls._local_version or "0.0.0"

        missing = []
        for name, binary_config in binaries_config.items():
            # 检查版本要求
            required_since = binary_config.get("required_since", "0.0.0")
            if cls._compare_version(current_version, required_since) < 0:
                continue

            # 检查文件是否存在
            check_paths = binary_config.get("check_paths", {})
            check_path = check_paths.get(current_platform)

            if not check_path:
                continue

            full_path = project_dir / check_path
            if not full_path.exists():
                missing.append({
                    "name": name,
                    "description": binary_config.get("description", ""),
                    "download_url": binary_config.get("download_url", ""),
                    "check_path": check_path,
                })

        return missing

    @staticmethod
    def _compare_version(v1: str, v2: str) -> int:
        """比较两个版本号

        返回: 1 if v1 > v2, -1 if v1 < v2, 0 if v1 == v2
        """
        def parse(v: str) -> List[int]:
            v = v.lstrip("vV")
            num_part = v.split("-")[0]
            result = []
            for p in num_part.split("."):
                try:
                    result.append(int(p))
                except ValueError:
                    result.append(0)
            return result

        p1, p2 = parse(v1), parse(v2)
        for a, b in zip(p1, p2):
            if a != b:
                return 1 if a > b else -1
        return len(p1) - len(p2)

    @classmethod
    def get_unread_notifications(cls) -> List[Dict[str, Any]]:
        """从 DB 查询未读通知"""
        from model.notifications import NotificationsModel
        try:
            notifications = NotificationsModel.get_unread()
            return [n.to_dict() for n in notifications]
        except Exception as e:
            logger.error(f"[Notification] Failed to get unread: {e}")
            return []

    @classmethod
    def get_unread_count(cls) -> int:
        """获取未读通知数量"""
        from model.notifications import NotificationsModel
        try:
            return NotificationsModel.get_unread_count()
        except Exception as e:
            logger.error(f"[Notification] Failed to get count: {e}")
            return 0

    @classmethod
    async def shutdown(cls):
        """停止后台任务"""
        if cls._task and not cls._task.done():
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
        cls._initialized = False
        logger.info("[Notification] Service shut down")
