# CLAUDE.md — 薪酬合规审阅工具

## 启动与运行

```bash
cd c:\Users\Zora\Desktop\coding\newidea
python app.py
# → http://localhost:5000
```

Python 路径：`C:\Users\Zora\anaconda3\python.exe`
测试用户：Elara, Hailey, kevin, Leon, Mercury, Touyi, Yee（校验人）/ Zora, Jack（负责人）

## DeepSeek API 配置

```bash
# 复制模板并填入真实 API Key
cp .env.example .env
# 编辑 .env 填入真实密钥
```

`.env` 文件示例（已加入 `.gitignore`，不会提交到 Git）：
```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
```

`config.py` 启动时自动通过 `load_dotenv()` 加载 `.env` 文件。

## 项目结构

```
newidea/
├── app.py              # Flask入口，注册蓝图，use_reloader=False避免监控site-packages
├── config.py           # SQLite路径、上传限制16MB
├── models.py           # Project / ModuleAssignment / ReviewField
├── users.py            # 从文件说明.xlsx「用户与权限」sheet 读取用户列表
├── excel_parser.py     # 上传解析：合并单元格填充、列校验
├── excel_writer.py     # 导出：HTML→openpyxl富文本（支持hex和rgb()颜色）
├── routes/
│   ├── auth.py         # 登录（校验用户列表）+ 登出
│   ├── projects.py     # 项目CRUD、列表筛选
│   ├── upload.py       # 上传+解析
│   ├── assign.py       # 模块分配(JSON API)
│   ├── review.py       # 审阅工作台+AJAX保存+l2_index_map预计算 + DeepSeek AI代理
│   ├── export.py       # 导出下载
│   └── ai_usage.py     # AI用量统计仪表盘
├── templates/
│   ├── base.html       # 基础模板(导航栏+AI用量入口)
│   ├── login.html      # 登录页(显示用户列表+datalist)
│   ├── index.html      # 项目列表
│   ├── project_detail.html  # 项目详情+分配(下拉框)
│   ├── review.html     # 审阅工作台(Tab+面板+Prompt面板+AI发送)
│   └── ai_usage.html   # AI用量仪表盘
├── static/
│   ├── css/app.css     # 全局样式(var色板、圆角6px、细滚动条)
│   └── js/review.js    # Quill管理、Tab切换、链接渲染、复制、原地编辑
└── uploads/            # 上传和导出文件
```

## 审阅工作台架构

- URL：`/projects/<id>/review?l2=<index>`
- 布局：顶栏(breadcrumb+折叠按钮) | 左树(可折叠180px) | 主内容(Tab面板)
- Tab切换3组对照对：官方→官方、行业通用→行业权威、内部口径→行业常规
- 每对：上部内容面板 + 下部参考依据面板
- 编辑：点✎→面板变为Quill编辑器(inline)，保存→恢复查看模式
- 参考依据链接：JS `renderRefText()` 渲染，点击在右半屏新窗口打开
- 链接复制：`navigator.clipboard` + `execCommand` fallback
- 导出用 openpyxl 写 `CellRichText`，导出后 openpyxl 读回会丢格式（已知行为）

## AI 用量追踪

- 模型：`AIUsageLog` 表（username, project_id, module, tokens, model, timestamp）
- 每次调用 DeepSeek API 自动记录（`routes/review.py` → `ai_check()`）
- 仪表盘：`/ai-usage` 页（导航栏「📊 AI用量」入口）
- 统计维度：按人汇总 / 按项目汇总 / 最近调用记录
- 费用估算：输入 ¥1/M tokens + 输出 ¥2/M tokens（DeepSeek 定价）
- 路由：`routes/ai_usage.py` → `usage_dashboard()`

## Quill编辑器

- 颜色白名单：`Quill.import('attributors/style/color')` 扩展 `#C00000 #548235 #2E75B5`
- `formatText(index, length, 'color', '#548235')` 应用颜色
- 初始化：`position:absolute; left:-9999px` 确保 DOM 可见，toolbar 绑定正常
- 不支持 toolbar module，用独立 HTML 按钮 + `mousedown` 事件

## 颜色规范

| 用途 | 色值 |
|------|------|
| 状态-已确认 | #36CFC9 |
| 状态-需修改 | #FFB800 |
| 状态-待讨论 | #722ED1 |
| 状态-待审阅 | #F2F3F5 |
| 文本-修改 | #C00000 (红) |
| 文本-增加 | #548235 (绿) |
| 文本-无源 | #2E75B5 (蓝) |
| 主操作蓝 | #1677FF |

