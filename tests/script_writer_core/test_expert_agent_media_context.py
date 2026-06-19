from unittest.mock import MagicMock, patch

from script_writer_core.agents.expert_agent import ExpertAgent


def test_expert_agent_injects_audio_and_video_urls_from_task_dict():
    agent = ExpertAgent(
        skill_names=[],
        model="test-model",
        allowed_tools=[],
        context_from_pm="",
        file_manager=MagicMock(),
        user_id="1",
        world_id="1",
        auth_token="token",
        tool_executor=MagicMock(),
        task_manager=MagicMock(),
        task_id="task-1",
    )

    with patch.object(agent, "_run_task_loop", return_value="done"):
        result = agent.execute_task({
            "session_id": "task-1",
            "description": "do task",
            "image_urls": ["http://localhost/image.png"],
            "audio_urls": ["http://localhost/audio.mp3"],
            "video_urls": ["http://localhost/video.mp4"],
        })

    assert result["success"] is True
    user_messages = [m for m in agent.conversation_history if m.get("role") == "user"]
    assert user_messages
    content = user_messages[-1]["content"]
    assert "[图片1]（URL: http://localhost/image.png）" in content
    assert "[音频1]（URL: http://localhost/audio.mp3）" in content
    assert "[视频1]（URL: http://localhost/video.mp4）" in content
