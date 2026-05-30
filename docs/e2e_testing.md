# 端到端浏览器自动化测试

本项目提供两种端到端测试方案：AI 智能体驱动（JSON 测试用例）和编程式自动化（pytest + Playwright）。

## 目录结构

```
auto_test/
├── test_modules/              # JSON 测试用例（AI 智能体驱动）
│   ├── index.json             # 模块索引（含依赖关系）
│   └── *.json                 # 15 个模块的测试用例
├── e2e/                       # 编程式 E2E 测试（pytest + Playwright）
│   ├── conftest.py            # 核心 fixtures
│   ├── pytest.ini             # pytest 配置
│   ├── helpers/
│   │   ├── api_client.py      # httpx 异步 API 客户端
│   │   └── page_objects.py    # Page Object 基类
│   ├── test_auth.py           # 认证模块（3 个 P0）
│   ├── test_session.py        # 会话管理（5 个 P0）
│   ├── test_world.py          # 世界 CRUD（5 个 P0）
│   ├── test_character.py      # 角色 CRUD（4 个 P0）
│   ├── test_location.py       # 场景 CRUD（5 个 P0）
│   ├── test_workflow.py       # 工作流 CRUD（5 个 P0）
│   ├── test_workflow_page.py  # 工作流前端页面（3 个 P0）
│   ├── test_audio.py          # 音频模块（2 个 P0）
│   ├── test_script_writer.py  # 剧本编辑器页面（2 个 P0）
│   ├── test_marketing_agent.py# 营销智能体页面（3 个 P0）
│   └── test_admin.py          # 管理后台（1 个 P0）
├── test_assets/               # 测试资源文件
├── test_config.json           # 测试配置文件
└── test_sessions/             # 测试会话记录
```

## 快速开始

### 1. 安装依赖

```bash
pip install playwright pytest-html pytest-timeout pytest-asyncio
playwright install chromium
```

### 2. 配置

复制 `test_config.example.json` 为 `test_config.json`，填写：
- `base_url`: 服务器地址（默认 http://localhost:8000）
- `credentials.primary`: 测试账号手机号和密码
- `test_assets`: 测试资源文件路径

### 3. 运行测试

```bash
cd auto_test/e2e

# 运行所有 P0 测试
pytest -v -m p0

# 运行指定模块
pytest -v -m auth
pytest -v -m session
pytest -v -m world

# 运行所有测试
pytest -v

# 生成 HTML 报告
pytest -v --html=reports/report.html --self-contained-html
```

## Fixture 架构

```
e2e_config (session) ─── 读取 test_config.json
├── auth_token (session) ─── API 登录获取 token
├── user_id (session) ─── 登录返回的 user_id
├── auth_headers (session) ─── Authorization + X-User-Id
├── browser (session) ─── Playwright chromium 实例
│   └── browser_context (function) ─── 注入 localStorage 认证
│       └── page (function) ─── 独立页面实例
└── api_client (function) ─── httpx.Client
    ├── test_world (function) ─── 创建测试世界，yield 后清理
    │   ├── test_character (function) ─── 创建测试角色
    │   └── test_location (function) ─── 创建测试场景
    ├── test_workflow (function) ─── 创建测试工作流
    └── test_session_id (function) ─── 创建测试会话
```

### 关键设计

- **认证跳过 UI**：通过 API 登录获取 token，注入 localStorage，避免反复 UI 登录
- **API 客户端**：使用 httpx.Client（同步），不阻塞服务端事件循环
- **测试数据工厂**：`test_world`、`test_workflow` 等 fixture 自动创建和清理测试数据

## 测试标记

| 标记 | 说明 |
|------|------|
| `p0` | P0 核心功能（必须通过） |
| `p1` | P1 重要功能（应该通过） |
| `p2` | P2 次要功能（可选通过） |
| `auth` | 认证模块 |
| `session` | 会话管理模块 |
| `world` | 世界管理模块 |
| `character` | 角色管理模块 |
| `location` | 场景管理模块 |
| `workflow` | 工作流 CRUD 模块 |
| `workflow_page` | 工作流前端页面模块 |
| `audio` | 音频模块 |
| `script_writer` | 剧本编辑器模块 |
| `marketing_agent` | 营销智能体模块 |
| `admin` | 管理后台模块 |

## 模块依赖关系

```
auth (无依赖)
├── workflow_list
├── world_management
│   ├── location_management
│   └── character_management
├── workflow_editor
│   ├── node_operations
│   │   ├── shot_frame_video
│   │   ├── shot_group_video
│   │   └── camera_control
│   ├── timeline
│   ├── grid_image_generation
│   └── audio
├── error_handling
└── marketing_agent
```

## 两种测试方案对比

| 维度 | JSON 测试 (AI 智能体) | pytest E2E (编程式) |
|------|----------------------|-------------------|
| 驱动方式 | AI 解读 JSON，调用 MCP 工具 | 编程式 Playwright API |
| 执行速度 | 慢（AI 推理 + MCP 通信） | 快（直接 API 调用） |
| 稳定性 | 受 AI 理解准确性影响 | 确定性高 |
| 适合场景 | 探索性测试、新功能验证 | 回归测试、CI/CD |
| 维护方式 | JSON 文件编辑 | Python 代码 |

## 添加新测试

1. 在 `e2e/` 目录创建 `test_<模块名>.py`
2. 使用 `conftest.py` 中的 fixtures
3. 添加 pytest markers：`@pytest.mark.<模块名>` 和 `@pytest.mark.p0`
4. 使用 Page Object 模式操作浏览器页面
5. 更新本文档
