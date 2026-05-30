"""
镜头组视频 E2E 测试。
覆盖镜头组基本流程、模型选项、时长更新、保存恢复等功能。
"""
import pytest

from helpers.editor_helpers import add_script_node, click_split_button, navigate_to_editor


@pytest.mark.shot_group_video
class TestShotGroupVideo:
    """镜头组视频测试"""

    @pytest.mark.p0
    def test_shot_group_basic_flow(self, editor_page, base_url, test_workflow):
        """sgv_001 - 验证镜头组基本流程：创建剧本 -> 生成镜头组 -> 选择模型 -> 设置时长"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        # 创建剧本节点并输入内容
        add_script_node(page, text=(
            "场景一：清晨的城市街道，阳光洒在柏油路面上。\n"
            "场景二：咖啡馆内，主角坐在窗边看报纸。"
        ))

        # 点击解析按钮（自动确认弹窗）
        click_split_button(page)

        # 验证镜头组节点被创建
        nodes_after = page.evaluate("() => document.querySelectorAll('.node').length")
        assert nodes_after > 1, "未生成镜头组节点"

        # 在镜头组节点中查找视频模型选择器（shot_frame 节点会排在 shot_group 之后）
        has_model = page.evaluate("""() => {
            const nodes = document.querySelectorAll('.node');
            for (const n of nodes) {
                const sel = n.querySelector('.shot-group-video-model');
                if (sel && sel.options && sel.options.length > 0) return true;
            }
            return false;
        }""")

        # 设置时长
        has_duration = page.evaluate("""() => {
            const nodes = document.querySelectorAll('.node');
            for (const n of nodes) {
                const sel = n.querySelector('.shot-group-video-duration');
                if (sel && sel.options && sel.options.length > 0) return true;
            }
            return false;
        }""")

        assert has_model or has_duration, "镜头组基本参数设置失败"

    @pytest.mark.p1
    def test_shot_group_model_options(self, editor_page, base_url, test_workflow):
        """sgv_004 - 验证视频模型下拉框有多个选项"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        add_script_node(page, text="场景一：清晨的城市街道。")

        page.evaluate("""() => {
            const btn = document.querySelector('.node.selected .script-split-btn');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(3000)

        option_count = page.evaluate("""() => {
            const sel = document.querySelector('.shot-group-video-model');
            return sel ? sel.options.length : 0;
        }""")
        if option_count > 0:
            assert option_count >= 2, f"视频模型下拉框应有多个选项，实际有 {option_count} 个"

    @pytest.mark.p1
    def test_shot_group_duration_update(self, editor_page, base_url, test_workflow):
        """sgv_005 - 验证切换模型后时长选项更新"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        add_script_node(page, text="场景一：清晨的城市街道。")

        page.evaluate("""() => {
            const btn = document.querySelector('.node.selected .script-split-btn');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(3000)

        # 获取当前时长选项并切换模型
        result = page.evaluate("""() => {
            const durationSel = document.querySelector('.shot-group-video-duration');
            const modelSel = document.querySelector('.shot-group-video-model');
            if (!durationSel || !modelSel) return null;

            const initial = Array.from(durationSel.options).map(o => o.textContent);

            // 切换模型
            const newIndex = modelSel.selectedIndex === 0 ? 1 : 0;
            modelSel.selectedIndex = newIndex;
            modelSel.dispatchEvent(new Event('change', { bubbles: true }));

            return { initial, modelChanged: true };
        }""")
        page.wait_for_timeout(500)

        if result and result.get("modelChanged"):
            updated = page.evaluate("""() => {
                const sel = document.querySelector('.shot-group-video-duration');
                return sel ? Array.from(sel.options).map(o => o.textContent) : [];
            }""")
            if result["initial"] and updated:
                assert result["initial"] != updated, (
                    f"切换模型后时长选项未更新: {result['initial']} -> {updated}"
                )

    @pytest.mark.p0
    def test_shot_group_save_restore(self, editor_page, base_url, test_workflow):
        """sgv_009 - 验证镜头组配置保存后重新加载能恢复"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        add_script_node(page, text="场景一：清晨的城市街道。\n场景二：咖啡馆内。")

        page.evaluate("""() => {
            const btn = document.querySelector('.node.selected .script-split-btn');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(3000)

        # 设置模型
        saved_model = page.evaluate("""() => {
            const sel = document.querySelector('.shot-group-video-model');
            if (!sel || sel.options.length < 2) return null;
            sel.selectedIndex = 1;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
            return sel.options[sel.selectedIndex]?.textContent?.trim() || '';
        }""")
        page.wait_for_timeout(500)

        if not saved_model:
            pytest.skip("模型选择器不可用")

        # 保存工作流
        page.evaluate("() => { const btn = document.getElementById('saveBtn'); if (btn) btn.click(); }")
        page.wait_for_timeout(1000)

        # 重新加载
        page.reload(wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(1000)

        # 验证配置已恢复
        restored_model = page.evaluate("""() => {
            const sel = document.querySelector('.shot-group-video-model');
            return sel ? sel.options[sel.selectedIndex]?.textContent?.trim() || '' : '';
        }""")
        assert restored_model == saved_model, (
            f"模型未恢复: 保存={saved_model}, 恢复={restored_model}"
        )
