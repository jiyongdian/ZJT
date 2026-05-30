"""
工作流编辑器测试辅助函数。
提供节点创建、交互等通用操作。
所有节点操作通过 JS 直接调用全局函数，避免 placing 机制导致的 visibility 问题。
"""
import logging

logger = logging.getLogger(__name__)


def navigate_to_editor(page, base_url, workflow_id, auth_token=None, user_id=None):
    """导航到工作流编辑器并等待加载完成。

    通过 page.route() 拦截 /api/user/computing_power 请求，返回成功响应，
    防止 workflow.js 的 fetchComputingPower() 因认证失败而重定向到登录页。
    """
    import json as _json

    def handle_computing_power(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_json.dumps({
                "success": True,
                "data": {"computing_power": 9999}
            }),
        )

    page.route("**/api/user/computing_power", handle_computing_power)

    url = f"{base_url}/video-workflow?id={workflow_id}"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    page.locator("#addBtn").wait_for(state="attached", timeout=15000)


def create_node_via_js(page, node_type: str, data: dict = None, x: int = 200, y: int = 200):
    """通过 JS 全局函数创建节点，绕过 placing 机制。

    Args:
        page: Playwright page
        node_type: 节点类型 ("image", "script", "video", "shot_group", "camera_control" 等)
        data: 节点初始数据
        x, y: 节点位置
    Returns:
        节点 ID
    """
    func_name = f"create{node_type.replace('_', ' ').title().replace(' ', '')}NodeWithData"
    # 尝试带 Data 后缀的函数
    result = page.evaluate(f"""(x, y, data) => {{
        if (typeof {func_name} === 'function') {{
            return {func_name}({{ x, y, ...data, checkCollision: false }});
        }}
        // 回退：尝试不带 Data 的函数
        const funcName2 = '{func_name}'.replace('WithData', '');
        if (typeof window[funcName2] === 'function') {{
            return window[funcName2]({{ x, y, checkCollision: false }});
        }}
        return null;
    }}""", x, y, data or {})
    page.wait_for_timeout(500)
    return result


def make_all_nodes_visible(page):
    """强制使所有节点可见（绕过 placing 机制）。"""
    page.evaluate("""() => {
        document.querySelectorAll('.node').forEach(n => {
            if (n.style.visibility === 'hidden') n.style.visibility = '';
        });
        const container = document.querySelector('.canvas-container');
        if (container) container.classList.remove('placing');
    }""")
    page.wait_for_timeout(200)


def add_node(page, menu_id: str, timeout=1000):
    """点击添加按钮并选择菜单项，返回新创建的节点 locator。"""
    page.evaluate("() => document.getElementById('addMenu').classList.add('show')")
    page.wait_for_timeout(300)
    page.locator(f"#{menu_id}").click(force=True)
    page.wait_for_timeout(timeout)
    page.evaluate("() => document.getElementById('addMenu').classList.remove('show')")
    page.wait_for_timeout(500)

    # 模拟鼠标移动触发放置
    canvas = page.locator("#canvas")
    if canvas.count() > 0:
        box = canvas.bounding_box()
        if box:
            page.mouse.move(box["x"] + box["width"] * 0.4, box["y"] + box["height"] * 0.4)
            page.wait_for_timeout(300)

    make_all_nodes_visible(page)
    return page.locator(".node.selected").first


def get_selected_node(page):
    """获取当前选中的节点"""
    return page.locator(".node.selected").first


def add_script_node(page, text: str = "", timeout=1000):
    """创建剧本节点并输入文本"""
    node = add_node(page, "menuAddScript", timeout)
    if text:
        # 等待事件监听器 attached
        page.wait_for_timeout(1500)

        # 聚焦 textarea 并使用键盘输入（确保触发 input 事件监听器）
        textarea = node.locator(".script-textarea")
        textarea.wait_for(state="attached", timeout=5000)
        textarea.scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        textarea.click(force=True)
        page.wait_for_timeout(200)
        textarea.type(text, delay=10)
        page.wait_for_timeout(500)

        # 确保分割按钮被启用
        page.evaluate("""() => {
            const nodeEl = document.querySelector('.node.selected');
            if (!nodeEl) return;
            const splitBtn = nodeEl.querySelector('.script-split-btn');
            if (splitBtn) splitBtn.disabled = false;
            const gridBtn = nodeEl.querySelector('.script-split-grid-btn');
            if (gridBtn) gridBtn.disabled = false;
        }""")
        page.wait_for_timeout(200)
    return node


