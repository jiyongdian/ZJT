from unittest.mock import patch

from script_writer_core.agents.tool_executor import ToolExecutor
from script_writer_core.mcp_tool import MCP_TOOLS


def test_digital_human_expert_tools_are_visible_to_llm():
    executor = ToolExecutor(file_manager=None)

    definitions = executor.get_tool_definitions([
        "generate_digital_human",
        "generate_reference_audio",
        "check_reference_audio_status",
        "get_user_computing_power",
    ])
    names = {tool["function"]["name"] for tool in definitions}

    assert "generate_digital_human" in names
    assert "generate_reference_audio" in names
    assert "check_reference_audio_status" in names
    assert "get_user_computing_power" in names


def test_digital_human_config_does_not_allow_character_audio_tool():
    import json
    from pathlib import Path

    config = json.loads(Path("script_writer_core/config/agents_config.json").read_text(encoding="utf-8"))
    allowed_tools = config["expert_agents"]["digital-human-creator"]["allowed_tools"]

    assert "generate_character_reference_audio" not in allowed_tools
    assert "generate_reference_audio" in allowed_tools
    assert "check_reference_audio_status" in allowed_tools


def test_generate_reference_audio_schedules_audio_without_character_lookup():
    from script_writer_core import mcp_tool

    with patch(
        "config.config_util.get_dynamic_config_value",
        return_value="runninghub-key",
    ), patch(
        "model.AsyncTasksModel.create_and_schedule",
        return_value=123,
    ) as create_and_schedule, patch.object(
        mcp_tool, "get_file_manager"
    ) as get_file_manager:
        result = mcp_tool.generate_reference_audio(
            user_id="7",
            world_id="marketing",
            auth_token="token",
            text="hello world",
            style_prompt="natural calm voice",
        )

    assert result["success"] is True
    assert result["task_id"] == 123
    get_file_manager.assert_not_called()
    params = create_and_schedule.call_args.kwargs["params"]
    assert params["text"] == "hello world"
    assert params["style_prompt"] == "natural calm voice"
    assert "character_name" not in params


def test_generate_reference_audio_is_registered_in_mcp_tools():
    names = {tool["name"] for tool in MCP_TOOLS}

    assert "generate_reference_audio" in names
    assert "generate_digital_human" in names