## 权限

- 项目负责人：可编辑所有模块、分配、上传、删除
- 已分配校验人：仅编辑自己的模块
- 非负责人登录自动跳转到第一个分配模块
- `review.py` → `check_permission()`

## 已知注意事项

- `use_reloader=False` 避免 Flask watchdog 扫描 Anaconda site-packages 导致重启循环
- 端口占用用任务管理器杀 Python 进程
- 数据清空用 Python `db.session.execute(text('VACUUM'))` 不要直接删被占用的 db 文件
- `.tmp` 文件会干扰 Edit 工具
- JS 中避免 `?.` 可选链语法（兼容性）
- Jinja `tojson` 过滤器输出双引号，与 HTML 属性双引号冲突，需改用单引号包裹或预计算索引

## ✅ excel-format-v2 分支 — 已修复（2026-07-21）

### 分支状态

当前在 `excel-format-v2` 分支，包含以下已完成功能：
- 双格式 Excel 支持（v1: 13列3对照对 / v2: 7列2对照对）
- 格式自动检测（v2 首列标题为「标题Ⅰ」）
- AI Prompt 生成面板（一键复制给 AI 助手核对）
- 演示数据已入库（荷兰 NL 项目，408 字段）

### 已修复的 Bug

**1. review.html 布局 bug（div 嵌套错误）**
- 第 245 行 `</div>` 过早关闭了 flex row，导致 Prompt 面板被挤出三列布局
- 修复：删除第 245 行的 `</div>`，row 在第 262 行正确关闭
- mainCol 硬编码的 `max-width: calc(100% - 180px)` 移除，改为 JS 动态计算

**2. toggleSidebar() 不更新 mainCol 宽度**
- 侧边栏折叠/展开时 mainCol 的 max-width 未同步更新
- 修复：新增 `updateMainColWidth()` 辅助函数，在 `toggleSidebar()` 末尾调用

**3. togglePrompt() 不感知侧边栏折叠状态**
- 打开 Prompt 面板时始终按侧边栏 180px 计算，折叠时应按 0px
- 修复：新增 `getSidebarWidth()` 辅助函数，`updateMainColWidth()` 动态读取实际宽度

**4. restoreViewState() 不恢复 Prompt 面板和 mainCol 宽度**
- 页面刷新后 Prompt 面板状态丢失，mainCol 宽度未根据侧边栏/Prompt 状态更新
- 修复：`restoreViewState()` 新增 Prompt 面板恢复 + `updateMainColWidth()` 调用
- `saveViewState()` 新增 Prompt 面板状态持久化
- 新增 `window.beforeunload` 事件在页面离开前保存状态

**5. excel_writer.py 背景色处理 bug**
- `_parse_tags()` 中 `background-color` CSS 属性错误地覆盖了 `new_fmt['color']`（字体颜色），而非设置背景色
- 这是 copy-paste bug，且下游代码根本不处理背景色
- 修复：删除该代码块

**6. routes/review.py v2 格式说明列读取错误**
- 读取 Excel 中 `l2_说明` 时硬编码列号（l2=col3, desc=col4），v2 格式下应为 l2=col2, desc=col3
- 修复：根据 `project.format_version` 动态选择列号

### 此分支已完成的功能清单

| 功能 | 涉及文件 | 说明 |
|------|----------|------|
| 双格式支持 | models.py, excel_parser.py, routes/review.py, routes/export.py | `format_version` 字段区分 v1/v2 |
| 格式自动检测 | excel_parser.py `detect_format()` | 根据首列标题判断 |
| AI Prompt 面板 | templates/review.html, static/js/review.js | 右侧面板，一键复制 |
| Prompt 生成 | review.js `generatePrompt()` / `copyPrompt()` | 模板填充内容+链接 |
| 数据清理 | 数据库 | 删除了重复上传的 408 条记录 |

### 待办

- [ ] 推送 excel-format-v2 到 GitHub（公司网络需代理 `git config http.proxy http://127.0.0.1:7897`）
- [ ] 合并到 main（布局已修复，可以合并）

### 其他分支

- **trace**：独立 worktree 分支（`newidea-trace`），BGE-M3 + ChromaDB 向量搜索实验
  - `vector_search.py`, `keyword_checker.py`, `routes/trace.py`, `templates/trace.html`
  - 索引构建中，预计 4 天
  - 与主分支无关，不要合并
