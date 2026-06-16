# 数字人节点：算力显示 + 抽卡功能

- 日期：2026-06-14
- 涉及文件：`web/js/digital_human_node.js`、`web/i18n/locales/{zh-CN,en}/video_workflow.json`
- 范围：**纯前端改动**，后端无需任何改动

## 背景

数字人节点（`web/js/digital_human_node.js`）原先：
- 不显示算力
- 抽卡次数固定为 1（`form.append('count', 1)`）
- 节点内显示单个结果视频（`.dh-result-video`）
- 只创建一个关联视频节点，用局部 `pollVideoStatus`（封装单个 `pollTaskStatus`）轮询

需求：显示算力 + 支持用户抽卡（1-4 个结果）。

## 前提（已验证，后端无需改动）

- `/api/ai-app-run-image`（server.py:1874）已支持 `count: int = Form(1, ge=1, le=4)`，`for i in range(count)` 循环创建任务，返回 `project_ids` 数组，按 count 扣算力。
- `/api/system/task-configs` 已为数字人任务返回 `computing_power`（当前 `digital_human` / `digital_human_ltx2_3_voice` 均为 12，可被管理员在数据库动态覆盖）。
- `checkVideoStatus`（api.js:189）返回的 `result.tasks` 每个 task 带 `project_id`，多结果可精确对应。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 算力显示样式 | 详细版（值 + 明细行） | 与视频节点/分镜节点视觉一致 |
| 抽卡次数范围 | 1-4 | 与现有视频节点一致 |
| 节点内结果展示 | **不显示** | 与视频/分镜节点一致，结果全部在关联视频节点展示 |
| modelKey 取值 | 优先 `digital_human_ltx2_3_voice`，回退 `digital_human` | 与现有提交逻辑一致 |
| duration | 固定 5 | 与现有提交逻辑一致 |
| 多结果轮询 | 全局 `pollVideoStatus(projectIds, ...)` | 支持多 project，带 `onTaskUpdate` 实时反馈 |
| 多结果对应 | 按 `project_id` | 比按 index 稳健 |

## 实现要点

### UI 结构（bodyHtml）

```
角色图片 *  → [上传/连接]
说话音频 *  → [上传/连接]
提示词 *    → [textarea]
─────────────────────
算力消耗：    N 算力        （新增，详细版）
单个 X 算力 × M 个 = N 算力
─────────────────────
[生成视频 ▾]  抽卡次数：XM   （改为抽卡选择器）
[状态显示：生成中/成功/失败]   （保留）
```

移除节点内的"生成结果"视频区域（`.dh-result-field` / `.dh-result-video`）。

### 数据（defaultData）

- 新增 `drawCount: 1`
- `status` 保留
- 移除节点内 `videoUrl` 渲染（data 字段保留以兼容旧工作流）

### 算力计算

```js
function calculateDigitalHumanPower() {
  if (!window.TaskConfig || !window.TaskConfig.isLoaded()) return 0;
  var modelKey = TaskConfig.getTaskByKey('digital_human_ltx2_3_voice') ? 'digital_human_ltx2_3_voice' : 'digital_human';
  var single = TaskConfig.getComputingPower(modelKey, 5);
  return single * (node.data.drawCount || 1);
}
```

`updateDigitalHumanPowerDisplay()` 更新值 + 明细行。切换抽卡次数时立即更新；`TaskConfig.onLoaded()` 兜底异步加载后更新。

### 抽卡选择器（复用现有 CSS）

`gen-container` + `gen-btn-main`（生成）+ `gen-btn-caret`（▾）+ `gen-menu`（X1/X2/X3/X4）。事件处理与视频节点（nodes.js:4160-4182）一致：caret 切换菜单 / item 设 `drawCount`+更新 / document 点外关闭。

### 提交与多结果展示

- `form.append('count', node.data.drawCount || 1)`
- 后端返回 `project_ids` 数组 → 循环创建对应数量视频节点：
  - 纵向排列（`y = node.y + i*260`）
  - 每个绑定 `project_ids[i]`，命名 `数字人视频N`（单个时为 `数字人视频`）
  - 每个创建连接 `from = 数字人节点`
- `node.data._linkedVideoNodeIds = [...]` 跟踪多个关联节点（替代单个 `_linkedVideoNodeId`）
- 重新生成：先清理所有旧关联节点的连接

### 轮询改造

移除局部 `pollVideoStatus`，改用全局 `pollVideoStatus(projectIds, onProgress, onComplete, onError, onTaskUpdate)`（workflow.js:294）：
- `onTaskUpdate(tasks)`：按 `project_id` 找到对应视频节点更新状态/结果（实时）
- `onComplete(result)`：按各自 `status` 更新视频节点 url；刷新用户算力；恢复按钮
- `onError`/超时：标记状态，恢复按钮

### 重新加载复原（CLAUDE.md 第 4 条）

- `drawCount` 从 data 恢复 → 算力显示正确
- 关联视频节点 + 连接 + `project_id` 通过 `state.connections` / 节点 data 自动恢复
- 节点内状态恢复显示

## 错误处理

- TaskConfig 未加载：算力先显示 0，加载后回调更新（非阻塞）
- `project_ids` 为空：报错（保留现有逻辑）
- 部分任务失败：`onComplete` 内按各自状态更新（失败的标记失败，成功的正常显示）

## 不做的事（YAGNI）

- 不改后端 / 不加接口 / 不动数据库 / 不改 alembic
- 不改 `video_workflow.html`（JS 独立文件，符合 CLAUDE.md 第 3 条）
- 抽卡范围固定 1-4

## 验证

1. 新建节点 → 算力显示（如 12）；切 X4 → 算力变 48
2. 生成 4 个 → 创建 4 个关联视频节点，各自轮询出结果
3. 重新生成 → 清理旧 4 个、创建新的
4. 保存→重载 → drawCount / 算力 / 关联节点连接均复原
5. 中英文切换 → 翻译正常
6. 兼容旧工作流（无 drawCount 的旧节点默认 X1）
