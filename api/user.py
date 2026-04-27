"""
用户偏好 API 路由（演示模式）

社区版/无 enterprise 模块时，此路由提供演示数据。
真实的供应商切换逻辑在 enterprise/routes/user.py 中。
"""
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Optional, Dict, List
import logging

from model.user_tokens import UserTokensModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])


class ImplementationPreferenceRequest(BaseModel):
    task_key: str
    implementation_name: str


@router.get("/implementation-preferences")
async def get_implementation_preferences(
    auth_token: str = Header(None, alias="Authorization")
):
    """
    获取用户所有实现方偏好（演示模式）

    仅返回固定的演示数据，不做任何数据库查询。
    """
    # 移除 "Bearer " 前缀
    if not auth_token:
        raise HTTPException(status_code=401, detail="需要登录")

    if auth_token.startswith("Bearer "):
        auth_token = auth_token[7:]

    # 验证 token 有效性（演示模式仍需登录）
    user_id = UserTokensModel.get_user_id_by_token(auth_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="无效或已过期的认证信息")

    # 返回固定的演示数据
    return {
        "code": 0,
        "data": {
            "preferences": {},
            "available_implementations": {
                "gemini-2.5-flash-image-preview": {
                    "name": "nano-banana",
                    "category": "image_edit",
                    "category_group": "image",
                    "implementations": [
                        {"name": "gemini_duomi_v1", "display_name": "yw", "computing_power": 95, "enabled": True, "stats": None},
                        {"name": "comfiy", "display_name": "ComfyUI", "computing_power": 92, "enabled": True, "stats": None}
                    ]
                },
                "gemini-3-pro-image-preview": {
                    "name": "nano-banana-Pro",
                    "category": "image_edit",
                    "category_group": "image",
                    "implementations": [
                        {"name": "gemini_duomi_v1", "display_name": "yw", "computing_power": 98, "enabled": True, "stats": None},
                        {"name": "comfiy", "display_name": "ComfyUI", "computing_power": 95, "enabled": True, "stats": None}
                    ]
                },
                "gemini-3.1-flash-image-preview": {
                    "name": "nano-banana-2",
                    "category": "image_edit",
                    "category_group": "image",
                    "implementations": [
                        {"name": "gemini_duomi_v1", "display_name": "yw", "computing_power": 96, "enabled": True, "stats": None},
                        {"name": "comfiy", "display_name": "ComfyUI", "computing_power": 93, "enabled": True, "stats": None}
                    ]
                }
            },
            "is_demo": True
        }
    }


@router.put("/implementation-preference")
async def set_implementation_preference(
    request: ImplementationPreferenceRequest,
    auth_token: str = Header(None, alias="Authorization")
):
    """
    设置单个任务类型的实现方偏好（演示模式）

    不实际保存到数据库。
    """
    # 移除 "Bearer " 前缀
    if not auth_token:
        raise HTTPException(status_code=401, detail="需要登录")

    if auth_token.startswith("Bearer "):
        auth_token = auth_token[7:]

    # 验证 token 有效性
    user_id = UserTokensModel.get_user_id_by_token(auth_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="无效或已过期的认证信息")

    logger.info(f"[Demo] User {user_id} attempted to set preference {request.task_key}={request.implementation_name}")

    return {
        "code": 0,
        "message": "演示模式：偏好未实际保存",
        "is_demo": True
    }


@router.delete("/implementation-preference")
async def delete_implementation_preference(
    task_key: str = Query(...),
    auth_token: str = Header(None, alias="Authorization")
):
    """
    清除单个任务类型的实现方偏好（演示模式）

    不实际操作数据库。
    """
    # 移除 "Bearer " 前缀
    if not auth_token:
        raise HTTPException(status_code=401, detail="需要登录")

    if auth_token.startswith("Bearer "):
        auth_token = auth_token[7:]

    # 验证 token 有效性
    user_id = UserTokensModel.get_user_id_by_token(auth_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="无效或已过期的认证信息")

    logger.info(f"[Demo] User {user_id} attempted to clear preference {task_key}")

    return {
        "code": 0,
        "message": "演示模式：偏好未实际清除",
        "is_demo": True
    }
