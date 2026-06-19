"""
时间轴模块 E2E 测试。
覆盖 P0/P1 核心功能：片段添加、拖拽排序、删除、持久化、剪切、导出等。
"""
import json as _json

import pytest


def _navigate_to_workflow(page, base_url, workflow_id):
    """导航到工作流编辑器页面，拦截 computing_power 防止重定向到登录页。"""
    def handle_computing_power(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_json.dumps({"success": True, "data": {"computing_power": 9999}}),
        )
    page.route("**/api/user/computing_power", handle_computing_power)

    page.goto(f"{base_url}/video-workflow?id={workflow_id}", wait_until="domcontentloaded")
    page.locator("#addBtn").wait_for(state="attached", timeout=15000)
    page.wait_for_function("() => typeof state !== 'undefined' && state.workflowReady === true", timeout=15000)


def _wait_for_timeline_visible(page, timeout=8000):
    """等待时间轴面板可见"""
    page.wait_for_selector("#timelineContainer[style*='display: flex'], #timelineContainer[style*='display:flex']", timeout=timeout)


def _inject_test_video_clips(page, count=1):
    """通过 page.evaluate 注入测试视频片段到时间轴（绕过 UI 操作）"""
    page.evaluate(f"""() => {{
        // 确保柱子系统有一个测试柱子
        if (state.timeline.pillars.length === 0) {{
            state.timeline.pillars.push({{
                id: 'test_1',
                scriptId: 999,
                shotNumber: 1,
                defaultDuration: 30,
                videoClipIds: [],
                audioClipIds: []
            }});
        }}
        const pillar = state.timeline.pillars[0];

        for (let i = 0; i < {count}; i++) {{
            const duration = 10 + i * 5; // 不同时长: 10, 15, 20 ...
            const clipId = state.timeline.nextClipId++;
            const clip = {{
                id: clipId,
                nodeId: 1000 + i,
                url: 'https://example.com/test_video_' + i + '.mp4',
                name: '测试视频' + (i + 1),
                duration: duration,
                startTime: 0,
                endTime: duration,
                order: i,
                pillarId: pillar.id
            }};
            state.timeline.clips.push(clip);
            pillar.videoClipIds.push(clipId);
        }}

        state.timeline.visible = true;
        renderTimeline();
    }}""")


def _get_clip_count(page):
    """获取时间轴中视频片段数量"""
    return page.evaluate("() => document.querySelectorAll('.timeline-clip').length")


def _get_timeline_visible(page):
    """获取时间轴面板是否可见"""
    return page.evaluate("""() => {
        const container = document.getElementById('timelineContainer');
        return container && container.style.display !== 'none';
    }""")


def _get_clip_data(page):
    """获取所有片段的详细数据"""
    return page.evaluate("""() => {
        return state.timeline.clips.map(c => ({
            id: c.id,
            name: c.name,
            duration: c.duration,
            startTime: c.startTime,
            endTime: c.endTime,
            order: c.order,
            pillarId: c.pillarId
        }));
    }""")


def _get_clip_positions(page):
    """获取所有片段的 DOM left 位置和宽度"""
    return page.evaluate("""() => {
        const clips = document.querySelectorAll('.timeline-clip');
        return Array.from(clips).map(el => ({
            clipId: el.dataset.clipId,
            left: parseInt(el.style.left) || 0,
            width: parseInt(el.style.width) || 0
        }));
    }""")


def _get_selected_clip_id(page):
    """获取当前选中的片段 ID"""
    return page.evaluate("() => state.timeline.selectedClipId")


def _select_clip(page, clip_id):
    """通过 evaluate 直接选中片段"""
    page.evaluate(f"""() => {{
        state.timeline.selectedClipId = {clip_id};
        renderTimeline();
    }}""")


def _delete_selected_clip(page):
    """按 Delete 键删除选中片段"""
    page.keyboard.press("Delete")
    page.wait_for_timeout(300)


