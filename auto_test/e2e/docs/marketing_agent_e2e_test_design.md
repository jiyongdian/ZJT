# 营销智能体 E2E 测试设计文档

## 1. 概述

### 1.1 测试范围

营销智能体页面 (`/marketing-agent`) 是一个 Vue 3 单页应用，提供对话式 AI 营销内容创作能力。本文档覆盖页面所有核心功能的端到端测试设计。

### 1.2 技术约束

| 约束 | 说明 |
|------|------|
| 前端框架 | Vue 3 (CDN)，无构建步骤 |
| 消息输入 | `fill()` + `dispatchEvent('input')` 触发 Vue v-model 更新 |
| 遮挡问题 | `.feedback-fab-container` 需隐藏后才能点击发送按钮 |
| 删除确认 | `window.confirm()` 需通过 `page.on("dialog", lambda d: d.accept())` 处理 |
| 会话菜单 | 非右键菜单，需 hover → 点击 `.history-more-btn` → 点击 `.history-menu-item` |
| API 拦截 | `/api/user/computing_power` 需 mock 防止重定向到登录页 |
| SSE 流 | Agent 消息通过 `EventSource` 流式返回，测试中需 mock 或等待 |
| 认证注入 | `localStorage.setItem('auth_token', ...)` 在 `add_init_script` 中执行 |

### 1.3 已有测试覆盖

| 编号 | 测试名 | 优先级 | 状态 |
|------|--------|--------|------|
| ma_001 | 页面加载 | P0 | 已有 |
| ma_002 | 首页模式切换跳转 | P0 | 已有 |
| ma_003 | API 创建营销会话 | P0 | 已有 |
| ma_004 | 发送消息 | P1 | 已有 |
| ma_005 | 会话列表展示 | P1 | 已有 |
| ma_006 | 会话重命名 | P1 | 已有 |
| ma_007 | 会话删除 | P1 | 已有 |

---

## 2. P0 测试用例（核心功能）

### ma_008 - 新建会话按钮

**目标**：验证点击新建会话按钮后创建新会话并出现在列表顶部

**前置条件**：已登录，页面已加载

**步骤**：
1. 导航到 `/marketing-agent`
2. 等待侧边栏加载完成
3. 记录当前会话数量 `count_before`
4. 点击 `.new-chat-btn`
5. 等待 2 秒

**预期结果**：
- 会话数量增加 1：`count_after == count_before + 1`
- 新会话项出现在列表顶部（第一个 `.sidebar-history-item`）
- 新会话项被标记为 `.active`

**DOM 选择器**：
- `.new-chat-btn` - 新建按钮
- `.sidebar-history-item` - 会话项
- `.sidebar-history-item.active` - 当前活跃会话

---

### ma_009 - 切换会话

**目标**：验证点击不同会话项后主内容区切换到对应会话

**前置条件**：至少有 2 个会话

**步骤**：
1. 导航到 `/marketing-agent`
2. 等待会话列表加载
3. 记录第一个会话的标题 `title_1`
4. 点击第二个会话项 `.sidebar-history-item:nth-child(2)`
5. 等待 1 秒

**预期结果**：
- 第二个会话项变为 `.active`
- 第一个会话项不再 `.active`
- 主内容区更新（欢迎卡片或对应会话的消息）

---

### ma_010 - 发送消息后消息显示

**目标**：验证发送消息后用户消息和 AI 回复都出现在聊天区域

**前置条件**：已登录，页面已加载

**步骤**：
1. 导航到 `/marketing-agent`
2. 输入消息文本（fill + dispatchEvent）
3. 隐藏 `.feedback-fab-container`
4. 点击 `.marketing-send-btn`
5. 等待 5 秒

**预期结果**：
- 出现 `.message.user` 元素，内容包含发送的文本
- 出现 `.message.ai` 元素（AI 回复）
- 输入框被清空

**注意**：AI 回复依赖后端 LLM 服务，如果服务不可用则只验证用户消息

---

### ma_011 - 消息列表滚动

**目标**：验证消息较多时聊天区域可滚动

**前置条件**：会话中有多条消息

**步骤**：
1. 通过 API 追加 5+ 条消息到会话
2. 导航到该会话
3. 验证 `.chat-messages` 容器可滚动

**预期结果**：
- `.chat-messages` 的 `scrollHeight > clientHeight`
- 最新消息可见（容器滚动到底部）

---

## 3. P1 测试用例（重要功能）

### ma_012 - 会话搜索

**目标**：验证搜索框可按关键词过滤会话列表

**前置条件**：至少有 2 个不同名称的会话

