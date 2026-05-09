# 远程通知系统

## 概述

ZJT 系统作为客户端，定期从远程服务器拉取通知信息（版本更新、系统公告等），并在管理后台展示给管理员。

类似 WordPress 检查 wp.org 更新的机制：客户端定期轮询远程 API，获取最新通知并存储到本地数据库。

```
远程服务器 (ZJT官方)                    ZJT 客户端 (用户部署)
┌─────────────────┐                  ┌─────────────────────┐
│ 通知 API        │  ←── HTTP ────  │ NotificationService │
│ (Swagger 文档)  │                  │ (定时轮询)           │
│                 │  ──→ JSON ────→  │                     │
│ 返回:           │                  │ - 版本信息 → 内存缓存│
│ - 版本更新      │                  │ - 通知 → DB 存储    │
│ - 系统公告      │                  │                     │
└─────────────────┘                  │ admin.html 展示:    │
                                     │ - 通知中心          │
                                     │ - 未读角标          │
                                     └─────────────────────┘
```

## 远程服务器 API（Swagger 文档）

### 基础信息

- **Base URL**: `https://ailive.perseids.cn:11443/api/v1`（可通过 `config.constant.NotificationConstants.REMOTE_API_BASE` 配置）
- **认证**: 无需认证（公开接口）
- **客户端标识**: 通过 Header 传递客户端信息

### GET /notifications/check

客户端定时调用，获取最新通知和版本更新信息。

**请求 Header:**

| Header | 类型 | 说明 |
|--------|------|------|
| `X-Client-Version` | string | 客户端当前版本号（如 `1.5.2`） |
| `X-Client-Env` | string | 客户端环境（`prod` / `test` / `dev`） |
| `X-Client-ID` | string | 客户端唯一标识（单向 hash，不可逆） |

**X-Client-ID 生成规则:**

```python
import hashlib, socket, platform

def generate_client_id(install_path: str) -> str:
    """生成客户端唯一标识（单向hash，不可逆）

    组合: 主机名 + 主机IP + 安装路径
    效果:
    - 不同服务器 → 不同 ID
    - 同一服务器不同目录 → 不同 ID
    - 不可反推出原始信息
    """
    hostname = platform.node()
    ip = socket.gethostbyname(socket.gethostname())
    raw = f"{hostname}|{ip}|{install_path}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
```

**响应 200:**

```json
{
  "code": 0,
  "data": {
    "version_update": {
      "has_update": true,
      "current_version": "1.5.2",
      "latest_version": "1.6.0",
      "release_notes": "1. 修复了xxx问题\n2. 新增xxx功能\n3. 优化xxx性能",
      "changelog_url": "https://github.com/jeffstric/ZJT/releases/tag/v1.6.0"
    },
    "announcements": [
      {
        "id": "ann_20260508_001",
        "type": "announcement",
        "title": "新功能上线：AI 智能分镜",
        "content": "我们上线了 AI 智能分镜功能，可以自动将剧本拆分为分镜...",
        "level": "info",
        "start_time": "2026-05-08T00:00:00Z",
        "end_time": "2026-05-15T00:00:00Z",
        "link": "https://zjt.com/feature/storyboard",
        "link_text": "了解详情"
      },
      {
        "id": "ann_20260508_002",
        "type": "maintenance",
        "title": "系统维护通知",
        "content": "5月10日凌晨2点-4点进行系统维护，期间服务可能不可用",
        "level": "warning",
        "start_time": "2026-05-08T00:00:00Z",
        "end_time": "2026-05-10T06:00:00Z",
        "link": null,
        "link_text": null
      }
    ],
    "check_interval": 3600
  }
}
```

**字段说明:**

`version_update` — 版本更新信息（仅展示，无下载功能）:

