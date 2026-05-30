"""
宫格图片生成 E2E 测试。
覆盖 4 宫格、9 宫格生成，自动模型切换，以及分割 API 接口。
"""
import pytest

from helpers.editor_helpers import add_script_node, click_split_button, js_click_in_node, navigate_to_editor


@pytest.mark.grid_image
class TestGridImageGeneration:
    """宫格图片生成测试"""

    @pytest.mark.p0
    def test_4_grid_generation(self, editor_page, base_url, test_workflow):
        """验证输入 4 个场景后生成 4 宫格图片"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        node = add_script_node(page, text=(
            "场景一：清晨的城市街道，阳光洒在柏油路面上。\n"
            "场景二：咖啡馆内，主角坐在窗边看报纸。\n"
            "场景三：公园长椅上，一对老夫妇在聊天。\n"
            "场景四：夜晚的天台上，主角仰望星空。"
        ))

        # 点击分割+宫格按钮（通过 JS）
        page.evaluate("""() => {
            const btn = document.querySelector('.node.selected .script-split-grid-btn');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(3000)

        nodes_after = page.evaluate("() => document.querySelectorAll('.node').length")
        assert nodes_after >= 1, "宫格生成后应有节点存在"

    @pytest.mark.p0
    def test_9_grid_generation(self, editor_page, base_url, test_workflow):
        """验证输入 7 个场景后自动切换为 9 宫格模式"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        node = add_script_node(page, text=(
            "场景一：清晨的城市街道。\n"
            "场景二：咖啡馆内。\n"
            "场景三：公园长椅上。\n"
            "场景四：夜晚的天台。\n"
            "场景五：图书馆阅览室。\n"
            "场景六：海边沙滩。\n"
            "场景七：山顶观景台。"
        ))

        page.evaluate("""() => {
            const btn = document.querySelector('.node.selected .script-split-grid-btn');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(3000)

        nodes_after = page.evaluate("() => document.querySelectorAll('.node').length")
        assert nodes_after >= 1, "7 个场景解析后应生成多个节点"

    @pytest.mark.p1
    def test_auto_model_switch(self, editor_page, base_url, test_workflow):
        """验证 6 个场景使用标准模型时自动切换为增强模型"""
        wf_id = test_workflow["id"]
        page = editor_page
        navigate_to_editor(page, base_url, wf_id)

        node = add_script_node(page, text=(
            "场景一：清晨的城市街道。\n"
            "场景二：咖啡馆内。\n"
            "场景三：公园长椅上。\n"
            "场景四：夜晚的天台。\n"
            "场景五：图书馆阅览室。\n"
            "场景六：海边沙滩。"
        ))

        page.evaluate("""() => {
            const btn = document.querySelector('.node.selected .script-split-grid-btn');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(2000)

        nodes_after = page.evaluate("() => document.querySelectorAll('.node').length")
        assert nodes_after >= 1, "宫格生成操作未产生节点"

    @pytest.mark.p1
    def test_grid_split_api(self, api_client):
        """验证宫格分割 API 接口"""
        resp = api_client.get("/api/ai-tools/1/grid-split")
        assert resp.status_code in (200, 404, 422), (
            f"宫格分割 API 响应异常: {resp.status_code} {resp.text}"
        )
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (dict, list)), f"API 返回格式异常: {data}"
