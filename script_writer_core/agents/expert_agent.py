import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_agent import BaseAgent, InsufficientComputingPowerError, check_computing_power_sync
from .ask_user_mixin import AskUserMixin
from .history_manager import ExpertHistoryManager
from .tool_definitions import ASK_USER_TOOL_DEFINITION
from llm.llm_client_factory import get_llm_client
from script_writer_core.file_manager import FileManager
from script_writer_core.skill_loader import SkillLoader
from model.model import ModelModel

logger = logging.getLogger(__name__)


class ExpertAgent(BaseAgent, AskUserMixin):
    """专家智能体 - 执行具体任务"""
    
    def __init__(
        self,
        skill_names: List[str],
        model: str,
        allowed_tools: List[str],
        context_from_pm: str,
        file_manager: FileManager,
        user_id: str,
        world_id: str,
        auth_token: str,
        tool_executor: Any,
        vendor_id: Optional[int] = None,
        model_id: Optional[int] = None,
        enable_thinking: bool = False,
        thinking_effort: str = "medium",
        task_manager: Optional[Any] = None,
        task_id: Optional[str] = None
    ):
        # 使用第一个技能名称作为主要标识
        primary_skill = skill_names[0] if skill_names else "unknown"
        agent_id = f"expert_{primary_skill}"
        
        
        # 初始化技能加载器（支持用户级自定义 skill）
        self.skill_loader = SkillLoader(user_id=int(user_id) if user_id else None)
        
        system_prompt = self._build_system_prompt(skill_names, context_from_pm)
        
        super().__init__(
            agent_id=agent_id,
            skill_names=skill_names,
            model=model,
            allowed_tools=allowed_tools,
            system_prompt=system_prompt
        )
        
        self.context = context_from_pm
        self.file_manager = file_manager
        self.user_id = user_id
        self.world_id = world_id
        self.auth_token = auth_token
        self.tool_executor = tool_executor
        self.vendor_id = vendor_id
        self.model_id = model_id
        self.enable_thinking = enable_thinking
        self.thinking_effort = thinking_effort
        self.task_manager = task_manager
        self.task_id = task_id
        
        self.history_manager = ExpertHistoryManager(
            file_manager=file_manager,
            user_id=user_id,
            world_id=world_id
        )
        
        self.tool_calls_made: List[Dict[str, Any]] = []
        self.outputs: List[Any] = []
        self.pending_project_ids: List[str] = []
    
    def _build_system_prompt(self, skill_names: List[str], context: str) -> str:
        """构建系统提示"""
        # 构建基础提示
        skills_str = "、".join(skill_names)
        base_prompt = f"""你是一个专业的专家智能体，具备以下技能：{skills_str}

**PM 提供的上下文**：
{context}

**注意事项**：
1. 严格按照技能指导和任务要求执行
2. 使用工具时确保参数正确
3. 遇到问题及时报告
4. 完成后提供详细的执行总结
"""
        
        # 加载所有技能内容
        skill_prompts = []
        for skill_name in skill_names:
            skill_prompt = self.skill_loader.get_skill_prompt(skill_name)
            if skill_prompt:
                logger.info(f"Successfully loaded {skill_name} skill content ({len(skill_prompt)} chars)")
                skill_prompts.append((skill_name, skill_prompt))
            else:
                logger.warning(f"Failed to load {skill_name} skill, skipping")
        
        # 如果成功加载技能内容，则附加到提示词中
        if skill_prompts:
            skills_section = "\n\n" + "="*60 + "\n**你的技能指导**\n" + "="*60 + "\n\n"
            for skill_name, skill_prompt in skill_prompts:
                skills_section += f"\n### 技能：{skill_name}\n\n{skill_prompt}\n\n{'-'*60}\n"
            return base_prompt + skills_section
        else:
            return base_prompt
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行具体任务"""
        session_id = task.get("session_id", "unknown")
        task_description = task.get("description", "")
        conversation_history = task.get("conversation_history", [])
        image_urls = task.get("image_urls", [])
        image_base64_list = task.get("image_base64_list", [])

        logger.info(f"{self.agent_id}: Starting task execution - {task_description}")

        try:
            # 如果提供了对话历史，先添加到历史记录中
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get("role")
                    content = msg.get("content")
                    if role and content:
                        self.add_to_history(role, content)

            # 如果有图片 URL，以多模态形式添加到对话历史（让专家 LLM 能"看到"图片）
            if image_urls:
                from utils.image_compressor import url_to_base64
                content_parts = []
                for i, img_url in enumerate(image_urls, 1):
                    # 优先使用前端预压缩的 base64，避免重复下载压缩
                    if i - 1 < len(image_base64_list) and image_base64_list[i - 1]:
                        base64_data = image_base64_list[i - 1]
                    else:
                        base64_data = url_to_base64(img_url, max_size_mb=0.1, max_pixels=250_000)
                    if base64_data:
                        content_parts.append({"type": "text", "text": f"[图片{i}]（URL: {img_url}）"})
                        content_parts.append({"type": "image_url", "image_url": {"url": base64_data}})
                    else:
                        content_parts.append({"type": "text", "text": f"[图片{i}]（URL: {img_url}，注意：该图片加载失败）"})
                content_parts.append({"type": "text", "text": task_description})
                self.add_to_history("user", content_parts)
            else:
                self.add_to_history("user", task_description)

            result = self._run_task_loop(task_description)
            
            self._save_session_history(
                session_id=session_id,
                task=task,
                result=result,
                status="success"
            )
            
            logger.info(f"{self.agent_id}: Task completed successfully")
            return {
                "success": True,
                "result": result,
                "project_ids": self.pending_project_ids
            }

        except InsufficientComputingPowerError:
            raise
        except Exception as e:
            logger.error(f"{self.agent_id}: Task failed - {e}", exc_info=True)
            
            self._save_session_history(
                session_id=session_id,
                task=task,
                result=None,
                status="failed",
                error=str(e)
            )
            
            return {
                "success": False,
                "error": str(e),
                "project_ids": self.pending_project_ids
            }
    
    def _run_task_loop(self, task_description: str, max_iterations: int = 10) -> str:
        """运行任务循环"""
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1

            # 检查算力是否充足
            check_computing_power_sync(self.auth_token, self.agent_id)

            try:
                # 从数据库获取模型的最大输出 token 数
                max_output_tokens = 65536  # 默认值
                try:
                    if self.model_id:
                        model = ModelModel.get_by_id(self.model_id)
                        if model and model.max_output_tokens:
                            max_output_tokens = model.max_output_tokens
                            logger.info(f"{self.agent_id}: Using model max_output_tokens: {max_output_tokens}")
                except Exception as e:
                    logger.warning(f"{self.agent_id}: Failed to get model info for max_output_tokens: {e}")

                # 使用 LLM 客户端工厂获取对应模型的客户端并调用 API
                # 传入 vendor_id 确保正确路由到目标供应商（如 zjt_api）
                history_len = len(self.conversation_history)  # 记录调用前的历史长度，用于异常时截断
                response = get_llm_client(self.model, vendor_id=self.vendor_id).call_api(
                    model=self.model,
                    messages=self._format_messages_for_api(),
                    tools=self._get_tool_definitions(),
                    temperature=1,
                    max_tokens=max_output_tokens,
                    auth_token=self.auth_token,
                    vendor_id=self.vendor_id,
                    model_id=self.model_id,
                    enable_thinking=self.enable_thinking,
                    thinking_effort=self.thinking_effort
                )
                
                message = response.choices[0].message
                
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    self._handle_tool_calls(message)
                else:
                    content = message.content or ""
                    reasoning_content = getattr(message, 'reasoning_content', None)
                    if reasoning_content:
                        history_content = {"text": content, "reasoning_content": reasoning_content}
                    else:
                        history_content = content
                    self.add_to_history("assistant", history_content)
                    logger.info(f"{self.agent_id}: Task completed with response")
                    return content

            except InsufficientComputingPowerError:
                # 截断历史，移除不完整的 tool_calls 消息（防止重试时 LLM 报错）
                logger.info(f"{self.agent_id}: 截断不完整的历史，从 {len(self.conversation_history)} 恢复到 {history_len}")
                self.conversation_history = self.conversation_history[:history_len]
                raise
            except Exception as e:
                logger.error(f"{self.agent_id}: Error in task loop - {e}", exc_info=True)
                raise
        
        logger.warning(f"{self.agent_id}: Max iterations reached")
        return "任务执行达到最大迭代次数，可能未完全完成"
    
    def _handle_tool_calls(self, message):
        """处理工具调用"""
        tool_calls = message.tool_calls
        
        # 构建历史记录条目，包含 tool_calls
        history_entry = {
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in tool_calls
            ]
        }
        
        # 提取 thought_signature（如果存在）
        # 根据 Gemini 文档：并行函数调用时，只有第一个函数调用包含 thought_signature
        if hasattr(message, 'thought_signature') and message.thought_signature:
            history_entry["thought_signature"] = message.thought_signature
        
        # 提取 reasoning_content（如果存在）
        # DeepSeek 等推理模型要求在后续请求中回传 reasoning_content
        if hasattr(message, 'reasoning_content') and message.reasoning_content:
            history_entry["reasoning_content"] = message.reasoning_content
        
        self.add_to_history("assistant", history_entry)

        deferred_user_inputs = []
        deferred_multimodal_content = []  # fetch_image_as_base64 成功时注入的多模态图片

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments) if isinstance(tool_call.function.arguments, str) else tool_call.function.arguments

            self.tool_calls_made.append({
                "tool": tool_name,
                "args": tool_args,
                "timestamp": datetime.now().isoformat()
            })

            result = self._execute_tool(tool_name, tool_args)

            # 收集图片/视频生成任务的 project_ids
            if tool_name in ("generate_text_to_image", "edit_image", "generate_text_to_video", "image_to_video"):
                if isinstance(result, dict) and result.get("project_ids"):
                    self.pending_project_ids.extend(result["project_ids"])

            # ask_user 工具：在 tool 回答之前，将问题写入历史（保证顺序正确）
            # 同时移除 _verification_meta，避免 LLM 看到后重复提问
            if tool_name == "ask_user" and isinstance(result, dict) and "_verification_meta" in result:
                meta = result.pop("_verification_meta")
                agent_name = self._get_agent_display_name()
                self.add_to_history("verification", {
                    "title": f"{agent_name} 向您提问",
                    "description": meta["question"],
                    "options": meta["options"]
                })
                user_input = result.get("user_input", "")
                if user_input:
                    deferred_user_inputs.append(user_input)

            self.outputs.append(result)

            # 将result转换为JSON字符串以便后续解析，而不是Python dict的字符串表示
            self.add_to_history("tool", {
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": json.dumps(result, ensure_ascii=False)
            })

            # fetch_image_as_base64 成功时，将 base64 数据存入延迟多模态列表
            if tool_name == "fetch_image_as_base64" and isinstance(result, dict) and result.get("success"):
                base64_data_url = result.get("base64_data_url")
                if base64_data_url:
                    deferred_multimodal_content.append({
                        "type": "text",
                        "text": f"[系统注入] 以下是工具成功获取的图片（URL: {tool_args.get('image_url', '')}）："
                    })
                    deferred_multimodal_content.append({
                        "type": "image_url",
                        "image_url": {"url": base64_data_url}
                    })

        # 将用户的回答作为 user 消息写入历史，放在所有 tool 消息之后
        # 避免在 assistant(tool_calls) 和 tool 之间插入 user 消息导致 API 报错
        for user_input in deferred_user_inputs:
            self.add_to_history("user", user_input)

        # 将 fetch_image_as_base64 获取的图片作为多模态 user 消息注入
        # API 工具结果消息只支持文本内容，多模态图片必须通过 user 消息注入
        if deferred_multimodal_content:
            self.add_to_history("user", deferred_multimodal_content)
    
    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具调用"""
        # 特殊处理 ask_user 工具（但仍需检查权限）
        if tool_name == "ask_user":
            if "ask_user" not in self.allowed_tools:
                error_msg = f"工具 {tool_name} 不在允许列表中"
                logger.warning(f"{self.agent_id}: {error_msg}")
                return {"error": error_msg}
            return self._handle_ask_user(tool_args)

        if tool_name not in self.allowed_tools:
            error_msg = f"工具 {tool_name} 不在允许列表中"
            logger.warning(f"{self.agent_id}: {error_msg}")
            return {"error": error_msg}
        
        try:
            result = self.tool_executor.execute_tool(
                tool_name=tool_name,
                tool_args=tool_args,
                user_id=self.user_id,
                world_id=self.world_id,
                auth_token=self.auth_token
            )
            logger.info(f"{self.agent_id}: Tool {tool_name} executed successfully")
            return result
        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            logger.error(f"{self.agent_id}: {error_msg}", exc_info=True)
            return {"error": error_msg}

    def _is_deepseek_model(self) -> bool:
        """判断当前模型是否为 DeepSeek 模型"""
        return 'deepseek' in (self.model or '').lower()

    def _format_messages_for_api(self) -> List[Dict[str, Any]]:
        """格式化消息用于 API 调用"""
        messages = [{"role": "system", "content": self.system_prompt}]

        # 判断是否为 DeepSeek 模型，如果是则需要为历史 assistant 消息补充 reasoning_content
        is_deepseek = self._is_deepseek_model()

        for msg in self.conversation_history:
            role = msg.get("role")
            content = msg.get("content")

            if role == "tool":
                messages.append({
                    "role": "tool",
                    "tool_call_id": content.get("tool_call_id"),
                    "name": content.get("name"),
                    "content": content.get("content")
                })
            elif role == "assistant" and isinstance(content, dict) and "tool_calls" in content:
                assistant_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": content["tool_calls"]
                }

                # 如果有 thought_signature，也要传递给 API（Gemini 3 要求）
                if "thought_signature" in content:
                    assistant_msg["thought_signature"] = content["thought_signature"]

                # 如果有 reasoning_content，也要传递给 API
                if "reasoning_content" in content:
                    assistant_msg["reasoning_content"] = content["reasoning_content"]
                elif is_deepseek:
                    # DeepSeek 要求回传 reasoning_content，历史记录中没有时补充空字符串
                    assistant_msg["reasoning_content"] = ""

                messages.append(assistant_msg)
            elif role == "assistant" and isinstance(content, dict) and "reasoning_content" in content:
                # 纯文本 assistant 消息但包含 reasoning_content（DeepSeek 推理模型要求回传）
                assistant_msg = {
                    "role": "assistant",
                    "content": content.get("text", ""),
                    "reasoning_content": content["reasoning_content"]
                }
                messages.append(assistant_msg)
            elif role == "assistant" and is_deepseek:
                # DeepSeek 模型下，普通 assistant 消息也需要补充 reasoning_content
                assistant_msg = {
                    "role": "assistant",
                    "content": content if isinstance(content, str) else str(content),
                    "reasoning_content": ""
                }
                messages.append(assistant_msg)
            elif role == "user" and isinstance(content, list):
                # 多模态消息（包含图片）
                messages.append({
                    "role": "user",
                    "content": content
                })
            elif role == "verification":
                # 跳过 verification 消息（仅供前端展示，不发给 LLM）
                continue
            else:
                messages.append({
                    "role": role,
                    "content": content if isinstance(content, str) else str(content)
                })

        return messages

    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取工具定义"""
        tool_defs = self.tool_executor.get_tool_definitions(self.allowed_tools)

        # 如果配置了 task_manager，则添加 ask_user 工具定义
        if self.task_manager and self.task_id:
            tool_defs.append(ASK_USER_TOOL_DEFINITION)

        return tool_defs
    
    def _save_session_history(
        self,
        session_id: str,
        task: Dict[str, Any],
        result: Optional[str],
        status: str,
        error: Optional[str] = None
    ):
        """保存会话历史"""
        try:
            execution = {
                "status": status,
                "tool_calls": self.tool_calls_made,
                "outputs": self.outputs,
                "result": result,
                "error": error
            }
            
            self.history_manager.save_expert_session(
                skill_name=self.skill_name,
                session_id=session_id,
                task=task,
                execution=execution,
                conversation_history=self.conversation_history,
                summary=None
            )
        except Exception as e:
            logger.error(f"{self.agent_id}: Failed to save session history - {e}", exc_info=True)
