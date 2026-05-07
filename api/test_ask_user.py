"""
测试 ExpertAgent ask_user 功能的端点
- 端点独立，不影响生产代码
- 创建真实 ExpertAgent + 真实 LLM
- 验证完整的 ask_user 链路
"""

import os
import logging
import threading
import json
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Query as QueryParam
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 创建路由器（独立路由，不影响生产）
router = APIRouter(prefix="/api/test", tags=["test_ask_user"])


class TestAskUserRequest(BaseModel):
    """测试 ask_user 请求"""
    session_id: str
    user_id: str
    world_id: str
    auth_token: str = ""
    model: str  # 从前端获取，不再写死
    vendor_id: int  # 从前端获取
    model_id: int  # 从前端获取


@router.post("/ask-user")
async def test_ask_user(request: TestAskUserRequest):
    """
    测试 ExpertAgent ask_user 功能

    工作流程：
    1. 创建测试任务
    2. 启动后台线程执行 ExpertAgent
    3. LLM 第一轮调用 ask_user 工具向用户提问
    4. 用户在浏览器回答
    5. ExpertAgent 从 DB 轮询到回答
    6. LLM 第二轮基于用户回答生成内容
    7. 结果推送到 SSE，用户可见

    参数说明：
    - model: 模型标识（如 "gemini-2.0-flash-exp", "qwen-plus", 或 "ollama:llama2"）
    - vendor_id: 供应商 ID（从前端模型选择器的 dataset.vendorId 获取）
    - model_id: 模型在数据库中的 ID（从前端模型选择器的 dataset.modelId 获取）

    返回：
    {
        "success": true,
        "task_id": "xxx",
        "sse_url": "/api/task/xxx/stream",
        "message": "测试任务已创建，请在浏览器中回答 LLM 的问题"
    }
    """
    # 参数验证
    if not request.model or not request.model.strip():
        logger.error("Test request failed: model parameter is empty")
        return {
            "success": False,
            "error": "模型参数不能为空，请从下拉菜单选择一个模型"
        }

    if not request.user_id or not request.world_id:
        logger.error("Test request failed: user_id or world_id is empty")
        return {
            "success": False,
            "error": "缺少必需的参数（user_id 或 world_id）"
        }

    try:
        # 导入全局实例（在这里导入以避免循环导入）
        from api.script_writer import task_manager, file_manager, tool_executor
        from script_writer_core.agents.expert_agent import ExpertAgent
        from script_writer_core.agents.task_manager import TaskStatus

        logger.info(f"Test ask_user request: session_id={request.session_id}, user_id={request.user_id}, model={request.model}, vendor_id={request.vendor_id}, model_id={request.model_id}")

        # 1. 创建测试任务
        task_id = task_manager.create_task(
            session_id=request.session_id,
            user_message="(测试任务：使用 ask_user 工具提问，然后基于用户回答生成内容)",
            user_id=request.user_id,
            world_id=request.world_id,
            auth_token=request.auth_token,
            vendor_id=request.vendor_id,
            model_id=request.model_id,
            enable_thinking=False,
            thinking_effort="medium"
        )

        logger.info(f"Test task created: task_id={task_id}")

        # 2. 定义后台执行函数
        def run_test_task():
            """后台线程：执行 ExpertAgent 并调用 ask_user"""
            try:
                # 推送开始状态
                task_manager.push_message(task_id, 'status', {
                    'status': 'running',
                    'message': '测试任务开始执行，LLM 即将向您提问'
                })

                # 更新任务状态为 running
                try:
                    from model.agent_tasks import AgentTasksModel
                    AgentTasksModel.update_status(
                        task_id=task_id,
                        status='running',
                        started_at=datetime.now()
                    )
                except Exception as e:
                    logger.error(f"Failed to update task status: {e}")

                # 3. 创建 ExpertAgent 实例
                # 关键：仅允许 ask_user 工具，使 LLM 必须先提问
                expert = ExpertAgent(
                    skill_names=["story-writer"],  # 使用已有的技能
                    model=request.model,
                    allowed_tools=["ask_user"],  # 仅允许 ask_user
                    context_from_pm=(
                        "你是一个测试智能体。\n\n"
                        "你的任务很简单：\n"
                        "1. 首先，使用 ask_user 工具向用户提一个问题。\n"
                        "   - 问题示例：'你喜欢什么类型的故事？'\n"
                        "   - 重要：提供多个选项让用户快速选择，格式：options=['科幻', '悬疑', '爱情', '冒险', '奇幻']\n"
                        "   - 前端会显示这些选项作为按钮，用户也可以点击'其他'输入自定义答案\n\n"
                        "2. 等待用户的回答（可以是选项之一，或用户自定义输入）\n\n"
                        "3. 基于用户的回答，生成一个包含用户回答内容的短故事开头（3-5句）\n\n"
                        "例如，如果用户选择'科幻'或输入'科幻'，你可以回复：\n"
                        "'既然你喜欢科幻故事，我为你创作了这个开头：在未来的2157年，一艘神秘的飞船出现在火星轨道...'\n\n"
                        "如果用户选择'其他'并输入了自定义答案，也要基于这个答案生成故事开头。"
                    ),
                    file_manager=file_manager,
                    user_id=request.user_id,
                    world_id=request.world_id,
                    auth_token=request.auth_token,
                    tool_executor=tool_executor,
                    vendor_id=request.vendor_id,
                    model_id=request.model_id,
                    enable_thinking=False,
                    thinking_effort="medium",
                    task_manager=task_manager,  # 传入 task_manager 以支持 ask_user
                    task_id=task_id  # 传入 task_id 以支持 ask_user
                )

                logger.info(f"ExpertAgent created for task {task_id}")

                # 4. 执行任务
                # execute_task 会调用 _run_task_loop，LLM 将循环执行：
                # - 第 1 轮：看到 system prompt，调用 ask_user 工具向用户提问
                # - ExpertAgent._handle_ask_user() 会阻塞等待用户回答
                # - SSE 推送 human_verification_required 到前端
                # - 用户在浏览器中回答问题
                # - POST /api/verification/{id} 提交回答
                # - 轮询检测到回答，返回给 LLM
                # - 第 2 轮：LLM 看到用户回答，生成包含回答的回复
                # - 返回最终文本

                task_dict = {
                    "session_id": request.session_id,
                    "description": "(测试任务：使用 ask_user 工具提问，然后基于用户回答生成内容)",
                    "conversation_history": []
                }

                result = expert.execute_task(task_dict)

                logger.info(f"ExpertAgent task completed: {result}")

                # 5. 推送最终结果到 SSE
                if result.get("success"):
                    # 推送 LLM 最终回复
                    final_message = result.get("result", "")
                    task_manager.push_message(task_id, 'message', {
                        'content': final_message,
                        'timestamp': datetime.now().isoformat(),
                        'role': 'assistant'
                    })

                    logger.info(f"Test task {task_id} completed successfully")
                    logger.info(f"LLM final response: {final_message}")
                else:
                    # 推送错误消息
                    error_msg = result.get("error", "Unknown error")
                    task_manager.push_message(task_id, 'error', {
                        'error': error_msg,
                        'timestamp': datetime.now().isoformat()
                    })

                    logger.error(f"Test task {task_id} failed: {error_msg}")

                # 6. 推送完成消息
                task_manager.push_message(task_id, 'done', {
                    'status': 'completed',
                    'timestamp': datetime.now().isoformat()
                })

                # 更新数据库状态
                try:
                    from model.agent_tasks import AgentTasksModel
                    AgentTasksModel.update_status(
                        task_id=task_id,
                        status='completed',
                        completed_at=datetime.now(),
                        result=result.get("result", "")
                    )
                except Exception as e:
                    logger.error(f"Failed to update task completed status: {e}")

            except Exception as e:
                logger.error(f"Test task {task_id} failed with exception: {e}", exc_info=True)

                # 推送错误消息
                task_manager.push_message(task_id, 'error', {
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })

                # 推送完成消息
                task_manager.push_message(task_id, 'done', {
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })

                # 更新数据库状态
                try:
                    from model.agent_tasks import AgentTasksModel
                    AgentTasksModel.update_status(
                        task_id=task_id,
                        status='failed',
                        completed_at=datetime.now(),
                        error=str(e)
                    )
                except Exception as db_e:
                    logger.error(f"Failed to update task failed status: {db_e}")

        # 3. 启动后台线程
        thread = threading.Thread(target=run_test_task, daemon=True)
        thread.start()

        logger.info(f"Test task thread started for task_id={task_id}")

        # 4. 立即返回 task_id 和 SSE URL
        return {
            "success": True,
            "task_id": task_id,
            "sse_url": f"/api/task/{task_id}/stream",
            "message": "✅ 测试任务已创建。请在浏览器控制台中监听 SSE 事件，或在前端看到 LLM 提问时回答。",
            "instructions": {
                "step1": "打开浏览器控制台（F12）",
                "step2": "执行：const es = new EventSource('/api/task/{}/stream'); es.onmessage = e => console.log(JSON.parse(e.data));".format(task_id),
                "step3": "等待 LLM 问题（human_verification_required 消息）",
                "step4": "在前端回答或通过 POST /api/verification/{verification_id} 提交回答",
                "step5": "观察 LLM 最终回复（message 消息），验证 ask_user 链路"
            }
        }

    except Exception as e:
        logger.error(f"Failed to create test task: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "测试任务创建失败，请检查日志"
        }
