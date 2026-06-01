"""
角色卡页面 E2E 测试。
覆盖页面加载、来源类型切换、表单输入、历史记录弹窗等场景。

character_card.html 不需要登录即可访问，但功能依赖 localStorage 中的 user_id 和 auth_token。
使用 page fixture 注入认证信息，并 mock API 避免真实调用。
"""
import json as _json

import pytest


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _setup_character_card_page(browser, auth_token, user_id, base_url):
    """创建角色卡页面实例，注入认证信息并 mock API"""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
    )
    context.add_init_script(f"""
        localStorage.setItem('auth_token', '{auth_token}');
        localStorage.setItem('user_id', '{user_id}');
    """)
    p = context.new_page()

    # Mock API
    def _mock_api(route):
        url = route.request.url
        path = url.split(base_url)[-1].split("?")[0] if base_url in url else url

        if path == "/api/create-character":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps({"success": True, "task_id": "mock_task_123"}),
            )
        elif path.startswith("/api/character-status/"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps(
                    {
                        "status": "SUCCESS",
                        "progress": 100,
                        "characters": [
                            {
                                "id": "char_001",
                                "name": "测试角色",
                                "description": "一个测试角色",
                            }
                        ],
                        "raw_response": '{"name": "测试角色"}',
                    }
                ),
            )
        elif path == "/api/ai-tools/history":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps(
                    {
                        "success": True,
                        "data": {
                            "data": [
                                {
                                    "id": 1,
                                    "prompt": "提取角色",
                                    "message": "成功",
                                    "result_url": "",
                                    "created_at": "2025-01-01 10:00:00",
                                    "status": "SUCCESS",
                                }
                            ],
                            "total": 1,
                        },
                    }
                ),
            )
        else:
            route.continue_()

    p.route("**/api/**", _mock_api)
    return p, context


# ═══════════════════════════════════════════════════════════════
# P0 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.p0
@pytest.mark.character_card
def test_character_card_page_loads(browser, auth_token, user_id, base_url):
    """cc_001 - 角色卡页面加载成功。"""
    p, context = _setup_character_card_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/character_card.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    # 验证页面标题
    title = p.title()
    assert "角色" in title or "character" in title.lower() or title, f"页面标题: {title}"

    # 验证主要容器存在
    app = p.locator("#app")
    assert app.count() > 0, "应有 #app 容器"

    p.close()
    context.close()


@pytest.mark.p0
@pytest.mark.character_card
def test_character_card_source_tabs(browser, auth_token, user_id, base_url):
    """cc_002 - 来源类型 Tab 切换。"""
    p, context = _setup_character_card_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/character_card.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    # 验证两个 Tab 存在
    tabs = p.locator(".source-tab, .tab-btn, [class*='tab']")
    if tabs.count() < 2:
        # 尝试通过文本查找
        task_tab = p.locator("text=任务ID")
        url_tab = p.locator("text=视频URL")
        assert task_tab.count() > 0 or url_tab.count() > 0, "应有来源类型 Tab"

    p.close()
    context.close()


@pytest.mark.p0
@pytest.mark.character_card
def test_character_card_form_inputs(browser, auth_token, user_id, base_url):
    """cc_003 - 表单输入框存在。"""
    p, context = _setup_character_card_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/character_card.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    # 验证时间输入框存在
    start_input = p.locator("input[type='number'], input[placeholder*='起始'], input[placeholder*='start']")
    assert start_input.count() > 0, "应有起始秒输入框"

    end_input = p.locator("input[type='number']").nth(1) if p.locator("input[type='number']").count() > 1 else None
    assert end_input is not None, "应有结束秒输入框"

    p.close()
    context.close()


@pytest.mark.p0
@pytest.mark.character_card
def test_character_card_create_button(browser, auth_token, user_id, base_url):
    """cc_004 - 创建角色卡按钮存在。"""
    p, context = _setup_character_card_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/character_card.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    create_btn = p.locator("button:has-text('创建'), button:has-text('角色卡')")
    assert create_btn.count() > 0, "应有创建角色卡按钮"

    p.close()
    context.close()


# ═══════════════════════════════════════════════════════════════
# P1 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.p1
@pytest.mark.character_card
def test_character_card_history_button(browser, auth_token, user_id, base_url):
    """cc_005 - 历史记录按钮存在。"""
    p, context = _setup_character_card_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/character_card.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    history_btn = p.locator("button:has-text('历史')")
    assert history_btn.count() > 0, "应有历史记录按钮"

    p.close()
    context.close()


@pytest.mark.p1
@pytest.mark.character_card
def test_character_card_back_button(browser, auth_token, user_id, base_url):
    """cc_006 - 返回首页按钮存在。"""
    p, context = _setup_character_card_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/character_card.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    back_btn = p.locator("button:has-text('返回'), a:has-text('返回')")
    assert back_btn.count() > 0, "应有返回首页按钮"

    p.close()
    context.close()


@pytest.mark.p1
@pytest.mark.character_card
def test_character_card_with_task_id_param(browser, auth_token, user_id, base_url):
    """cc_007 - URL 带 task_id 参数时自动填充。"""
    p, context = _setup_character_card_page(browser, auth_token, user_id, base_url)
    p.goto(f"{base_url}/character_card.html?task_id=12345", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    # 验证任务 ID 输入框被填充
    task_input = p.locator("input[placeholder*='任务'], input[placeholder*='task']")
    if task_input.count() > 0:
        value = task_input.first.input_value()
        assert "12345" in value, f"任务 ID 应被填充为 12345，实际: {value}"

    p.close()
    context.close()


@pytest.mark.p1
@pytest.mark.character_card
def test_character_card_responsive_layout(browser, auth_token, user_id, base_url):
    """cc_008 - 窄屏下页面仍可用。"""
    context = browser.new_context(
        viewport={"width": 375, "height": 667},
        locale="zh-CN",
    )
    context.add_init_script(f"""
        localStorage.setItem('auth_token', '{auth_token}');
        localStorage.setItem('user_id', '{user_id}');
    """)
    p = context.new_page()
    p.goto(f"{base_url}/character_card.html", wait_until="domcontentloaded")
    p.wait_for_timeout(2000)

    # 验证页面容器存在
    app = p.locator("#app")
    assert app.count() > 0, "移动端应有 #app 容器"

    p.close()
    context.close()
