# 分镜组增量同步与字段继承

## 背景

此前向分镜组添加分镜非常繁琐：用户必须「删掉分镜组下所有已生成分镜节点 → 在编辑框新增分镜并手填十几项字段 → 点『生成分镜』重建所有节点」。

根因（均在 `web/js/nodes.js`）：
1. `generateShotFramesIndependent` / `generateShotFramesIndependentAsync` 的**去重跳过逻辑**：已存在的 `shot_id` 直接跳过、不更新。
2. 新节点**位置追加**到末尾，在分镜列表中间插入会导致顺序错乱。
3. `addNewShot` 创建的分镜大多字段为空，需手填。

本次改动（纯前端，集中在 `web/js/nodes.js`）解决上述两点。

## 改动 1：字段继承（addNewShot）

新增分镜时自动从相邻分镜（优先插入位置的上一个，否则下一个）继承共性字段，减少手填。

- **继承**（同一分镜组通常一致）：`duration`、`location_id`、`db_location_id`、`db_location_pic`、`location_name`、`time_of_day`、`weather`、`mood`、`environment_sound`、`background_music`、`shot_type`、`camera_movement`。
- **不继承**（每个分镜独有，留空）：`description`、`opening_frame_description`、`scene_detail`、`action`、`characters_present`、`dialogue`、`props`、`audio_notes`。
- `shot_id`：新生成 `s${Date.now()}`；`shot_number`：由 `renumberShots` 自动重算。

## 改动 2：增量同步（generateShotFramesIndependent / Async）

两个生成函数改为调用共用核心 `syncShotFramesToShots(shotGroupNodeId, shotGroupNode, { isAsync })`，行为：

1. 建立 `shot_id → shot_frame 节点` 映射。
2. 遍历 shots（按 `shot_number` 排序）：
   - 已有节点 → **就地更新基础信息**（`updateShotFrameNodeBasic`）。
   - 无节点 → 新建 `shot_frame`。
3. 按 shots 顺序重排所有关联节点的 y 坐标（x 固定为分镜组右侧 1200px）。
4. 孤儿节点（列表中已删除但画布节点仍在）**保留不删除**，移到末尾并 toast 提示。

**就地更新（保守同步）** —— `updateShotFrameNodeBasic(shotFrameNode, shot)`：
- 更新：`description`、`duration`、`shotType`、`cameraMovement`、`shotJson` 快照。
- **保留**：`imageUrl`、`generatedImage`、`previewImageUrl`、`videoMode`、`model`、`drawCount`、`videoDrawCount`、`videoDuration`、`videoModel`，以及用户手动编辑的 `imagePrompt`、`videoPrompt`、`videoPromptText`。
- 仅改对应 DOM 元素的 `textContent`，不重建节点 DOM（避免破坏事件绑定与生成结果展示）。

## 关键函数

| 函数 | 说明 |
|------|------|
| `addNewShot(insertIndex)` | 新增分镜，从相邻分镜继承共性字段 |
| `syncShotFramesToShots(nodeId, node, {isAsync})` | 增量同步核心（新建/更新/重排/孤儿保留） |
| `updateShotFrameNodeBasic(node, shot)` | 就地更新已有节点基础信息（保守，保留生成结果） |
| `generateShotFramesIndependent(...)` | 同步包装器（`isAsync:false`） |
| `generateShotFramesIndependentAsync(...)` | 异步包装器（`isAsync:true`），返回新建节点 id 列表 |

`createShotFrameNode` 基础信息显示区新增 `shot-frame-desc-display` / `shot-frame-meta` class，供就地更新时定位。

## 注意

- 不影响工作流重新加载（reload）：节点数据结构未变，仍是标准 `shot_frame`。
- `generateShotFramesIndependentAsync` 用于剧本解析后自动批量生成，首次全为新建，行为不变。
- 宫格生图流程依赖 `generateShotFramesIndependentAsync` 返回的新建节点 id 列表，已保留。

## 后续修复（形状坍塌 / 名称重名 / 按钮提醒）

实施后用户反馈三个问题，已修复：

### 1. 分镜组形状坍塌（横向 3 列 → 纵向）

**根因**：`updateShotGroupNodeDisplay` 重建 node-body 时丢失了 `.script-node-body` 容器，CSS `.node:has(.script-node-body)`（`video_workflow.css`，横向 3 列布局）失效，退化为默认纵向。

**修复**：`updateShotGroupNodeDisplay` 改为**局部更新**——只刷新 `.shot-group-shots-list`（分镜列表）和 `.shot-group-shot-count`（计数），保留 `createShotGroupNode` 的原始 DOM 结构、事件与 select 状态。同时在 `createShotGroupNode` 第1列补上 `.shot-group-model`（分镜模型）下拉框 + 初始化 + change 事件，消除"创建时无、保存后才出现"的历史不一致。

### 2. 分镜名称错乱/重名

**根因**：`createShotFrameNode` 的 title 计算有运算符优先级 bug（`shot_id || shot_number ? A : B` 实际解析为 `shot_id || (shot_number ? A : B)`），shot_id 存在时 title 直接 = shot_id（显示 `s1781446xxx`）；且 `updateShotFrameNodeBasic` 不更新 title，`renumberShots` 重排 shot_number 后已有节点标题不同步 → 与新节点重名。

**修复**：
- `createShotFrameNode` title 改为优先 shot_number：`shot_number ? 镜头N : (shot_id || 分镜图)`。
- `updateShotFrameNodeBasic` 同步更新 title 与 `.node-title` DOM（保留 svg 图标，只更新文本 + `data-i18n-params`）。

### 3. 新增分镜 shot_id 简化（base_x 命名）

`s${Date.now()}`（如 `s1781446xxx`）太长。`addNewShot` 改为基于**插入位置的前一个分镜**生成简短且唯一的 shot_id：

- 在分镜 `N` 后插入 → `N_1`。
- 再在 `N_x` 后插入 → `N_{该组所有 N_x 的最大序号 + 1}`。
- `base` 取自前一个分镜：基础分镜 → 用其 `shot_number`；`N_M` 插入分镜 → 用 `N`。
- 插在最前（无前一个）→ `0_1`、`0_2`...

示例：分镜组有 1、2、3 → 在 2 后插 → `2_1` → 在 `2_1` 后插 → 该组 `2_x` 有 {2_1} → `2_2`。

### 4. 生成分镜按钮闪烁提醒

`saveShotGroupEdit` 在局部更新后，给画布上该分镜组的 `.shot-group-generate-btn` 加 `.flashing` class（CSS `shot-group-generate-flash` 动画，白→橙→白，闪烁 3 次），`animationend` 自动移除，提醒用户点击同步。
