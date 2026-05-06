# 营销模式（Marketing Mode）

## 概述

营销模式是面向营销内容创作场景的全新交互模式，与短剧模式并列为系统的两大创作模式。该模式提供营销智能体（Marketing Agent）对话式创作能力，可帮助用户生成带货脚本、广告创意、产品文案等营销内容。

## 模式入口

### 模式切换

用户首次进入系统时，会弹出"选择创作模式"弹窗，可在以下两种模式中选择：

- 🎬 **短剧模式**：适用于 AI 短剧创作，包含剧本、角色、场景、视频生成全流程
- 🎯 **营销模式**：适用于营销内容创作，包含带货脚本、广告创意、产品文案等全流程

模式选择后保存在 `localStorage` 的 `creation_mode` 字段中（值为 `short_drama` 或 `marketing`）。用户可在首页顶部"切换模式"按钮重新选择。

### 实现位置

- 模式选择弹窗：`web/index.html`，约第 630-660 行
- 模式切换方法：`web/index.html` 中 `selectCreationMode(mode)` 方法

## 页面结构

### 营销首页（`/`）

营销模式首页通过 `web/index.html` 中的 `ListPage` 组件根据 `creationMode` 动态渲染。营销模式分支位于约第 810 行起的 `<template v-if="$root.creationMode === 'marketing'">` 块中。

页面包含以下区块：

| 区块 | 说明 |
|------|------|
| 左侧导航 | 灵感、生成、资产、画布（纯 UI 展示，未实现跳转） |
| 大标题 | "开启你的 Agent 模式 即刻造梦！" |
| 中央输入区 | 文本输入框 + 上传按钮 + 功能按钮条 |
| 创作类型 | Agent 模式 / 图片生成 / 视频生成（纯 UI 展示） |
| 功能卡片 | 无限画布、Agent 模式、图片生成、视频生成（纯 UI 展示） |

输入框中输入内容并点击发送（或按 Enter）后，会跳转至 `/marketing-agent` 对话界面，并通过 URL 参数 `initial_message` 传递初始消息。

样式定义：`web/css/index.css` 末尾的"营销模式首页样式"区块（`.marketing-*` 类前缀）。

### 营销智能体对话页面（`/marketing-agent`）

营销智能体对话界面位于 `web/marketing_agent.html`，使用 Vue 3 单文件应用实现。页面布局参考"营销智能体参考图/智能体对话.png"。

#### 页面布局

| 区块 | 说明 |
|------|------|
| 左侧边栏 | 新对话按钮、搜索框、默认创作、最近对话列表、用户信息 |
| 顶部栏 | 当前日期、搜索框、时间/生成类型/操作类型筛选器 |
| 消息流 | 欢迎卡片 + 用户/AI 消息气泡，支持 Markdown 渲染 |
| 底部输入区 | 文本输入框 + 上传/技能/添加主体按钮 + 发送按钮 |

#### 后端路由

由 `server.py` 中的 `serve_marketing_agent` 函数（约第 8077-8083 行）服务静态 HTML：

```python
@app.get("/marketing-agent")
async def serve_marketing_agent():
    file_path = os.path.join(static_dir, "marketing_agent.html")
    if os.path.isfile(file_path):
        content = _get_processed_html(file_path)
        return Response(content=content, media_type="text/html")
    raise HTTPException(status_code=404, detail="Marketing agent page not found")
```

#### 接口复用

营销智能体的对话能力**复用 `script_writer` 的现有接口**，无需新增后端 API：

| 用途 | 接口 | 方法 |
|------|------|------|
| 创建会话 | `/api/session/create` | POST |
| 发送消息 | `/api/session/{session_id}/task` | POST |
| 接收流式响应 | `/api/task/{task_id}/stream` | GET (SSE) |
| 加载历史 | `/api/session/{session_id}/history` | GET |
| 获取/创建世界 | `/api/worlds` | GET / POST |

页面初始化流程：
1. 从 URL 参数获取 `user_id`，从 `localStorage` 获取 `auth_token`
2. 调用 `GET /api/worlds` 获取用户的世界列表
3. 若用户没有世界，自动调用 `POST /api/worlds` 创建"营销世界"
4. 调用 `POST /api/session/create` 创建新会话
5. 若 URL 中有 `initial_message` 参数，自动发送首条消息

## 样式与主题

营销模式采用**浅色主题**（白底蓝调），与短剧模式的深色主题形成视觉区分。

### 主题色变量

定义于 `web/css/marketing_agent.css` 顶部 `:root` 中：

```css
--bg-primary: #f5f5f5;       /* 主背景 */
--bg-secondary: #ffffff;     /* 卡片/输入框背景 */
--accent-color: #00a8e6;     /* 主题色（亮蓝） */
--text-primary: #1a1a1a;     /* 主文本 */
--text-secondary: #666666;   /* 次要文本 */
--text-muted: #999999;       /* 弱化文本 */
--border-color: #e8e8e8;     /* 边框 */
```

## 文件清单

| 文件路径 | 类型 | 说明 |
|----------|------|------|
| `web/index.html` | 修改 | 模式选择器（电商模式→营销模式）、ListPage 动态渲染分支 |
| `web/css/index.css` | 修改 | 末尾追加"营销模式首页样式"区块 |
| `web/marketing_agent.html` | 新建 | 营销智能体对话页面（Vue 3） |
| `web/css/marketing_agent.css` | 新建 | 对话页面样式（浅色主题） |
| `server.py` | 修改 | 新增 `/marketing-agent` 路由 |

## 本地存储键

| 键名 | 用途 |
|------|------|
| `creation_mode` | 当前选择的创作模式（`short_drama` / `marketing`） |
| `marketing_sessions` | 营销模式本地会话历史缓存 |

## 后续可扩展点

1. **左侧导航功能**：当前左侧"灵感、生成、资产、画布"和"无限画布、Agent 模式、图片生成、视频生成"功能卡片为纯 UI 展示，可逐步实现实际页面跳转。
2. **筛选器联动**：顶部"时间、生成类型、操作类型"筛选器目前仅有 UI，可结合后端实现历史记录筛选。
3. **营销技能库**：可在 `script_writer_core/skills/` 下新增营销专用 skill（如 `marketing-script-writer`、`product-copy-writer`），并通过 `system_prompt` 切换使营销 Agent 拥有专属能力。
4. **营销专用世界**：当前自动创建"营销世界"，未来可根据营销主题（如"美妆"、"3C数码"）创建多个细分世界。