**步骤**：
1. 导航到 `/marketing-agent`
2. 等待会话列表加载
3. 在 `.sidebar-search input` 中输入某会话名称的关键词
4. 等待 500ms（Vue 计算属性响应）

**预期结果**：
- 可见的 `.sidebar-history-item` 数量减少
- 所有可见项的 `.history-title` 包含搜索关键词（大小写不敏感）

---

### ma_013 - 创建类型切换（Agent/Image/Video）

**目标**：验证底部输入栏的类型选择器可切换三种创作模式

**前置条件**：已登录，页面已加载

**步骤**：
1. 导航到 `/marketing-agent`
2. 点击 `.marketing-bar-btn` 中的类型选择按钮（第一个）
3. 等待 `.marketing-dropdown-menu` 出现
4. 点击图片模式选项
5. 等待 500ms

**预期结果**：
- 下拉菜单关闭
- 类型按钮图标/文本更新为图片模式
- 设置面板显示图片相关选项（比例、分辨率）

**DOM 选择器**：
- `.marketing-dropdown-menu` - 下拉菜单
- `.marketing-panel` - 设置面板

---

### ma_014 - 设置面板（比例选择）

**目标**：验证 Agent 模式下设置面板可选择不同比例

**前置条件**：已登录，Agent 模式

**步骤**：
1. 导航到 `/marketing-agent`
2. 点击设置按钮打开 `.marketing-panel`
3. 找到比例选项区域
4. 选择一个非默认比例（如 `16:9`）
5. 等待 300ms

**预期结果**：
- 选中的比例项高亮
- `localStorage` 中 `marketing_selected_ratio` 更新
- 底部算力消耗预估可能变化

---

### ma_015 - LLM 模型选择

**目标**：验证 Agent 模式下可切换 LLM 模型

**前置条件**：已登录，Agent 模式

**步骤**：
1. 导航到 `/marketing-agent`
2. 打开模型选择面板
3. 找到 LLM 模型列表
4. 点击一个不同的模型
5. 等待 300ms

**预期结果**：
- 选中的模型项高亮
- `localStorage` 中 `marketing_selected_llm_model_id` 更新
- 模型选择面板关闭

---

### ma_016 - 图片上传（文件选择器）

**目标**：验证通过文件选择器上传图片后显示缩略图

**前置条件**：已登录，Agent 模式，有测试图片文件

**步骤**：
1. 导航到 `/marketing-agent`
2. 找到 `input[type='file']`（通过 `.marketing-upload-btn` 触发）
3. 设置输入文件为测试图片
4. 等待上传完成

**预期结果**：
- 输入区上方出现媒体缩略图条
- 缩略图条中显示已上传的图片预览
- 上传状态从 "uploading" 变为完成

**DOM 选择器**：
- `.marketing-upload-btn` - 上传按钮
- `input[type='file']` - 文件输入
- `.media-thumbnail-bar` / `.media-item` - 缩略图条

---

### ma_017 - 计算力余额显示

**目标**：验证顶部栏显示算力余额

**前置条件**：已登录

**步骤**：
1. 拦截 `/api/user/computing_power` 返回固定值
2. 导航到 `/marketing-agent`
3. 等待页面加载

**预期结果**：
- `.computing-power-display` 可见
- 显示的数值与 mock 返回值一致
- 根据数值有正确的 CSS 类（`low-power` / `medium-power` / `high-power`）

---

### ma_018 - 欢迎卡片显示

**目标**：验证新会话（无消息）显示欢迎卡片

**前置条件**：已登录，新建一个空会话

**步骤**：
1. 通过 API 创建新会话
2. 导航到 `/marketing-agent`
3. 切换到新创建的会话

**预期结果**：
- `.welcome-card` 可见
- 聊天区域无 `.message` 元素
- 输入框可用

---

### ma_019 - 会话标题自动更新

**目标**：验证发送第一条消息后会话标题自动更新

**前置条件**：新建一个空会话

**步骤**：
1. 导航到 `/marketing-agent`
2. 切换到空会话
3. 发送消息 "产品推广方案"
4. 等待 3 秒

**预期结果**：
- 当前会话的 `.history-title` 文本更新
- 新标题与发送的消息内容相关（可能截断）

---

### ma_020 - 反馈弹窗

**目标**：验证点击反馈按钮打开二维码弹窗

**前置条件**：已登录

**步骤**：
1. 导航到 `/marketing-agent`
2. 点击 `.feedback-fab` 按钮
3. 等待弹窗出现

**预期结果**：
- `.feedback-fab-container` 中的弹窗变为可见
- 显示二维码图片
- 点击关闭按钮后弹窗关闭