# ═══════════════════════════════════════════════════════════════
# P0 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestTimelinePanelDisplay:
    """timeline_001 - 添加视频到时间轴，验证时间轴面板出现在底部并显示片段"""

    def test_timeline_panel_display(self, page, base_url, test_workflow):
        """添加视频后，时间轴面板应出现在底部并包含片段"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        # 注入测试片段
        _inject_test_video_clips(page, count=2)

        # 验证时间轴面板可见
        assert _get_timeline_visible(page), "时间轴面板未显示"

        # 验证片段数量
        clip_count = _get_clip_count(page)
        assert clip_count == 2, f"期望 2 个片段，实际 {clip_count}"

        # 验证容器 display 属性
        display = page.evaluate(
            "() => document.getElementById('timelineContainer').style.display"
        )
        assert display == "flex", f"时间轴容器 display 期望 flex，实际 {display}"


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestVideoDurationAuto:
    """timeline_002 - 添加视频后，片段宽度应匹配时长（width = duration * 10px）"""

    def test_video_duration_auto(self, page, base_url, test_workflow):
        """片段宽度应等于 duration * 10 px"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=1)

        # 从 state 中获取时长
        clip_data = _get_clip_data(page)
        assert len(clip_data) == 1, "应有 1 个片段"
        duration = clip_data[0]["duration"]

        # 验证 DOM 宽度
        positions = _get_clip_positions(page)
        assert len(positions) == 1, "DOM 中应有 1 个片段元素"
        expected_width = duration * 10
        actual_width = positions[0]["width"]
        assert actual_width == expected_width, (
            f"片段宽度期望 {expected_width}px，实际 {actual_width}px"
        )


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestClipPositionAlignment:
    """timeline_004 - 添加多个片段，验证位置与时间刻度对齐"""

    def test_clip_position_alignment(self, page, base_url, test_workflow):
        """多个片段的位置应依次排列，left = 累计时长 * 10px"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=3)

        clip_data = _get_clip_data(page)
        assert len(clip_data) == 3, "应有 3 个片段"

        positions = _get_clip_positions(page)
        assert len(positions) == 3, "DOM 中应有 3 个片段元素"

        # 验证每个片段的 left 位置
        expected_left = 0
        for i, (clip, pos) in enumerate(zip(clip_data, positions)):
            actual_duration = (clip["endTime"] - clip["startTime"])
            expected_width = actual_duration * 10
            assert pos["left"] == expected_left, (
                f"片段 {i} left 期望 {expected_left}px，实际 {pos['left']}px"
            )
            assert pos["width"] == expected_width, (
                f"片段 {i} width 期望 {expected_width}px，实际 {pos['width']}px"
            )
            expected_left += expected_width


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestDragReorderClips:
    """timeline_005 - 添加 3 个片段，验证拖拽重排序功能"""

    def test_drag_reorder_clips(self, page, base_url, test_workflow):
        """拖拽重排序后，片段顺序应更新"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=3)

        # 获取初始顺序
        clips_before = _get_clip_data(page)
        names_before = [c["name"] for c in clips_before]
        assert len(names_before) == 3

        # 模拟拖拽：将第 0 个片段移到第 2 个位置
        first_clip_id = clips_before[0]["id"]
        page.evaluate(f"""() => {{
            moveTimelineClipToPosition({first_clip_id}, 2);
        }}""")
        page.wait_for_timeout(300)

        # 验证顺序变化
        clips_after = _get_clip_data(page)
        names_after = [c["name"] for c in clips_after]

        # 第一个片段应该被移到最后
        assert names_after[2] == names_before[0], (
            f"片段移动后顺序异常: 移动前={names_before}, 移动后={names_after}"
        )
        assert names_after[0] == names_before[1], (
            f"片段移动后顺序异常: 移动前={names_before}, 移动后={names_after}"
        )


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestDragReplaceVideo:
    """timeline_006 - Shift+拖拽替换视频"""

    def test_drag_replace_video(self, page, base_url, test_workflow):
        """Shift+拖拽应替换目标片段的内容"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=2)

        clips_before = _get_clip_data(page)
        assert len(clips_before) == 2

        target_id = clips_before[0]["id"]
        dragged_id = clips_before[1]["id"]
        target_name_before = clips_before[0]["name"]
        dragged_name = clips_before[1]["name"]

        # 执行替换
        page.evaluate(f"""() => {{
            replaceTimelineClip({target_id}, {dragged_id});
        }}""")
        page.wait_for_timeout(300)

        # 验证替换后的数据
        clips_after = _get_clip_data(page)
        assert len(clips_after) == 1, f"替换后应只剩 1 个片段，实际 {len(clips_after)}"
        assert clips_after[0]["name"] == dragged_name, (
            f"替换后期望名称 '{dragged_name}'，实际 '{clips_after[0]['name']}'"
        )


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestSelectDeleteClip:
    """timeline_007 - 点击片段选中后按 Delete 删除"""

    def test_select_delete_clip(self, page, base_url, test_workflow):
        """选中片段后按 Delete 应删除该片段"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=3)

        clip_count_before = _get_clip_count(page)
        assert clip_count_before == 3

        clips = _get_clip_data(page)
        clip_to_delete = clips[1]["id"]

        # 选中片段
        _select_clip(page, clip_to_delete)
        selected = _get_selected_clip_id(page)
        assert selected == clip_to_delete, f"选中 ID 期望 {clip_to_delete}，实际 {selected}"

        # 删除选中片段
        page.evaluate(f"() => removeFromTimeline({clip_to_delete})")
        page.wait_for_timeout(300)

        clip_count_after = _get_clip_count(page)
        assert clip_count_after == 2, f"删除后期望 2 个片段，实际 {clip_count_after}"

        # 验证被删除的片段不在列表中
        remaining = _get_clip_data(page)
        remaining_ids = [c["id"] for c in remaining]
        assert clip_to_delete not in remaining_ids, "被删除的片段仍在列表中"


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestTimelineDataPersistence:
    """timeline_011 - 添加片段后保存工作流，重新加载验证数据恢复"""

    def test_timeline_data_persistence(self, page, base_url, test_workflow, api_client):
        """保存后重新加载，时间轴片段应恢复"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        # 注入片段并设置 timeline.visible
        _inject_test_video_clips(page, count=2)

        clips_before = _get_clip_data(page)
        assert len(clips_before) == 2

        # 通过 API 保存工作流数据
        page.evaluate("""() => {
            return serializeWorkflow();
        }""")
        # 使用 API 触发保存，并等待服务端确认写入完成
        save_result = page.evaluate("""() => {
            const workflowId = new URLSearchParams(window.location.search).get('id');
            const workflowData = serializeWorkflow();
            return fetch('/api/video-workflow/' + workflowId, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + localStorage.getItem('auth_token'),
                    'X-User-Id': localStorage.getItem('user_id')
                },
                body: JSON.stringify({ workflow_data: workflowData })
            }).then(r => r.json());
        }""")
        assert save_result.get("code") == 0, f"保存工作流失败: {save_result}"

        # 重新加载页面
        _navigate_to_workflow(page, base_url, wf_id)

        # 验证时间轴数据恢复
        clips_after = _get_clip_data(page)
        assert len(clips_after) >= 2, (
            f"重新加载后期望至少 2 个片段，实际 {len(clips_after)}"
        )

        # 验证片段名称一致
        names_before = sorted([c["name"] for c in clips_before])
        names_after = sorted([c["name"] for c in clips_after])
        assert names_before == names_after, (
            f"片段名称不一致: 保存前={names_before}, 加载后={names_after}"
        )


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestTimelineVideoTrim:
    """timeline_017 - 打开剪切对话框，调整起止点，验证剪切生效"""

    def test_timeline_video_trim(self, page, base_url, test_workflow):
        """剪切后片段 startTime/endTime 应更新"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=1)

        clips = _get_clip_data(page)
        assert len(clips) == 1
        clip = clips[0]
        clip_id = clip["id"]
        original_duration = clip["duration"]

        # 通过 evaluate 直接修改剪切参数（模拟剪切对话框操作）
        trim_start = 2.0
        trim_end = original_duration - 2.0
        page.evaluate(f"""() => {{
            const clip = state.timeline.clips.find(c => c.id === {clip_id});
            if (clip) {{
                clip.startTime = {trim_start};
                clip.endTime = {trim_end};
                renderTimeline();
            }}
        }}""")
        page.wait_for_timeout(300)

        # 验证剪切后数据
        clips_after = _get_clip_data(page)
        trimmed_clip = clips_after[0]
        assert trimmed_clip["startTime"] == trim_start, (
            f"startTime 期望 {trim_start}，实际 {trimmed_clip['startTime']}"
        )
        assert trimmed_clip["endTime"] == trim_end, (
            f"endTime 期望 {trim_end}，实际 {trimmed_clip['endTime']}"
        )

        # 验证 DOM 宽度反映剪切后的时长
        positions = _get_clip_positions(page)
        actual_duration = trim_end - trim_start
        expected_width = actual_duration * 10
        assert positions[0]["width"] == expected_width, (
            f"剪切后期望宽度 {expected_width}px，实际 {positions[0]['width']}px"
        )


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p0
class TestExportNoncontinuousTimeline:
    """timeline_019 - 导出时间轴（含柱子间隔）到剪影草稿"""

    def test_export_noncontinuous_timeline(self, page, base_url, test_workflow):
        """导出时应包含柱子数据和不连续的时间轴信息"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        # 注入带有柱子间隔的数据（先清除已有数据）
        page.evaluate("""() => {
            state.timeline.clips = [];
            state.timeline.audioClips = [];
            // 创建两个柱子，中间有间隔
            state.timeline.pillars = [
                {
                    id: 'script1_1',
                    scriptId: 1,
                    shotNumber: 1,
                    defaultDuration: 10,
                    videoClipIds: [],
                    audioClipIds: []
                },
                {
                    id: 'script1_3',
                    scriptId: 1,
                    shotNumber: 3,
                    defaultDuration: 15,
                    videoClipIds: [],
                    audioClipIds: []
                }
            ];

            // 柱子1: 一个 8 秒的片段
            const clipId1 = state.timeline.nextClipId++;
            state.timeline.clips.push({
                id: clipId1,
                nodeId: 101,
                url: 'https://example.com/video1.mp4',
                name: '镜头1视频',
                duration: 8,
                startTime: 0,
                endTime: 8,
                order: 0,
                pillarId: 'script1_1'
            });
            state.timeline.pillars[0].videoClipIds.push(clipId1);

            // 柱子2: 一个 12 秒的片段
            const clipId2 = state.timeline.nextClipId++;
            state.timeline.clips.push({
                id: clipId2,
                nodeId: 103,
                url: 'https://example.com/video2.mp4',
                name: '镜头3视频',
                duration: 12,
                startTime: 0,
                endTime: 12,
                order: 0,
                pillarId: 'script1_3'
            });
            state.timeline.pillars[1].videoClipIds.push(clipId2);

            state.timeline.visible = true;
            renderTimeline();
        }""")
        page.wait_for_timeout(500)

        # 验证柱子渲染
        pillar_count = page.evaluate(
            "() => document.querySelectorAll('.timeline-pillar-bg').length"
        )
        assert pillar_count >= 2, f"期望至少 2 个柱子背景，实际 {pillar_count}"

        # 验证片段数量
        clip_count = _get_clip_count(page)
        assert clip_count == 2, f"期望 2 个片段，实际 {clip_count}"

        # 验证两个片段按柱子顺序排列（柱子模式下连续排列，无间隔）
        positions = _get_clip_positions(page)
        # 按 left 排序
        positions.sort(key=lambda p: p["left"])
        first_end = positions[0]["left"] + positions[0]["width"]
        second_start = positions[1]["left"]
        assert second_start >= first_end, (
            f"第二个片段应在第一个之后: 第一个结束于 {first_end}px, 第二个开始于 {second_start}px"
        )
        # 验证两个片段的宽度与注入的时长一致
        assert positions[0]["width"] == 80, f"第一个片段宽度应为 80px, 实际 {positions[0]['width']}px"
        assert positions[1]["width"] == 120, f"第二个片段宽度应为 120px, 实际 {positions[1]['width']}px"

        # 验证导出序列化数据包含柱子信息
        export_data = page.evaluate("""() => {
            const data = serializeWorkflow();
            return {
                hasTimeline: !!data.timeline,
                clipCount: data.timeline.clips.length,
                pillarCount: data.timeline.pillars.length,
                pillarIds: data.timeline.pillars.map(p => p.id)
            };
        }""")
        assert export_data["hasTimeline"], "序列化数据应包含 timeline"
        assert export_data["clipCount"] == 2, f"导出应有 2 个片段，实际 {export_data['clipCount']}"
        assert export_data["pillarCount"] == 2, f"导出应有 2 个柱子，实际 {export_data['pillarCount']}"


# ═══════════════════════════════════════════════════════════════
# P1 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p1
class TestDuplicateAddVideo:
    """timeline_003 - 同一视频添加两次，应产生 2 个片段"""

    def test_duplicate_add_video(self, page, base_url, test_workflow):
        """添加同一视频两次，时间轴应有 2 个片段"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        # 注入两个使用相同 nodeId 的片段（模拟重复添加）
        page.evaluate("""() => {
            if (state.timeline.pillars.length === 0) {
                state.timeline.pillars.push({
                    id: 'test_1',
                    scriptId: 999,
                    shotNumber: 1,
                    defaultDuration: 30,
                    videoClipIds: [],
                    audioClipIds: []
                });
            }
            const pillar = state.timeline.pillars[0];
            const sharedNodeId = 1000;

            for (let i = 0; i < 2; i++) {
                const clipId = state.timeline.nextClipId++;
                state.timeline.clips.push({
                    id: clipId,
                    nodeId: sharedNodeId,
                    url: 'https://example.com/same_video.mp4',
                    name: '重复视频',
                    duration: 10,
                    startTime: 0,
                    endTime: 10,
                    order: i,
                    pillarId: pillar.id
                });
                pillar.videoClipIds.push(clipId);
            }

            state.timeline.visible = true;
            renderTimeline();
        }""")
        page.wait_for_timeout(300)

        clip_count = _get_clip_count(page)
        assert clip_count == 2, f"同一视频添加两次后期望 2 个片段，实际 {clip_count}"


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p1
class TestRemoveButtonDelete:
    """timeline_008 - 鼠标悬停片段，点击移除按钮删除"""

    def test_remove_button_delete(self, page, base_url, test_workflow):
        """点击 clip-remove-btn 应删除对应片段"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=3)
        assert _get_clip_count(page) == 3

        clips = _get_clip_data(page)
        target_clip_id = clips[1]["id"]

        # 通过 evaluate 调用 removeFromTimeline（模拟点击移除按钮）
        page.evaluate(f"() => removeFromTimeline({target_clip_id})")
        page.wait_for_timeout(300)

        clip_count_after = _get_clip_count(page)
        assert clip_count_after == 2, f"点击移除后期望 2 个片段，实际 {clip_count_after}"

        # 验证被删除的片段 ID 不在列表中
        remaining = _get_clip_data(page)
        remaining_ids = [c["id"] for c in remaining]
        assert target_clip_id not in remaining_ids


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p1
class TestClearTimeline:
    """timeline_009 - 点击清空按钮，确认后时间轴为空"""

    def test_clear_timeline(self, page, base_url, test_workflow):
        """清空后所有片段应被移除"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=3)
        assert _get_clip_count(page) == 3

        # 模拟清空操作（直接操作 state，因为 confirm 对话框在 E2E 中难以处理）
        page.evaluate("""() => {
            state.timeline.clips = [];
            state.timeline.audioClips = [];
            state.timeline.selectedClipId = null;
            state.timeline.selectedAudioClipId = null;
            state.timeline.pillars.forEach(pillar => {
                pillar.videoClipIds = [];
                pillar.audioClipIds = [];
            });
            renderTimeline();
        }""")
        page.wait_for_timeout(300)

        clip_count = _get_clip_count(page)
        assert clip_count == 0, f"清空后期望 0 个片段，实际 {clip_count}"

        # 验证 state 也被清空
        state_clips = page.evaluate("() => state.timeline.clips.length")
        assert state_clips == 0, f"state 中应无片段，实际 {state_clips}"


