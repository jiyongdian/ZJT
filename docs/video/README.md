# 视频功能文档

本目录包含与视频生成相关的功能文档。

## 文档列表

| 文档 | 说明 |
|------|------|
| [extract_frame_node.md](./extract_frame_node.md) | 提取帧节点 - 从视频提取首帧/尾帧 |
| [grid_merge_video_generation.md](./grid_merge_video_generation.md) | 分镜组多宫格图片合并 & 视频生成 |
| [shot_group_video_generation.md](./shot_group_video_generation.md) | 分镜组节点视频生成功能 |
| [../drivers/seedance_volcengine_v1_driver.md](../drivers/seedance_volcengine_v1_driver.md) | Seedance 火山引擎驱动（支持参考音频/视频） |

## 功能说明

- **extract_frame_node**: 从视频中提取首帧或尾帧，自动创建图片节点
- **grid_merge_video_generation**: 将多个分镜首帧合并为宫格图后生成视频
- **shot_group_video_generation**: 拼接所有分镜视频提示词，使用第一个分镜首帧生成视频