---

### ma_021 - URL 参数初始消息

**目标**：验证通过 `?initial_message=` 参数可自动发送初始消息

**前置条件**：已登录

**步骤**：
1. 导航到 `/marketing-agent?initial_message=帮我写一个营销方案`
2. 等待页面加载和消息处理

**预期结果**：
- 自动创建新会话
- 消息 "帮我写一个营销方案" 被发送
- 出现 `.message.user` 元素

---

## 4. P2 测试用例（扩展功能）

### ma_022 - 视频上传（带压缩）

**目标**：验证上传超过大小限制的视频时自动压缩

**前置条件**：已登录，Agent 模式，有测试视频文件

**步骤**：
1. 导航到 `/marketing-agent`
2. 通过 file input 上传测试视频
3. 等待压缩和上传

**预期结果**：
- 缩略图条显示视频项
- 状态从 "compressing" 变为 "uploading" 再变为完成
- 上传的视频 URL 可用

---

### ma_023 - @ 引用系统

**目标**：验证输入 `@` 后弹出媒体引用下拉框

**前置条件**：已登录，已上传至少 1 个媒体文件

**步骤**：
1. 导航到 `/marketing-agent`
2. 上传一个图片
3. 在文本框中输入 `@`
4. 等待下拉框出现

**预期结果**：
- 出现 mention 下拉框
- 列表中包含已上传的媒体文件
- 选择后插入引用标签到文本中

---

### ma_024 - 图片模态框

**目标**：验证点击聊天中的图片可打开全屏查看

**前置条件**：会话中有包含图片的 AI 消息

**步骤**：
1. 通过 API 或 UI 使 AI 回复包含图片
2. 点击消息中的图片
3. 等待模态框出现

**预期结果**：
- `#imgModal` 可见
- `#imgModalImg` 显示放大的图片
- 点击关闭按钮或遮罩层关闭模态框

---

### ma_025 - Continue 按钮

**目标**：验证 AI 回复完成后显示继续按钮

**前置条件**：Agent 模式，AI 刚完成一次回复

**步骤**：
1. 发送消息并等待 AI 回复完成
2. 检查是否出现 `.continue-btn`

**预期结果**：
- AI 回复完成后出现 `.continue-btn`
- 点击后触发新一轮 AI 回复

---

### ma_026 - 打字指示器

**目标**：验证 AI 回复过程中显示打字指示器

**前置条件**：Agent 模式，正在等待 AI 回复

**步骤**：
1. 发送消息
2. 在 AI 回复过程中检查 `.typing-indicator`

**预期结果**：
- AI 回复过程中 `.typing-indicator` 可见
- AI 回复完成后 `.typing-indicator` 消失

---

### ma_027 - 会话历史恢复

**目标**：验证切换会话后消息历史正确恢复

**前置条件**：至少 2 个会话，各自有消息

**步骤**：
1. 导航到 `/marketing-agent`
2. 切换到会话 A，记录消息内容
3. 切换到会话 B，验证消息不同
4. 切换回会话 A，验证消息恢复

**预期结果**：
- 每个会话显示各自的消息历史
- 切换后消息内容一致

---

### ma_028 - 保持至少一个会话

**目标**：验证删除最后一个会话时有保护提示

**前置条件**：只剩 1 个会话

**步骤**：
1. 导航到 `/marketing-agent`
2. 删除所有会话直到只剩 1 个
3. 尝试删除最后一个会话

**预期结果**：
- 显示提示信息（不能删除最后一个会话）
- 会话数量保持为 1

---

### ma_029 - 图片生成模式

**目标**：验证切换到图片模式后可直接生成图片

**前置条件**：已登录

**步骤**：
1. 导航到 `/marketing-agent`
2. 切换到图片模式
3. 输入描述文本
4. 点击发送

**预期结果**：
- 调用 `/api/text-to-image` 接口
- 消息区域显示生成状态
- 完成后显示生成的图片

---

### ma_030 - 视频生成模式

**目标**：验证切换到视频模式后可直接生成视频

**前置条件**：已登录

**步骤**：
1. 导航到 `/marketing-agent`
2. 切换到视频模式
3. 输入描述文本
4. 点击发送

**预期结果**：
- 调用 `/api/ai-app-run` 接口
- 消息区域显示生成状态
- 完成后显示生成的视频

---

### ma_031 - 视频时长选择

**目标**：验证视频模式下可选择不同时长

**前置条件**：视频模式

**步骤**：
1. 切换到视频模式
2. 打开设置面板
3. 找到视频时长选项
4. 选择不同时长（如 5 秒、10 秒）

