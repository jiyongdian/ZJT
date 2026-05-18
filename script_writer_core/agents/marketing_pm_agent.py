"""
营销项目经理智能体 - 专门负责营销创作流程的协调
基于 PMAgent 基类，移除了剧本智能体特有的逻辑
"""

import logging
from typing import Dict, Any, List, Optional

from .pm_agent import PMAgent
from .task_manager import TaskManager
from script_writer_core.file_manager import FileManager
from script_writer_core.skill_loader import SkillLoader
from agents.skill_loader import SopLoader

logger = logging.getLogger(__name__)


class MarketingPMAgent(PMAgent):
    """
    营销项目经理智能体 - 负责统筹营销创作流程

    与剧本智能体的核心区别：
    1. 不加载环境上下文（世界设定、角色、剧本等）
    2. 使用营销专用的提示词（来自 agents/skills/marketing-pm/SKILL.md）
    3. 支持 load_sop 工具动态加载 SOP 流程
    4. 不包含剧本相关的文件操作工具
    """

    def __init__(
        self,
        model: str,
        allowed_tools: List[str],
        task_manager: TaskManager,
        file_manager: FileManager,
        tool_executor: Any,
        agents_config: Dict[str, Any],
        user_id: str,
        world_id: str,
        auth_token: str,
        base_prompt: str,
        sop_loader: SopLoader,
        skill_loader: Optional[SkillLoader] = None,
        max_consecutive_failures: int = 3,
        max_total_failures: int = 7,
        context_window: Optional[int] = None,
    ):
        """
        初始化营销 PM Agent

        Args:
            model: 使用的 LLM 模型
            allowed_tools: 允许使用的工具列表
            task_manager: 任务管理器
            file_manager: 文件管理器
            tool_executor: 工具执行器
            agents_config: 智能体配置
            user_id: 用户ID
            world_id: 世界ID
            auth_token: 认证令牌
            base_prompt: 营销智能体的基础提示词（必须提供）
            sop_loader: SOP 加载器（必须提供）
            skill_loader: 技能加载器（可选）
            max_consecutive_failures: 最大连续失败次数
            max_total_failures: 最大累计失败次数
            context_window: 上下文窗口大小
        """
        if not base_prompt:
            raise ValueError("MarketingPMAgent 必须提供 base_prompt")
        if not sop_loader:
            raise ValueError("MarketingPMAgent 必须提供 sop_loader")

        # 调用父类构造函数，跳过环境上下文加载
        super().__init__(
            model=model,
            allowed_tools=allowed_tools,
            task_manager=task_manager,
            file_manager=file_manager,
            tool_executor=tool_executor,
            agents_config=agents_config,
            user_id=user_id,
            world_id=world_id,
            auth_token=auth_token,
            max_consecutive_failures=max_consecutive_failures,
            max_total_failures=max_total_failures,
            context_window=context_window,
            base_prompt=base_prompt,
            skill_loader=skill_loader,
            sop_loader=sop_loader,
            skill_names=[],  # 营销智能体不从 SkillLoader 加载技能
            skip_env_context=True  # 营销智能体不加载环境上下文
        )

        self.agent_id = "marketing_pm_agent"
        logger.info(f"{self.agent_id}: MarketingPMAgent 初始化完成")

    def _build_system_prompt(self, skill_names: List[str]) -> str:
        """
        构建营销智能体的系统提示词

        营销智能体必须提供 base_prompt，直接使用它作为基础提示词
        不使用剧本架构师的默认提示词
        """
        if not self._custom_base_prompt:
            raise ValueError("MarketingPMAgent 必须提供 base_prompt")

        # 营销智能体直接使用 base_prompt，不加载默认的剧本架构师提示词
        base_prompt = self._custom_base_prompt

        # 营销智能体通常 skill_names=[]，所以不会追加额外技能内容
        # 但保留这个逻辑以支持未来可能的扩展
        skill_prompts = []
        for skill_name in skill_names:
            skill_prompt = self.skill_loader.get_skill_prompt(skill_name)
            if skill_prompt:
                logger.info(f"Successfully loaded {skill_name} skill content ({len(skill_prompt)} chars)")
                skill_prompts.append((skill_name, skill_prompt))
            else:
                logger.warning(f"Failed to load {skill_name} skill, skipping")

        if skill_prompts:
            skills_section = "\n\n" + "="*60 + "\n**你的核心技能**\n" + "="*60 + "\n\n"
            for skill_name, skill_prompt in skill_prompts:
                skills_section += f"\n### 技能：{skill_name}\n\n{skill_prompt}\n\n{'-'*60}\n"
            return base_prompt + skills_section
        else:
            return base_prompt

    def _build_context_for_expert(self, skill_name: str, user_id: str = "0", world_id: str = "0") -> str:
        """
        为专家构建上下文

        营销智能体的专家不需要世界设定等环境上下文
        只提供基本的任务上下文
        """
        context_parts = [
            f"**技能**: {skill_name}"
        ]

        # 检查专家配置中的 summary_only 设置
        expert_config = self.agents_config.get("expert_agents", {}).get(skill_name, {})
        summary_only = expert_config.get("summary_only", False)

        if summary_only:
            # 摘要模式：只提供基本信息
            context_parts.append("**上下文模式**: 摘要模式，请根据任务描述执行")
        else:
            # 完整模式：提供 PM 的系统提示词作为上下文
            # 营销智能体不需要世界设定等环境内容
            context_parts.append("**上下文模式**: 完整模式")

        return "\n".join(context_parts)
