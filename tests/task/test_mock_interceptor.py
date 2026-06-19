"""
task.mock_interceptor 纯逻辑单元测试（不依赖 DB）。

覆盖：mock_task_id 识别/生成、各通道响应结构、按主分类解析 mock URL
（验证图编模型 category=IMAGE_EDIT 但 categories=[TEXT_TO_IMAGE] 时取 image_edit 而非 text_to_image）、
命中计数器。
"""
from unittest.mock import patch, MagicMock

import pytest

from config.unified_config import TaskCategory
from task import mock_interceptor as mi


# ──────────────── is_mock_id ────────────────
class TestIsMockId:
    def test_recognizes_mock_prefix(self):
        assert mi.is_mock_id("mock_task_abc123") is True

    def test_rejects_real_external_id(self):
        assert mi.is_mock_id("RH_task_123") is False
        assert mi.is_mock_id("12345") is False
        assert mi.is_mock_id("") is False

    def test_rejects_non_str(self):
        assert mi.is_mock_id(None) is False
        assert mi.is_mock_id(12345) is False
        assert mi.is_mock_id(["mock_task_x"]) is False


# ──────────────── generate_mock_project_id ────────────────
class TestGenerateMockProjectId:
    def test_prefix_and_length(self):
        pid = mi.generate_mock_project_id()
        assert pid.startswith(mi.MOCK_PROJECT_PREFIX)
        # 前缀 + 16 hex
        assert len(pid) == len(mi.MOCK_PROJECT_PREFIX) + 16

    def test_hex_only_after_prefix(self):
        pid = mi.generate_mock_project_id()
        assert all(c in "0123456789abcdef" for c in pid[len(mi.MOCK_PROJECT_PREFIX):])

    def test_unique(self):
        ids = {mi.generate_mock_project_id() for _ in range(200)}
        assert len(ids) == 200


# ──────────────── 响应结构构造 ────────────────
class TestResponseConstructors:
    def test_visual_async_submit(self):
        r = mi.visual_async_submit_result(5)
        assert r["success"] is True
        assert r["project_id"].startswith(mi.MOCK_PROJECT_PREFIX)

    def test_visual_async_status_success(self):
        with patch.object(mi, "resolve_mock_url_for_visual", return_value="/upload/mock/v.mp4"):
            r = mi.visual_async_status_result(5)
        assert r["status"] == "SUCCESS"
        assert r["result_url"] == "/upload/mock/v.mp4"

    def test_visual_sync_result(self):
        with patch.object(mi, "resolve_mock_url_for_visual", return_value="/upload/mock/i.png"):
            r = mi.visual_sync_result(5)
        assert r["success"] is True
        assert r["sync_mode"] is True
        assert r["result_url"] == "/upload/mock/i.png"

    def test_comfyui_submit_result(self):
        r = mi.comfyui_submit_result(5)
        assert r["status"] == "submitted"
        assert len(r["project_ids"]) == 1
        assert r["project_ids"][0].startswith(mi.MOCK_PROJECT_PREFIX)

    def test_comfyui_status_success_structure(self):
        # _handle_task_success 接收 tasks[0] 元素，需含 results[0].file_url
        r = mi.comfyui_status_success("/upload/mock/g.png")
        assert r["status"] == "SUCCESS"
        assert r["results"][0]["file_url"] == "/upload/mock/g.png"
        assert r["results"][0]["result_url"] == "/upload/mock/g.png"

    def test_async_submit_result(self):
        r = mi.async_submit_result("runninghub_audio")
        assert r["success"] is True
        assert r["project_id"].startswith(mi.MOCK_PROJECT_PREFIX)


# ──────────────── resolve_mock_url_for_visual（主分类优先）────────────────
class TestResolveMockUrl:
    @staticmethod
    def _cfg(category, categories=None):
        c = MagicMock()
        c.category = category
        c.categories = categories or []
        return c

    def test_image_edit_primary_wins_over_text_to_image_category(self):
        """关键回归：图编模型主分类 IMAGE_EDIT + categories=[TEXT_TO_IMAGE]
        必须取 image_edit，不能误取 text_to_image（方案 P1-3 修复点）。"""
        with patch.object(mi, "UnifiedConfigRegistry") as reg:
            reg.get_by_id.return_value = self._cfg(
                TaskCategory.IMAGE_EDIT, [TaskCategory.TEXT_TO_IMAGE]
            )
            with patch.object(mi, "_img", side_effect=lambda k: f"/upload/mock/{k}.png"):
                url = mi.resolve_mock_url_for_visual(1)
        assert url == "/upload/mock/image_edit.png"

    def test_text_to_image_primary(self):
        with patch.object(mi, "UnifiedConfigRegistry") as reg:
            reg.get_by_id.return_value = self._cfg(TaskCategory.TEXT_TO_IMAGE)
            with patch.object(mi, "_img", side_effect=lambda k: f"/upload/mock/{k}.png"):
                url = mi.resolve_mock_url_for_visual(2)
        assert url == "/upload/mock/text_to_image.png"

    def test_image_to_video_primary(self):
        with patch.object(mi, "UnifiedConfigRegistry") as reg:
            reg.get_by_id.return_value = self._cfg(TaskCategory.IMAGE_TO_VIDEO)
            with patch.object(mi, "_vid", side_effect=lambda k: f"/upload/mock/{k}.mp4"):
                url = mi.resolve_mock_url_for_visual(3)
        assert url == "/upload/mock/image_to_video.mp4"

    def test_digital_human_uses_video_bucket(self):
        with patch.object(mi, "UnifiedConfigRegistry") as reg:
            reg.get_by_id.return_value = self._cfg(TaskCategory.DIGITAL_HUMAN)
            with patch.object(mi, "_vid", side_effect=lambda k: f"/upload/mock/{k}.mp4"):
                url = mi.resolve_mock_url_for_visual(4)
        assert url == "/upload/mock/digital_human.mp4"

    def test_text_to_video_falls_to_video_bucket(self):
        with patch.object(mi, "UnifiedConfigRegistry") as reg:
            reg.get_by_id.return_value = self._cfg(
                TaskCategory.IMAGE_TO_VIDEO, [TaskCategory.TEXT_TO_VIDEO]
            )
            with patch.object(mi, "_vid", side_effect=lambda k: f"/upload/mock/{k}.mp4"):
                url = mi.resolve_mock_url_for_visual(5)
        # IMAGE_TO_VIDEO 命中（pick 顺序：IMAGE_TO_VIDEO 在前）
        assert url == "/upload/mock/image_to_video.mp4"

    def test_unknown_type_returns_none(self):
        with patch.object(mi, "UnifiedConfigRegistry") as reg:
            reg.get_by_id.return_value = None
            assert mi.resolve_mock_url_for_visual(99999) is None

    def test_exception_returns_none(self):
        with patch.object(mi, "UnifiedConfigRegistry") as reg:
            reg.get_by_id.side_effect = RuntimeError("boom")
            assert mi.resolve_mock_url_for_visual(1) is None


# ──────────────── 命中计数器 ────────────────
class TestCounters:
    def test_bump_increments_summary(self):
        before = mi.mock_hit_summary().get("unit_test_chan", 0)
        mi._bump("unit_test_chan")
        mi._bump("unit_test_chan")
        after = mi.mock_hit_summary().get("unit_test_chan", 0)
        assert after - before >= 2

    def test_constructor_bumps_channel(self):
        before = mi.mock_hit_summary().get("visual_async_submit", 0)
        mi.visual_async_submit_result(1)
        after = mi.mock_hit_summary().get("visual_async_submit", 0)
        assert after > before
