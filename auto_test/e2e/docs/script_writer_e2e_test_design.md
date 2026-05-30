# 剧本编辑器 E2E 测试设计文档

## 1. 概述

### 1.1 测试范围

剧本编辑器页面 (`/script-writer`) 是一个 Vue 3 + 原生 JS 单页应用，提供 AI 辅助剧本创作能力。本文档覆盖页面核心功能的端到端测试设计。

### 1.2 技术约束

| 约束 | 说明 |
|------|------|
| URL 参数 | 必须携带 `user_id` 和 `world_id`，否则重定向或显示世界选择提示 |
| 认证注入 | `localStorage.setItem('auth_token', ...)` 在 `add_init_script` 中执行 |
| 消息输入 | `#message-input` textarea，Enter 发送，Shift+Enter 换行 |
| SSE 流 | Agent 消息通过 `EventSource` 流式返回 |
| 文件侧边栏 | 右侧 5 个 tab：worlds/characters/scripts/locations/props |
| 模态框 | 新建世界/剧本/角色/场景/道具、编辑、查看、导入脚本等多个模态框 |
| 算力拦截 | `/api/user/computing_power` 需 mock 防止重定向 |

### 1.3 页面初始化依赖

页面加载时需要以下 URL 参数：
- `user_id` (必需，缺失则重定向到 `/video-workflow-list`)
- `world_id` (可选，缺失则显示世界选择提示并禁用输入)
- `workflow_id` (可选，用于跳转到工作流画布)

---

## 2. P0 测试用例（核心功能）

### sw_001 - 页面加载

**目标**：验证携带正确 URL 参数后页面加载成功

**步骤**：
1. 注入 localStorage 认证信息
2. 导航到 `/script-writer?user_id={uid}&world_id={wid}`
3. 等待页面加载

**预期结果**：
- 页面 body 可见
- `.app-container` 存在
- `.chat-area` 存在

---

### sw_002 - 无 world_id 时显示世界选择提示

**目标**：验证不带 world_id 时页面显示世界选择提示

**步骤**：
1. 导航到 `/script-writer?user_id={uid}`（无 world_id）
2. 等待页面加载

**预期结果**：
- 世界选择侧边栏自动打开（`.world-sidebar.open` 或 overlay 可见）
- 聊天区域显示世界选择提示

---

### sw_003 - 世界侧边栏开关

**目标**：验证汉堡按钮可打开/关闭世界选择侧边栏

**步骤**：
1. 导航到完整 URL
2. 点击 `.hamburger-btn`
3. 等待侧边栏打开
4. 点击 `.world-close-btn` 或遮罩层关闭

**预期结果**：
- 点击后 `.world-sidebar` 变为 `.world-sidebar.open`
- 遮罩层 `.world-sidebar-overlay` 变为 `.active`
- 关闭后恢复

---

### sw_004 - 会话自动创建

**目标**：验证页面加载后自动创建或复用会话

**步骤**：
1. 导航到完整 URL
2. 等待页面加载完成

**预期结果**：
- `#session-id` 显示会话 ID
- 输入框可用

---

### sw_005 - 发送消息

**目标**：验证发送消息后用户消息出现在聊天区域

**步骤**：
1. 导航到完整 URL
2. 在 `#message-input` 输入文本
3. 点击 `#send-btn`
4. 等待 3 秒

**预期结果**：
- 出现 `.message.user-message` 元素
- 消息内容包含发送的文本
- 输入框被清空

---

### sw_006 - 需求选择器显示

**目标**：验证新会话时显示需求选择按钮

**步骤**：
1. 导航到完整 URL
2. 等待页面加载

**预期结果**：
- `#requirement-selector` 可见
- 有 4 个 `.requirement-btn` 按钮

---

### sw_007 - 需求选择 - 新建剧本

**目标**：点击"剧本新建"按钮后输入框填入默认文本

**步骤**：
1. 导航到完整 URL
2. 点击第 3 个 `.requirement-btn`（剧本新建）

**预期结果**：
- `#message-input` 包含"新建"相关文本
- 输入框获得焦点

---

### sw_008 - 模型选择器加载

**目标**：验证 LLM 模型选择器加载完成

**步骤**：
1. 导航到完整 URL
2. 等待模型加载

**预期结果**：
- `#model-selector` 有多个 `<option>`
- 有一个默认选中的模型

---