**预期结果**：
- 时长选项可点击且高亮
- 选中后更新 UI 状态

---

### ma_032 - 视频生成方式切换

**目标**：验证视频模式下可切换首尾帧/全能参考

**前置条件**：视频模式，已上传参考图

**步骤**：
1. 切换到视频模式
2. 上传参考图片
3. 找到生成方式选项
4. 切换 "首尾帧" 和 "全能参考"

**预期结果**：
- 两种模式可切换
- UI 提示文案更新

---

### ma_033 - 语言切换

**目标**：验证页面支持中英文切换

**前置条件**：已登录

**步骤**：
1. 导航到 `/marketing-agent`
2. 找到语言切换器（如果存在）
3. 切换到英文
4. 验证 UI 文本变化

**预期结果**：
- 页面标题、按钮文本等切换为英文
- 切换回中文后恢复

---

### ma_034 - 响应式布局（移动端侧边栏）

**目标**：验证窄屏下侧边栏变为抽屉模式

**前置条件**：已登录

**步骤**：
1. 设置 viewport 为 375x667（移动端）
2. 导航到 `/marketing-agent`
3. 验证侧边栏状态
4. 点击汉堡菜单按钮（如果有）

**预期结果**：
- 侧边栏默认隐藏
- 点击按钮后通过 `.sidebar.open` 显示
- 点击遮罩层关闭

---

## 5. API 测试用例

### ma_api_001 - 创建营销会话

**目标**：验证 `POST /api/session/create` 创建 `session_type=2` 会话

```
请求：POST /api/session/create
Body：{ user_id, world_id, auth_token, session_type: 2 }
预期：200/201，响应包含 session_id
```

---

### ma_api_002 - 获取营销会话列表

**目标**：验证 `GET /api/sessions` 按 `session_type=2` 过滤

```
请求：GET /api/sessions?user_id=xxx&world_id=1&session_type=2&limit=50
预期：200，响应为会话列表，所有会话的 session_type=2
```

---

### ma_api_003 - 获取会话历史

**目标**：验证 `GET /api/session/{id}/history` 返回消息列表

```
请求：GET /api/session/{id}/history
Headers：Authorization, X-User-Id
预期：200，响应包含 messages 数组
```

---

### ma_api_004 - 追加消息

**目标**：验证 `POST /api/session/{id}/message` 追加消息

```
请求：POST /api/session/{id}/message
Body：{ role: "user", content: "测试消息" }
预期：200
验证：GET history 后包含该消息
```

---

### ma_api_005 - 更新会话标题

**目标**：验证 `PUT /api/session/{id}/title` 更新标题

```
请求：PUT /api/session/{id}/title
Body：{ title: "新标题" }
预期：200
```

---

### ma_api_006 - 删除会话

**目标**：验证 `DELETE /api/session/{id}` 软删除会话

```
请求：DELETE /api/session/{id}
预期：200
验证：GET sessions 列表中不包含该会话
```

---

### ma_api_007 - 创建 Agent 任务

**目标**：验证 `POST /api/session/{id}/task` 创建任务

```
请求：POST /api/session/{id}/task
Body：{ message: "你好", auth_token: "xxx" }
预期：200，响应包含 task_id
```

---

### ma_api_008 - 图片上传

**目标**：验证 `POST /api/upload-agent-image` 上传图片

```
请求：POST /api/upload-agent-image
Form：file + session_id
预期：200，响应包含图片 URL
```

---

### ma_api_009 - 验证提交

**目标**：验证 `POST /api/verification/{id}` 提交用户回答

```
请求：POST /api/verification/{verification_id}
Body：{ answer: "用户选择" }
预期：200
```

---

## 6. Fixtures 设计

### 6.1 新增 Fixture

```python
# conftest.py 新增

@pytest.fixture
def marketing_session(api_client, auth_token, user_id):
    """创建营销会话（session_type=2），测试后清理"""
    worlds = get_worlds_list(api_client)
    world_id = worlds[0]["id"] if worlds else "1"

    resp = api_client.post(
        "/api/session/create",
        json={
            "user_id": str(user_id),
            "world_id": str(world_id),
            "auth_token": auth_token,
            "session_type": 2,
        },
    )
    if resp.status_code not in (200, 201):
        pytest.fail(f"创建营销会话失败: {resp.status_code} {resp.text}")
    data = resp.json()
    sid = (
        data.get("session_id")
        or data.get("id")
        or data.get("data", {}).get("session_id")
    )
    yield {"id": sid, "data": data}
    try:
        api_client.delete(f"/api/session/{sid}")
    except Exception:
        pass
```

