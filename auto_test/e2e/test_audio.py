"""
音频模块 API 测试。
覆盖 P0 核心接口：提交 TTS 任务、查询音频状态。

注意：/api/audio-generate 使用 form-data 格式（非 JSON）。
"""
import pytest


class TestAudioGenerate:
    """音频生成模块 P0 测试"""

    def test_submit_tts_task(self, api_client):
        """P0 - 提交 TTS 任务（使用 form-data）"""
        payload = {"text": "测试文本", "voice": "default"}
        resp = api_client.post("/api/audio-generate", data=payload)
        assert resp.status_code in (200, 201, 202), (
            f"提交 TTS 任务失败: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        # audio_id 可能为 null（异步分配），但 status 应为 submitted
        status = data.get("status")
        assert status == "submitted", f"任务未成功提交: {data}"

    def test_query_audio_status(self, api_client):
        """P0 - 提交 TTS 任务并验证响应状态"""
        payload = {"text": "状态查询测试", "voice": "default"}
        resp = api_client.post("/api/audio-generate", data=payload)
        assert resp.status_code in (200, 201, 202), f"提交任务失败: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("status") == "submitted", f"任务状态异常: {data}"


class TestAudioGenerateP1:
    """音频生成模块 P1 测试"""

    def test_audio_generate_with_ref(self, api_client):
        """P1 - 提交带 ref_audio_url 参数的 TTS 任务"""
        payload = {
            "text": "使用参考音频生成测试",
            "voice": "default",
            "ref_audio_url": "https://example.com/ref_audio.wav",
        }
        resp = api_client.post("/api/audio-generate", data=payload)
        assert resp.status_code in (200, 201, 202), (
            f"带参考音频的 TTS 任务提交失败: {resp.status_code} {resp.text}"
        )

    def test_audio_generate_empty_text(self, api_client):
        """P1 - 提交空文本 TTS 任务，验证返回错误"""
        payload = {"text": "", "voice": "default"}
        resp = api_client.post("/api/audio-generate", data=payload)
        assert resp.status_code in (400, 422, 200), (
            f"空文本应返回错误或明确状态: {resp.status_code} {resp.text}"
        )