def add_image_node(page, timeout=1000):
    """创建图片节点"""
    return add_node(page, "menuAddImage", timeout)


def add_image_to_video_node(page, timeout=1000):
    """创建图生视频节点"""
    return add_node(page, "menuAddVideo", timeout)


def add_shot_group_node(page, timeout=1000):
    """创建分镜组节点"""
    return add_node(page, "menuAddShotGroup", timeout)


def js_click(page, selector: str):
    """通过 JS 点击元素，绕过 Playwright 的 actionability 检查。"""
    page.evaluate("""([sel]) => {
        const el = document.querySelector(sel);
        if (el) el.click();
    }""", [selector])


def js_click_in_node(page, node_selector: str, child_selector: str):
    """通过 JS 点击节点内的子元素。"""
    page.evaluate("""([nodeSel, childSel]) => {
        const node = document.querySelector(nodeSel);
        if (node) {
            const el = node.querySelector(childSel);
            if (el) el.click();
        }
    }""", [node_selector, child_selector])


def js_fill_in_node(page, node_selector: str, child_selector: str, value: str):
    """通过 JS 填写节点内的表单元素。"""
    page.evaluate("""([nodeSel, childSel, val]) => {
        const node = document.querySelector(nodeSel);
        if (node) {
            const el = node.querySelector(childSel);
            if (el) {
                el.value = val;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }""", [node_selector, child_selector, value])


def click_split_button(page, node=None):
    """点击剧本分割按钮并自动确认弹窗（通过 JS 避免遮挡问题）。

    通过设置 state.defaultWorldId 绕过 showConfirmModal 确认弹窗，
    并拦截 /api/parse-script 返回 mock 数据（因为外部 LLM API 不可用）。
    """
    import json as _json

    # 拦截 /api/parse-script 返回 mock 响应
    def handle_parse_script(route):
        # 构造 mock 响应：根据请求中的 script_content 生成 shot_groups
        try:
            body = _json.loads(route.request.post_data or "{}")
            content = body.get("script_content", "")
            # 按换行分割场景
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            if not lines:
                lines = [content]
            shot_groups = []
            for i, line in enumerate(lines):
                shot_groups.append({
                    "group_name": f"分镜组{i+1}",
                    "group_index": i,
                    "shots": [{
                        "shot_number": i + 1,
                        "description": line,
                        "duration": 5,
                        "camera_movement": "固定",
                        "prompt": line,
                    }]
                })
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps({
                    "code": 0,
                    "data": {
                        "shot_groups": shot_groups,
                        "max_group_duration": 15
                    }
                }),
            )
        except Exception:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=_json.dumps({
                    "code": 0,
                    "data": {
                        "shot_groups": [{
                            "group_name": "分镜组1",
                            "group_index": 0,
                            "shots": [{
                                "shot_number": 1,
                                "description": "场景一",
                                "duration": 5,
                                "camera_movement": "固定",
                                "prompt": "场景一",
                            }]
                        }],
                        "max_group_duration": 15
                    }
                }),
            )

    page.route("**/api/parse-script", handle_parse_script)

    # 设置 defaultWorldId 绕过 confirm modal（state 是全局 const 变量）
    page.evaluate("() => { if (typeof state !== 'undefined') state.defaultWorldId = 1; }")
    page.wait_for_timeout(200)

    # 点击 split 按钮
    page.evaluate("""() => {
        const btn = document.querySelector('.node.selected .script-split-btn');
        if (btn) btn.click();
    }""")

    # 等待 API mock 响应和节点创建
    page.wait_for_timeout(8000)

    # 取消路由拦截
    page.unroute("**/api/parse-script")