### 6.2 Page Object 扩展

```python
class MarketingAgentPage(BasePage):
    """营销智能体页面"""

    def navigate(self):
        super().navigate("/marketing-agent")

    def is_loaded(self) -> bool:
        return self.is_element_visible("body", timeout=10000)

    def has_sidebar(self) -> bool:
        return self.is_element_visible(".sidebar", timeout=5000)

    def has_input_area(self) -> bool:
        return self.is_element_visible(".marketing-textarea", timeout=5000)

    def wait_for_sidebar_loaded(self):
        """等待侧边栏会话列表加载"""
        self.page.wait_for_selector(".sidebar-history-item, .new-chat-btn", timeout=10000)

    def send_message(self, text: str):
        """发送消息（处理 Vue v-model 和遮挡问题）"""
        textarea = self.page.locator(".marketing-textarea").first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.click()
        self.page.wait_for_timeout(200)
        textarea.fill(text)
        self.page.evaluate("""() => {
            const ta = document.querySelector('.marketing-textarea');
            if (ta) ta.dispatchEvent(new Event('input', { bubbles: true }));
        }""")
        self.page.wait_for_timeout(300)
        # 隐藏 feedback-fab 避免遮挡
        self.page.evaluate("""() => {
            const fab = document.querySelector('.feedback-fab-container');
            if (fab) fab.style.display = 'none';
        }""")
        self.page.locator(".marketing-send-btn").first.click()

    def get_session_count(self) -> int:
        """获取侧边栏会话数量"""
        return self.page.locator(".sidebar-history-item").count()

    def click_new_chat(self):
        """点击新建会话按钮"""
        self.page.locator(".new-chat-btn").first.click()
        self.page.wait_for_timeout(1000)

    def switch_session(self, index: int):
        """切换到指定索引的会话"""
        self.page.locator(".sidebar-history-item").nth(index).click()
        self.page.wait_for_timeout(1000)
```

---

## 7. 测试文件结构

```
auto_test/e2e/
├── test_marketing_agent.py          # UI 测试（扩展现有文件）
├── test_marketing_agent_api.py      # API 测试（新建）
├── helpers/
│   └── page_objects.py              # MarketingAgentPage 扩展
└── conftest.py                      # 新增 marketing_session fixture
```

---

## 8. 执行策略

### 8.1 标记

```python
pytest.mark.marketing_agent    # 所有营销智能体测试
pytest.mark.p0                 # P0 核心测试
pytest.mark.p1                 # P1 重要测试
pytest.mark.p2                 # P2 扩展测试
```

### 8.2 执行命令

```bash
# 仅 P0
python -m pytest auto_test/e2e/test_marketing_agent.py -m "marketing_agent and p0" -v --timeout=120

# 全部营销智能体测试
python -m pytest auto_test/e2e/test_marketing_agent.py -m marketing_agent -v --timeout=120

# 包含 API 测试
python -m pytest auto_test/e2e/test_marketing_agent.py auto_test/e2e/test_marketing_agent_api.py -m marketing_agent -v --timeout=120
```

### 8.3 预估用例数

| 优先级 | 数量 | 预估耗时 |
|--------|------|----------|
| P0 | 4 (已有) + 4 (新增) = 8 | ~60s |
| P1 | 3 (已有) + 9 (新增) = 12 | ~120s |
| P2 | 0 + 13 (新增) = 13 | ~180s |
| API | 0 + 9 (新增) = 9 | ~30s |
| **合计** | **42** | **~390s (~6.5min)** |

---

## 9. Mock 策略

| API | Mock 方式 | 说明 |
|-----|-----------|------|
| `/api/user/computing_power` | `page.route()` | 返回固定算力值，防止重定向 |
| `/api/task/{id}/stream` | `page.route()` 或 SSE mock | Agent 模式测试需要模拟流式响应 |
| `/api/system/server-config` | `page.route()` | 返回固定配置 |
| `/api/models` | `page.route()` | 返回固定的模型列表 |
| `/api/text-to-image` | `page.route()` | 图片生成模式测试 |
| `/api/ai-app-run` | `page.route()` | 视频生成模式测试 |

### 9.1 SSE Mock 示例

```python
def mock_sse_stream(route):
    """模拟 Agent SSE 流式响应"""
    body = "event: message\ndata: {\"content\": \"测试回复\"}\n\n"
    body += "event: done\ndata: {}\n\n"
    route.fulfill(
        status=200,
        content_type="text/event-stream",
        body=body,
    )

page.route("**/api/task/*/stream", mock_sse_stream)
```
