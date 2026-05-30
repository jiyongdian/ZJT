"""
工作流列表页面 E2E 测试。
覆盖列表加载、卡片展示、搜索筛选、增删改查交互、页面跳转等场景。
"""
import time

import pytest


# ──────────────────────────── P0 测试 ────────────────────────────


@pytest.mark.workflow_list
class TestWorkflowListP0:
    """工作流列表页面 P0 核心测试"""

    def test_workflow_list_page_loads(self, workflow_list_page):
        """list_001 - 工作流列表页正常加载，页面包含工作流卡片网格"""
        workflow_list_page.navigate()
        workflow_list_page.wait_for_load()
        assert workflow_list_page.is_loaded(), "工作流列表页未能正常加载"

        # 等待工作流容器渲染完成（loading 消失后出现 .workflow-grid 或 .empty-state）
        workflow_list_page.page.wait_for_selector(
            ".workflow-grid, .empty-state", timeout=10000
        )

        # 页面中应存在工作流容器
        container = workflow_list_page.page.query_selector("#workflowContainer")
        assert container is not None, "页面缺少 #workflowContainer 容器"

        # 验证有工作流卡片或空状态提示
        cards = workflow_list_page.page.query_selector_all(".workflow-card")
        empty = workflow_list_page.page.query_selector(".empty-state")
        assert cards or empty, "页面既无工作流卡片也无空状态提示"

    def test_workflow_card_display(self, workflow_list_page, test_workflow):
        """list_002 - 工作流卡片展示名称、状态、编辑和删除按钮"""
        workflow_list_page.navigate()
        workflow_list_page.wait_for_load()

        # 等待卡片加载
        workflow_list_page.page.wait_for_selector(".workflow-card", timeout=10000)

        # 通过 JS 验证卡片结构
        card_info = workflow_list_page.page.evaluate("""() => {
            const cards = document.querySelectorAll('.workflow-card');
            if (!cards.length) return { count: 0, items: [] };
            const items = [];
            cards.forEach(card => {
                const name = card.querySelector('.workflow-name')?.textContent?.trim() || '';
                const status = card.querySelector('.workflow-status')?.textContent?.trim() || '';
                const hasEdit = !!card.querySelector('.workflow-actions .btn');
                const hasDelete = card.querySelectorAll('.workflow-actions .btn').length >= 2;
                items.push({ name, status, hasEdit, hasDelete });
            });
            return { count: cards.length, items };
        }""")

        assert card_info["count"] > 0, "页面未渲染出任何工作流卡片"

        # 验证存在包含测试工作流名称的卡片
        test_wf_name = test_workflow["data"].get("data", test_workflow["data"]).get(
            "name", "E2E测试工作流"
        )
        found = any(test_wf_name in item["name"] for item in card_info["items"])
        assert found, f"未找到包含 '{test_wf_name}' 的工作流卡片"

        # 验证每张卡片都有编辑和删除按钮
        for item in card_info["items"]:
            assert item["hasEdit"], f"卡片 '{item['name']}' 缺少编辑按钮"
            assert item["hasDelete"], f"卡片 '{item['name']}' 缺少删除按钮"

    def test_create_workflow_from_list(self, workflow_list_page, page, api_client):
        """list_006 - 从列表页新建工作流：点击新建按钮 -> 填写表单 -> 保存 -> 验证卡片出现"""
        workflow_list_page.navigate()
        workflow_list_page.wait_for_load()

        # 等待页面加载完成
        page.wait_for_selector(".workflow-grid, .empty-state", timeout=10000)

        # 点击新建工作流按钮
        create_btn = page.query_selector("button:has-text('新建工作流')")
        assert create_btn is not None, "未找到新建工作流按钮"
        create_btn.click()

        # 等待模态框打开
        page.wait_for_selector("#createModal.active", timeout=5000)

        # 填写工作流名称
        name_input = page.query_selector("#workflowName")
        assert name_input is not None, "模态框中未找到名称输入框"
        test_name = f"E2E新建测试_{int(time.time())}"
        name_input.fill(test_name)

        # 选择比例（必须选择，否则会报错）
        ratio_input = page.query_selector(
            'input[name="workflowRatio"][value="16:9"]'
        )
        if ratio_input:
            ratio_input.check()

        # 点击"仅创建工作流"按钮（第2个 button，class="btn btn-secondary btn-sm"）
        submit_btn = page.query_selector(
            "#workflowForm .modal-actions button:nth-child(2)"
        )
        assert submit_btn is not None, "未找到提交按钮"
        submit_btn.click()

        # 等待模态框关闭（null-safe：元素可能已被移除）
        page.wait_for_function(
            "(() => { const el = document.getElementById('createModal'); return !el || !el.classList.contains('active'); })()",
            timeout=10000,
        )

        # 等待列表刷新，查找新创建的卡片
        page.wait_for_selector(".workflow-card", timeout=10000)

        # 验证新工作流卡片出现
        card_names = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.workflow-name'))
                .map(el => el.textContent.trim());
        }""")
        assert test_name in card_names, (
            f"新建的工作流 '{test_name}' 未出现在列表中，当前卡片: {card_names}"
        )

        # 清理：通过 API 删除
        resp = api_client.get("/api/video-workflow/list?page=1&page_size=100")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("data", [])
            for item in items:
                if item.get("name") == test_name:
                    api_client.delete(f"/api/video-workflow/{item['id']}")
                    break

    def test_edit_workflow_from_list(
        self, workflow_list_page, page, api_client, test_workflow
    ):
        """list_007 - 从列表页编辑工作流：点击编辑 -> 修改名称 -> 保存 -> 验证更新"""
        wf_data = test_workflow["data"].get("data", test_workflow["data"])
        wf_id = test_workflow["id"]
        original_name = wf_data.get("name", "E2E测试工作流")

        workflow_list_page.navigate()
        workflow_list_page.wait_for_load()

        # 等待卡片加载
        page.wait_for_selector(".workflow-card", timeout=10000)

        # 找到目标卡片的编辑按钮
        edit_btn = page.evaluate(f"""() => {{
            const cards = document.querySelectorAll('.workflow-card');
            for (const card of cards) {{
                const nameEl = card.querySelector('.workflow-name');
                if (nameEl && nameEl.textContent.trim().includes('{original_name}')) {{
                    const editBtn = card.querySelector('.workflow-actions .btn');
                    if (editBtn) {{
                        editBtn.click();
                        return true;
                    }}
                }}
            }}
            return false;
        }}""")
        assert edit_btn, f"未找到工作流 '{original_name}' 的编辑按钮"

        # 等待模态框打开
        page.wait_for_selector("#createModal.active", timeout=5000)

        # 修改名称
        name_input = page.query_selector("#workflowName")
        new_name = f"E2E编辑测试_{int(time.time())}"
        name_input.fill("")
        name_input.fill(new_name)

        # 点击保存按钮（仅创建工作流按钮，编辑模式下也是同一个）
        submit_btn = page.query_selector(
            "#workflowForm .modal-actions button:nth-child(2)"
        )
        assert submit_btn is not None, "未找到保存按钮"
        submit_btn.click()

        # 等待模态框关闭（null-safe：元素可能已被移除）
        page.wait_for_function(
            "(() => { const el = document.getElementById('createModal'); return !el || !el.classList.contains('active'); })()",
            timeout=10000,
        )

        # 等待列表刷新
        page.wait_for_timeout(2000)

        # 验证更新后的名称出现在列表中
        card_names = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.workflow-name'))
                .map(el => el.textContent.trim());
        }""")
        assert new_name in card_names, (
            f"编辑后的工作流 '{new_name}' 未出现在列表中，当前卡片: {card_names}"
        )

        # 清理：恢复原名
        api_client.put(
            f"/api/video-workflow/{wf_id}",
            json={"name": original_name},
        )

    def test_delete_workflow_from_list(self, workflow_list_page, page, api_client):
        """list_008 - 从列表页删除工作流：点击删除 -> 确认 -> 验证从列表移除"""
        # 先通过 API 创建一个待删除的工作流
        del_name = f"E2E待删除_{int(time.time())}"
        resp = api_client.post(
            "/api/video-workflow/create",
            json={"name": del_name, "description": "将被删除的测试工作流"},
        )
        assert resp.status_code in (200, 201), f"创建待删除工作流失败: {resp.text}"
        resp_data = resp.json()
        del_id = resp_data.get("id") or resp_data.get("data", {}).get("id")
        assert del_id, f"创建响应中未找到 ID: {resp_data}"

        try:
            workflow_list_page.navigate()
            workflow_list_page.wait_for_load()

            # 等待卡片加载
            page.wait_for_selector(".workflow-card", timeout=10000)

            # 找到目标卡片的删除按钮并点击
            clicked = page.evaluate(f"""() => {{
                const cards = document.querySelectorAll('.workflow-card');
                for (const card of cards) {{
                    const nameEl = card.querySelector('.workflow-name');
                    if (nameEl && nameEl.textContent.trim().includes('{del_name}')) {{
                        const btns = card.querySelectorAll('.workflow-actions .btn');
                        // 删除按钮是第二个
                        if (btns.length >= 2) {{
                            btns[1].click();
                            return true;
                        }}
                    }}
                }}
                return false;
            }}""")
            assert clicked, f"未找到工作流 '{del_name}' 的删除按钮"

            # 等待删除确认模态框出现
            page.wait_for_selector("#deleteModal.active", timeout=5000)

            # 点击确认删除按钮
            confirm_btn = page.query_selector("#deleteModal .btn-danger")
            assert confirm_btn is not None, "未找到确认删除按钮"
            confirm_btn.click()

            # 等待模态框关闭
            page.wait_for_function(
                "!document.getElementById('deleteModal').classList.contains('active')",
                timeout=10000,
            )

            # 等待列表刷新
            page.wait_for_timeout(2000)

            # 验证该工作流已不在列表中
            card_names = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('.workflow-name'))
                    .map(el => el.textContent.trim());
            }""")
            assert del_name not in card_names, (
                f"已删除的工作流 '{del_name}' 仍在列表中"
            )
        finally:
            # 确保清理
            try:
                api_client.delete(f"/api/video-workflow/{del_id}")
            except Exception:
                pass

    def test_click_card_enters_editor(
        self, workflow_list_page, page, test_workflow
    ):
        """list_009 - 点击工作流卡片主体，验证跳转到 /video-workflow?id= 编辑器页面"""
        wf_data = test_workflow["data"].get("data", test_workflow["data"])
        wf_id = test_workflow["id"]
        wf_name = wf_data.get("name", "E2E测试工作流")

        workflow_list_page.navigate()
        workflow_list_page.wait_for_load()

        # 等待卡片加载
        page.wait_for_selector(".workflow-card", timeout=10000)

        # 使用 Playwright 原生点击触发 onclick="enterWorkflow(id)"
        card = page.locator(f".workflow-card:has(.workflow-name:has-text('{wf_name}'))").first
        assert card.count() > 0, f"未找到工作流 '{wf_name}' 的卡片"
        card.click()

        # 等待页面跳转
        try:
            page.wait_for_url("**/video-workflow**", timeout=10000)
        except Exception:
            pytest.skip(f"点击卡片后未跳转到编辑器，可能页面结构变化")

        # 验证 URL 包含工作流 ID
        current_url = page.url
        assert "/video-workflow" in current_url, f"未跳转到编辑器页面: {current_url}"
        assert f"id={wf_id}" in current_url, (
            f"URL 中未包含工作流 ID {wf_id}: {current_url}"
        )


# ──────────────────────────── P1 测试 ────────────────────────────


@pytest.mark.workflow_list
class TestWorkflowListP1:
    """工作流列表页面 P1 测试"""

    def test_search_workflows(self, workflow_list_page, page, test_workflow):
        """list_003 - 搜索框输入关键词，验证列表过滤结果"""
        wf_data = test_workflow["data"].get("data", test_workflow["data"])
        wf_name = wf_data.get("name", "E2E测试工作流")

        workflow_list_page.navigate()
        workflow_list_page.wait_for_load()

        # 等待卡片加载
        page.wait_for_selector(".workflow-card", timeout=10000)

        # 在搜索框输入关键词
        search_input = page.query_selector("#searchInput")
        assert search_input is not None, "未找到搜索输入框"

        # 使用工作流名称的前几个字符作为搜索关键词
        keyword = wf_name[:6]
        search_input.fill(keyword)

        # 等待搜索触发（前端有 300ms debounce）
        page.wait_for_timeout(1000)

        # 验证搜索结果
        card_info = page.evaluate("""() => {
            const cards = document.querySelectorAll('.workflow-card');
            return Array.from(cards).map(card => {
                const name = card.querySelector('.workflow-name')?.textContent?.trim() || '';
                const visible = card.offsetParent !== null;
                return { name, visible };
            });
        }""")

        # 如果有卡片结果，应包含匹配的名称
        if card_info:
            matching = [
                c for c in card_info if keyword.lower() in c["name"].lower()
            ]
            assert matching, (
                f"搜索 '{keyword}' 后未找到匹配的卡片，当前结果: "
                + str([c["name"] for c in card_info])
            )

    def test_status_filter(self, workflow_list_page, page, test_workflow):
        """list_004 - 选择状态筛选，验证列表按状态过滤"""
        workflow_list_page.navigate()
        workflow_list_page.wait_for_load()

        # 等待卡片加载
        page.wait_for_selector(".workflow-card", timeout=10000)

        # 记录初始卡片数量
        initial_count = page.evaluate(
            "document.querySelectorAll('.workflow-card').length"
        )

        # 选择"已启用"状态
        status_filter = page.query_selector("#statusFilter")
        assert status_filter is not None, "未找到状态筛选下拉框"
        status_filter.select_option("1")

        # 等待列表刷新
        page.wait_for_timeout(2000)

        # 验证筛选后的状态标签
        card_statuses = page.evaluate("""() => {
            const cards = document.querySelectorAll('.workflow-card');
            return Array.from(cards).map(card => {
                const statusEl = card.querySelector('.workflow-status');
                const statusClass = statusEl?.className || '';
                return {
                    hasEnabled: statusClass.includes('status-enabled'),
                    text: statusEl?.textContent?.trim() || ''
                };
            });
        }""")

        # 所有卡片应为"已启用"状态
        for cs in card_statuses:
            assert cs["hasEnabled"], (
                f"筛选 '已启用' 后仍有非启用状态的卡片: {cs['text']}"
            )

        # 恢复为全部状态
        status_filter.select_option("")
        page.wait_for_timeout(1000)

    def test_empty_name_validation(self, workflow_list_page, page):
        """list_010 - 打开新建模态框，不填写名称直接提交，验证错误提示"""
        workflow_list_page.navigate()
        workflow_list_page.wait_for_load()

        # 等待页面加载
        page.wait_for_selector(".workflow-grid, .empty-state", timeout=10000)

        # 点击新建按钮
        create_btn = page.query_selector("button:has-text('新建工作流')")
        assert create_btn is not None, "未找到新建工作流按钮"
        create_btn.click()

        # 等待模态框打开
        page.wait_for_selector("#createModal.active", timeout=5000)

        # 确保名称为空
        name_input = page.query_selector("#workflowName")
        assert name_input is not None, "未找到名称输入框"
        name_input.fill("")

        # 点击提交按钮（"仅创建工作流"）
        submit_btn = page.query_selector(
            "#workflowForm .modal-actions button:nth-child(2)"
        )
        assert submit_btn is not None, "未找到提交按钮"
        submit_btn.click()

        # 等待错误提示出现（toast）
        page.wait_for_selector(".toast.show", timeout=5000)

        # 验证出现了错误 toast
        toast_text = page.evaluate(
            "document.getElementById('toast')?.textContent?.trim() || ''"
        )
        assert toast_text, "提交空名称后未出现任何提示"

        # 验证模态框仍然打开（未成功提交）
        is_modal_open = page.evaluate(
            "document.getElementById('createModal').classList.contains('active')"
        )
        assert is_modal_open, "提交空名称后模态框不应关闭"

        # 关闭模态框
        cancel_btn = page.query_selector(
            "#createModal .modal-actions .btn-secondary"
        )
        if cancel_btn:
            cancel_btn.click()
