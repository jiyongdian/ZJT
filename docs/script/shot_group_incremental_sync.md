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
