from unittest.mock import MagicMock, patch

from script_writer_core.agents.pm_agent import PMAgent
from script_writer_core.agents.task_manager import AgentTask


def _create_pm_agent(task_manager):
    file_manager = MagicMock()
    file_manager.get_context_for_ai.return_value = ""
    return PMAgent(
        model="test-model",
        allowed_tools=["call_agent"],
        task_manager=task_manager,
        file_manager=file_manager,
        tool_executor=MagicMock(),
        agents_config={
            "pm_agent": {"skills": []},
            "expert_agents": {
                "image-understanding": {
                    "skills": [],
                    "allowed_tools": [],
                    "model": "test-model",
                }
            },
        },
        user_id="1",
        world_id="1",
        auth_token="token",
        base_prompt="test prompt",
        skip_env_context=True,
    )


def test_handle_agent_call_pushes_expert_text_once_for_frontend_visibility():
    task_manager = MagicMock()
    agent = _create_pm_agent(task_manager)
    task = AgentTask(
        task_id="task-1",
        session_id="session-1",
        user_message="describe image",
        user_id="1",
        world_id="1",
        auth_token="token",
        vendor_id=1,
        model_id=1,
    )

    with patch("script_writer_core.agents.pm_agent.ExpertAgent") as expert_cls:
        expert = expert_cls.return_value
        expert.execute_task.return_value = {
            "success": True,
            "result": "### 图片内容分析\n只有一条分析结果",
            "project_ids": [],
        }

        result = agent._handle_agent_call(
            {
                "AgentName": "image-understanding",
                "task_description": "analyze",
            },
            task,
            {},
        )

    assert result["success"] is True
    pushed_types = [call.args[1] for call in task_manager.push_message.call_args_list]
    assert "progress" in pushed_types
    assert pushed_types.count("message") == 1
    message_calls = [call for call in task_manager.push_message.call_args_list if call.args[1] == "message"]
    assert message_calls[0].args[2]["content"].startswith("### 图片内容分析")
    assert agent.completed_tasks[0]["result"]["result"].startswith("### 图片内容分析")
