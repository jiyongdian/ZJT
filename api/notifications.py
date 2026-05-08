"""
通知系统 API 路由

提供客户端轮询接口和管理员通知管理接口。
"""
import asyncio
from fastapi import APIRouter, Header, Query, Path
from typing import Optional
import logging

from model.users import UsersModel
from model.user_tokens import UserTokensModel
from model.notifications import NotificationsModel
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ============ 认证辅助 ============

def _get_current_user(auth_token: str = None) -> Optional[int]:
    """从 token 获取当前用户 ID，失败返回 None"""
    if not auth_token:
        return None
    if auth_token.startswith("Bearer "):
        auth_token = auth_token[7:]
    try:
        return UserTokensModel.get_user_id_by_token(auth_token)
    except Exception:
        return None


def _require_admin(auth_token: str = None):
    """验证管理员权限，失败抛出异常"""
    user_id = _get_current_user(auth_token)
    if not user_id:
        raise ValueError("未登录")
    user = UsersModel.get_by_id(user_id)
    if not user or user.role != 'admin':
        raise ValueError("权限不足")
    return user


# ============ 客户端接口 ============

@router.get("/poll")
async def poll_notifications():
    """
    客户端轮询接口（每 30 秒调用一次）

    返回版本升级状态 + 未读通知列表 + 未读数量
    无需认证，全局公告。
    """
    try:
        # 版本升级状态（内存缓存，无需认证）
        version_status = NotificationService.get_version_status()

        # 未读通知（无需认证，全局公告）
        notifications = await asyncio.to_thread(NotificationService.get_unread_notifications)
        unread_count = await asyncio.to_thread(NotificationService.get_unread_count)

        return {
            "code": 0,
            "data": {
                "version_update": version_status if version_status.get("has_update") else None,
                "notifications": notifications,
                "unread_count": unread_count,
            }
        }
    except Exception as e:
        logger.error(f"Poll failed: {e}")
        return {"code": 1, "message": str(e)}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int = Path(..., description="通知ID"),
):
    """标记单条通知为已读（全局公告，无需认证）"""
    try:
        affected = await asyncio.to_thread(NotificationsModel.mark_read, notification_id)
        return {"code": 0, "data": {"updated": affected > 0}}
    except Exception as e:
        logger.error(f"Mark read failed: {e}")
        return {"code": 1, "message": str(e)}


@router.post("/read-all")
async def mark_all_notifications_read():
    """标记所有通知为已读（全局公告，无需认证）"""
    try:
        affected = await asyncio.to_thread(NotificationsModel.mark_all_read)
        return {"code": 0, "data": {"updated_count": affected}}
    except Exception as e:
        logger.error(f"Mark all read failed: {e}")
        return {"code": 1, "message": str(e)}


# ============ 管理员接口 ============

@router.get("/admin/list")
async def admin_list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    authorization: str = Header(None),
):
    """管理员查看通知列表（分页）"""
    try:
        await asyncio.to_thread(_require_admin, authorization)
        result = await asyncio.to_thread(
            NotificationsModel.list_all, page=page, page_size=page_size
        )
        return {
            "code": 0,
            "data": {
                "items": [n.to_dict() for n in result["items"]],
                "total": result["total"],
                "page": result["page"],
                "page_size": result["page_size"],
            }
        }
    except ValueError as e:
        return {"code": 1, "message": str(e)}
    except Exception as e:
        logger.error(f"Admin list failed: {e}")
        return {"code": 1, "message": str(e)}


@router.delete("/admin/{notification_id}")
async def admin_delete_notification(
    notification_id: int = Path(..., description="通知ID"),
    authorization: str = Header(None),
):
    """管理员删除通知"""
    try:
        await asyncio.to_thread(_require_admin, authorization)
        affected = await asyncio.to_thread(NotificationsModel.delete_by_id, notification_id)
        return {"code": 0, "data": {"deleted": affected > 0}}
    except ValueError as e:
        return {"code": 1, "message": str(e)}
    except Exception as e:
        logger.error(f"Admin delete failed: {e}")
        return {"code": 1, "message": str(e)}