| 字段 | 类型 | 说明 |
|------|------|------|
| `has_update` | bool | 是否有新版本 |
| `current_version` | string | 客户端当前版本（由客户端上报，服务器回传） |
| `latest_version` | string | 最新版本号 |
| `release_notes` | string | 更新日志（纯文本，支持换行） |
| `changelog_url` | string\|null | 完整更新日志链接（可选） |

`announcements[]` — 系统公告:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一 ID（客户端用于去重） |
| `type` | string | 类型: `announcement` / `maintenance` / `feature` / `security` |
| `title` | string | 标题 |
| `content` | string | 正文 |
| `level` | string | 级别: `info` / `warning` / `error` / `success` |
| `start_time` | ISO8601 | 生效时间 |
| `end_time` | ISO8601 | 过期时间（过期后不再返回） |
| `link` | string\|null | 外部链接（可选） |
| `link_text` | string\|null | 链接文案（可选） |

顶层字段:

| 字段 | 类型 | 说明 |
|------|------|------|
| `check_interval` | int | 建议的下次检查间隔（秒），客户端应尊重此值 |

## 客户端实现

### 文件清单

| 文件 | 说明 |
|------|------|
| `config/constant.py` | `NotificationConstants` 常量定义 |
| `model/notifications.py` | 数据库模型（Entity + Model + SQL） |
| `services/notification_service.py` | 后台拉取服务 |
| `api/notifications.py` | API 路由 |
| `server.py` | 路由注册 + 服务初始化 |
| `web/admin.html` | 前端通知中心页面 |
| `web/js/admin.js` | 前端轮询和交互逻辑 |
| `web/css/admin.css` | 通知样式 |
| `alembic/versions/20260508_create_notifications.py` | 数据库迁移 |

### 数据库表

```sql
CREATE TABLE notifications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  remote_id VARCHAR(64) NOT NULL COMMENT '远程通知ID（用于去重）',
  notification_type VARCHAR(32) NOT NULL DEFAULT 'announcement',
  title VARCHAR(255) NOT NULL,
  content TEXT,
  level VARCHAR(16) NOT NULL DEFAULT 'info',
  extra_data TEXT COMMENT 'JSON: link, link_text 等',
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  start_time DATETIME,
  end_time DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_remote_id (remote_id),
  KEY idx_is_read (is_read),
  KEY idx_created_at (created_at)
);
```

### NotificationService

后台服务，定时从远程服务器拉取通知：

- **初始化**: 服务器启动时调用 `initialize()`，生成 `client_id`，延迟 5 秒后首次检查
- **定时轮询**: 按远程返回的 `check_interval`（默认 3600 秒）定时检查
- **去重**: 通知按 `remote_id` 去重（UNIQUE KEY 约束），已存在的不重复插入
- **容错**: 远程 API 不可达时静默跳过，不影响本地功能

### 客户端 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/notifications/poll` | GET | 前端轮询，返回版本更新 + 未读通知 + 未读数量 + 缺失二进制 |
| `/api/notifications/{id}/read` | POST | 标记单条通知为已读 |
| `/api/notifications/read-all` | POST | 标记所有通知为已读 |
| `/api/notifications/admin/list` | GET | 管理员查看通知列表（分页，需管理员权限） |
| `/api/notifications/admin/{id}` | DELETE | 管理员删除通知（需管理员权限） |

### Poll API 响应

`/api/notifications/poll` 返回示例:

