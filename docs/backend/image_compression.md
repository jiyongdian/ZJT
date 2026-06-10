# 图片压缩功能

## 概述

系统提供自动图片压缩功能，用于处理超过 API 限制的图片文件。

## 使用场景

### Seedream 火山引擎驱动

火山引擎 Seedream API 对输入图片有 **10 MB** 的大小限制。系统会在发送请求前自动检查并压缩超过限制的图片。

**驱动文件**: `task/visual_drivers/seedream_volcengine_v1_driver.py`

## 压缩工具

### 工具位置

`utils/image_compressor.py`

### 核心函数

#### `compress_image_to_limit()`

压缩图片到指定大小限制。

**参数**:
- `image_path` (str): 输入图片路径
- `max_size_mb` (float): 最大文件大小（MB），默认 10.0
- `output_path` (Optional[str]): 输出路径，如果为 None 则覆盖原文件
- `quality_start` (int): 起始压缩质量（1-100），默认 95
- `quality_min` (int): 最低压缩质量（1-100），默认 60

**返回值**: `Tuple[bool, Optional[str], Optional[str]]`
- `bool`: 是否成功
- `Optional[str]`: 输出文件路径（成功时）
- `Optional[str]`: 错误信息（失败时）

**示例**:
```python
from utils.image_compressor import compress_image_to_limit

success, output_path, error = compress_image_to_limit(
    image_path="/path/to/large_image.jpg",
    max_size_mb=10.0,
    output_path=None,  # 覆盖原文件
    quality_start=95,
    quality_min=60
)

if success:
    print(f"压缩成功: {output_path}")
else:
    print(f"压缩失败: {error}")
```

#### `get_image_size_mb()`

获取图片文件大小（MB）。

**参数**:
- `image_path` (str): 图片路径

**返回值**: `Optional[float]`
- 文件大小（MB），失败返回 None

## 压缩策略

### 1. 质量压缩

首先尝试降低 JPEG 质量参数（从 95 逐步降低到 60），同时保持原始分辨率。

### 2. 格式转换

如果原图是 PNG 格式，会自动转换为 JPEG 格式以获得更好的压缩效果：
- 处理透明通道（转换为白色背景）
- 启用渐进式 JPEG
- 启用优化模式

### 3. 尺寸缩放

如果降低质量仍无法满足大小限制，会逐步缩小图片尺寸：
- 每次缩小到原尺寸的 90%
- 最多尝试 10 次
- 使用 LANCZOS 重采样算法保证质量

## 工作流程

### Seedream 驱动中的集成

系统使用 `compress_and_upload_image_sync()` 统一处理图片：

1. **解析 URL 到本地路径**
   - 本地文件路径 → 直接使用
   - 本地服务 URL → 映射到本地文件
   - 远程 URL → 下载到临时目录

2. **检查图片大小**
   - ≤ 10MB → 跳过压缩
   - > 10MB → 执行压缩

3. **压缩图片**（如需要）
   - 输出到 `upload/temp/{YYYYMMDD}/` 目录
   - 自动降低质量或缩小尺寸

4. **保存并返回 URL**
   - 本地环境 → 上传到 CDN
   - 服务器环境 → 返回服务器 URL

**示例代码：**
```python
from utils.image_upload_utils import compress_and_upload_image_sync

success, new_url, error = compress_and_upload_image_sync(
    image_url,
    config,
    max_size_mb=10.0,
    is_local=False
)

if success:
    # 使用 new_url
else:
    # 处理错误
```

## 日志记录

压缩过程会记录详细日志：

```
WARNING - 图片 /path/to/image.jpg 大小 11.23 MB 超过 10 MB 限制，开始压缩
INFO - 原始图片大小: 11.23 MB
INFO - 质量 95: 10.85 MB
INFO - 质量 90: 9.87 MB
INFO - 压缩完成: 11.23 MB -> 9.87 MB (质量: 90)
INFO - 图片压缩成功: /path/to/image.jpg
```

## 错误处理

### 常见错误

1. **文件不存在**
   ```
   错误: 文件不存在: /path/to/image.jpg
   ```

2. **无法打开图片**
   ```
   错误: 无法打开图片: [具体错误信息]
   ```

3. **无法压缩到限制大小**
   ```
   错误: 无法将图片压缩到 10 MB 以下
   ```

### 用户提示

当压缩失败时，系统会返回友好的错误信息：
```json
{
    "success": false,
    "error": "图片压缩失败: [具体原因]",
    "error_type": "USER",
    "retry": false
}
```

## 性能考虑

- 压缩操作在同步模式下执行
- 对于大图片，压缩可能需要几秒钟
- 建议在上传前对图片进行预处理

## 临时文件清理

压缩后的图片保存在 `upload/temp/{YYYYMMDD}/` 目录下。系统会自动清理过期文件：

- **清理机制**: 复用 `media_cache.py` 的定时任务
- **清理周期**: 每 24 小时执行一次
- **保留时间**: 保留最近 2 天的文件
- **实现位置**: `utils/media_cache.py` 中的 `cleanup_temp_dir()` 方法

日志示例：
```
INFO - 开始清理 upload/temp 目录，保留 2 天，截止时间: 2026-03-26 11:00:00
INFO - 删除过期目录: /path/to/upload/temp/20260325 (15 个文件)
INFO - upload/temp 清理完成，删除 15 个文件
```

## 扩展性

如需为其他驱动添加图片压缩功能，使用统一函数：

```python
from utils.image_upload_utils import compress_and_upload_image_sync

success, new_url, error = compress_and_upload_image_sync(
    image_url,  # 支持本地路径或 URL
    config,
    max_size_mb=YOUR_LIMIT_MB,
    is_local=False
)

if success:
    # 使用 new_url（已压缩并上传）
else:
    # 处理错误
    logger.error(f"图片处理失败: {error}")
```