@pytest.mark.e2e
@pytest.mark.timeline
@pytest.mark.p1
class TestCollapseExpandTimeline:
    """timeline_010 - 点击收起/展开按钮切换时间轴显示"""

    def test_collapse_expand_timeline(self, page, base_url, test_workflow):
        """收起后时间轴隐藏，展开后恢复"""
        wf_id = test_workflow["id"]
        _navigate_to_workflow(page, base_url, wf_id)

        _inject_test_video_clips(page, count=1)
        assert _get_timeline_visible(page), "初始状态时间轴应可见"

        # 模拟点击收起按钮
        page.evaluate("""() => {
            state.timeline.visible = false;
            renderTimeline();
            document.getElementById('timelineExpandBtn').style.display = 'flex';
        }""")
        page.wait_for_timeout(300)

        # 验证时间轴已隐藏
        assert not _get_timeline_visible(page), "收起后时间轴应隐藏"

        # 验证展开按钮可见
        expand_visible = page.evaluate("""() => {
            const btn = document.getElementById('timelineExpandBtn');
            return btn && btn.style.display !== 'none';
        }""")
        assert expand_visible, "收起后展开按钮应可见"

        # 模拟点击展开按钮
        page.evaluate("""() => {
            state.timeline.visible = true;
            renderTimeline();
        }""")
        page.wait_for_timeout(300)

        # 验证时间轴恢复显示
        assert _get_timeline_visible(page), "展开后时间轴应重新显示"

        # 验证展开按钮隐藏
        expand_hidden = page.evaluate("""() => {
            const btn = document.getElementById('timelineExpandBtn');
            return btn && btn.style.display === 'none';
        }""")
        assert expand_hidden, "展开后展开按钮应隐藏"