### sw_009 - 算力余额显示

**目标**：验证顶部栏显示算力余额

**步骤**：
1. Mock `/api/user/computing_power` 返回固定值
2. 导航到完整 URL

**预期结果**：
- `#power-value` 显示数值
- `.computing-power-display` 可见

---

### sw_010 - 文件侧边栏加载

**目标**：验证右侧文件侧边栏加载完成

**步骤**：
1. 导航到完整 URL
2. 等待文件加载

**预期结果**：
- `.file-sidebar` 存在
- `.file-tabs` 有 5 个 tab 按钮
- 默认显示 worlds tab

---

## 3. P1 测试用例（重要功能）

### sw_011 - 文件 Tab 切换

**目标**：验证点击不同 tab 切换文件列表

**步骤**：
1. 导航到完整 URL
2. 点击 "characters" tab
3. 等待加载
4. 点击 "scripts" tab

**预期结果**：
- 每次切换后 `.tab-btn.active` 更新
- 文件列表内容变化

---

### sw_012 - 聊天区域可滚动

**目标**：验证有消息时聊天区域可滚动

**步骤**：
1. 导航到完整 URL
2. 发送多条消息

**预期结果**：
- `.chat-messages` 容器存在
- 有消息时 scrollHeight > 0

---

### sw_013 - Enter 发送消息

**目标**：验证在输入框按 Enter 键发送消息

**步骤**：
1. 导航到完整 URL
2. 在 `#message-input` 输入文本
3. 按 Enter 键

**预期结果**：
- 消息被发送（出现 `.message.user-message`）

---

### sw_014 - Agent 轮播图

**目标**：验证欢迎卡片上的 Agent 轮播图可切换

**步骤**：
1. 导航到完整 URL（新会话）
2. 点击 `#carousel-next`
3. 点击 `#carousel-prev`

**预期结果**：
- 轮播图切换（`.carousel-slide.active` 变化）
- 指示器更新

---

### sw_015 - 压缩历史按钮

**目标**：验证压缩历史按钮可点击

**步骤**：
1. 导航到完整 URL
2. 找到 `.chat-compress-btn`
3. 点击（会弹出 confirm 对话框）

**预期结果**：
- 按钮存在且可点击
- 弹出确认对话框

---

### sw_016 - 刷新/新建会话按钮

**目标**：验证刷新按钮存在

**步骤**：
1. 导航到完整 URL
2. 找到 `.chat-refresh-btn`

**预期结果**：
- 按钮存在且可见

---

### sw_017 - 提交数据按钮

**目标**：验证提交数据按钮存在

**步骤**：
1. 导航到完整 URL
2. 找到提交数据按钮

**预期结果**：
- `.header-action-btn.primary` 存在
- 按钮文本包含"提交数据"

---

### sw_018 - 自动提交开关

**目标**：验证自动提交开关可切换

**步骤**：
1. 导航到完整 URL
2. 找到 `#auto-submit-switch`
3. 点击切换

**预期结果**：
- 开关存在
- 点击后状态变化

---

### sw_019 - 新建世界模态框

**目标**：验证点击新建世界按钮打开模态框

**步骤**：
1. 打开世界侧边栏
2. 点击 `.world-add-btn`
3. 等待模态框出现

**预期结果**：
- `#new-world-modal` 可见
- 包含名称和描述输入框

---

### sw_020 - 导航栏项目

**目标**：验证左侧导航栏显示

**步骤**：
1. 导航到完整 URL

**预期结果**：
- `#step-nav` 存在
- 有 "剧本资产" 和 "制作工坊" 两个导航项

---

### sw_021 - 面包屑导航

**目标**：验证顶部面包屑导航显示

**步骤**：
1. 导航到完整 URL

**预期结果**：
- `.breadcrumb-nav` 存在
- 包含"工作流列表"链接和"剧本智能创作系统"

---

### sw_022 - 世界名称显示

**目标**：验证 header 显示当前世界名称

**步骤**：
1. 导航到完整 URL（带 world_id）

**预期结果**：
- `#world-name-display` 显示世界名称（非"加载中"）

---

## 4. P2 测试用例（扩展功能）

### sw_023 - i18n 语言切换

**目标**：验证语言切换按钮存在

**步骤**：
1. 导航到完整 URL
2. 检查 `#i18n-switcher-container`

**预期结果**：
- 容器存在且有子元素