```json
{
  "code": 0,
  "data": {
    "version_update": {
      "has_update": true,
      "current_version": "1.5.0",
      "latest_version": "1.6.1",
      "release_notes": "1.6.1 版本实现了自动升级功能",
      "changelog_url": "https://github.com/jeffstric/ZJT/releases/tag/1.6.1",
      "required_binaries": []
    },
    "notifications": [
      {
        "id": 1,
        "remote_id": "ann_20260508_001",
        "type": "announcement",
        "title": "新功能上线：版本自动升级",
        "content": "我们上线了版本自动升级功能，可以自动检测并升级到最新版本...",
        "level": "info",
        "link": "https://github.com/jeffstric/ZJT/releases/tag/1.6.1",
        "link_text": "查看更新",
        "is_read": false,
        "start_time": "2026-05-08T00:00:00Z",
        "end_time": "2026-06-30T00:00:00Z",
        "created_at": "2026-05-08T12:00:00"
      }
    ],
    "unread_count": 1,
    "missing_binaries": [
      {
        "name": "ffmpeg",
        "description": "音视频处理工具",
        "download_url": "https://cdn.zjt.com/bin/ffmpeg-6.0-win64.zip",
        "check_path": "bin/ffmpeg/ffmpeg.exe"
      }
    ]
  }
}
```

`notifications[]` — 未读通知列表（从数据库读取）:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 数据库自增 ID |
| `remote_id` | string | 远程通知 ID（去重用） |
| `type` | string | 类型: `announcement` / `maintenance` / `feature` / `security` |
| `title` | string | 标题 |
| `content` | string | 正文 |
| `level` | string | 级别: `info` / `warning` / `error` / `success` |
| `link` | string\|null | 外部链接 |
| `link_text` | string\|null | 链接文案 |
| `is_read` | bool | 是否已读 |
| `start_time` | ISO8601\|null | 生效时间 |
| `end_time` | ISO8601\|null | 过期时间 |
| `created_at` | string | 创建时间 |

`version_update` — 版本更新信息（无更新时为 `null`）:

| 字段 | 类型 | 说明 |
|------|------|------|
| `has_update` | bool | 是否有新版本 |
| `current_version` | string | 客户端当前版本 |
| `latest_version` | string | 最新版本号 |
| `release_notes` | string | 更新日志 |
| `changelog_url` | string\|null | 完整更新日志链接 |
| `required_binaries` | array | 新版本需要的二进制依赖 |

`missing_binaries[]` — 本地缺失的二进制依赖:

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 工具名称 |
| `description` | string | 工具描述 |
| `download_url` | string | 下载地址（可选） |
| `check_path` | string | 需要放置的相对路径 |

### 前端展示

管理后台「通知中心」页面：

- **版本升级横幅**: 显示新版本号和更新日志（仅信息展示，无下载按钮）
- **缺失二进制依赖提醒**: 显示本地缺失的二进制工具，包括下载链接和放置路径
- **通知列表**: 按类型和级别展示，支持标记已读 / 全部已读
- **未读角标**: 侧边栏菜单显示未读通知数量
- **自动轮询**: 每 30 秒轮询一次 `/api/notifications/poll`

### 二进制依赖配置

系统通过 `config/required_binaries.yml` 配置文件定义所需的二进制依赖。

**配置文件格式:**

```yaml
binaries:
  ffmpeg:
    description: "音视频处理工具"
    download_url: "https://cdn.zjt.com/bin/ffmpeg-6.0-win64.zip"
    check_paths:
      windows: "bin/ffmpeg/ffmpeg.exe"
      linux: "bin/ffmpeg/ffmpeg"
      macos: "bin/ffmpeg/ffmpeg"
    required_since: "2.0.0"
```

**字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 工具名称（YAML key） |
| `description` | string | 工具描述 |
| `download_url` | string | 下载地址（可选） |
| `check_paths` | object | 按平台的检查路径 |
| `check_paths.windows` | string | Windows 平台相对路径 |
| `check_paths.linux` | string | Linux 平台相对路径 |
| `check_paths.macos` | string | macOS 平台相对路径 |
| `required_since` | string | 从哪个版本开始需要此依赖（语义化版本号） |

**检查逻辑:**

1. 读取 `config/required_binaries.yml` 配置
2. 根据当前平台（Windows/Linux/macOS）选择对应的检查路径
3. 比较当前版本与 `required_since`，只检查当前版本需要的依赖
4. 检查文件是否存在，缺失的依赖会在通知中心显示