---

### sw_024 - 新建剧本模态框

**目标**：验证 FAB 按钮打开新建剧本模态框

**步骤**：
1. 切换到 scripts tab
2. 点击 `#add-file-btn`

**预期结果**：
- `#new-script-modal` 可见

---

### sw_025 - 导入脚本模态框

**目标**：验证需求选择器的"导入已有剧本"打开导入模态框

**步骤**：
1. 点击第 1 个 `.requirement-btn`

**预期结果**：
- `#import-script-modal` 可见
- 包含 drop zone 和 textarea

---

### sw_026 - 反馈弹窗

**目标**：验证反馈按钮打开二维码弹窗

**步骤**：
1. 点击 `.feedback-fab`
2. 等待弹窗

**预期结果**：
- `#feedback-modal` 可见

---

### sw_027 - 新建角色模态框

**目标**：验证新建角色模态框可打开

**步骤**：
1. 通过 JS 调用 `showNewCharacterModal()` 或找到触发按钮

**预期结果**：
- `#new-character-modal` 可见
- 包含名称、年龄等输入框

---

### sw_028 - 新建场景模态框

**目标**：验证新建场景模态框可打开

**步骤**：
1. 通过 JS 调用 `showNewLocationModal()`

**预期结果**：
- `#new-location-modal` 可见

---

### sw_029 - 新建道具模态框

**目标**：验证新建道具模态框可打开

**步骤**：
1. 通过 JS 调用 `showNewPropModal()`

**预期结果**：
- `#new-prop-modal` 可见

---

### sw_030 - 响应式布局

**目标**：验证窄屏下页面仍可用

**步骤**：
1. 设置 viewport 为 375x667
2. 导航到完整 URL

**预期结果**：
- 页面加载成功
- 核心元素存在

---

## 5. API 测试用例

### sw_api_001 - 获取剧本文件列表

```
GET /api/scripts-files?user_id=&world_id=&auth_token=&raw_json=true
预期：200，返回文件列表
```

### sw_api_002 - 获取角色文件列表

```
GET /api/characters-files?user_id=&world_id=&auth_token=&raw_json=true
预期：200，返回文件列表
```

### sw_api_003 - 获取场景文件列表

```
GET /api/locations-files?user_id=&world_id=&auth_token=&raw_json=true
预期：200，返回文件列表
```

### sw_api_004 - 获取道具文件列表

```
GET /api/props-files?user_id=&world_id=&auth_token=&raw_json=true
预期：200，返回文件列表
```

### sw_api_005 - 获取世界文件列表

```
GET /api/worlds-files?user_id=&world_id=&auth_token=&raw_json=true
预期：200，返回文件列表
```

### sw_api_006 - 同步文件

```
POST /api/sync-files
Body: { user_id, world_id, auth_token }
预期：200
```

### sw_api_007 - 提交数据到数据库

```
POST /api/submit-to-database
Body: { user_id, world_id, auth_token }
预期：200
```

### sw_api_008 - 获取模型列表

```
GET /api/models
Headers: Authorization
预期：200，返回模型列表
```

### sw_api_009 - 获取供应商列表

```
GET /api/vendors
预期：200，返回供应商列表
```

---

## 6. 关键文件

- `web/script_writer.html` - 页面主体（7065 行，含内联 JS）
- `web/css/script_writer.css` - 样式
- `web/js/task_config.js` - 任务配置模块
- `auto_test/e2e/test_script_writer.py` - 测试文件
- `auto_test/e2e/helpers/page_objects.py` - ScriptWriterPage
- `auto_test/e2e/conftest.py` - Fixtures

---

## 7. 执行策略

```bash
# 仅 P0
python -m pytest auto_test/e2e/test_script_writer.py -m "script_writer and p0" -v --timeout=120

# 全部
python -m pytest auto_test/e2e/test_script_writer.py -m script_writer -v --timeout=120

# 包含 API
python -m pytest auto_test/e2e/test_script_writer.py auto_test/e2e/test_script_writer_api.py -m script_writer -v --timeout=120
```

### 预估用例数

| 优先级 | 数量 | 预估耗时 |
|--------|------|----------|
| P0 | 10 | ~60s |
| P1 | 12 | ~90s |
| P2 | 8 | ~60s |
| API | 9 | ~20s |
| **合计** | **39** | **~230s (~4min)** |
