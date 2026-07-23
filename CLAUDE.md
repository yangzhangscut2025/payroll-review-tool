# CLAUDE.md — 薪酬合规审阅工具

## 当前状态

- **分支**：`excel-format-v2`（GitHub 默认分支，已保护）
- **生产环境**：腾讯云服务器 `106.53.56.194:5000`，Waitress 16 线程
- **本地开发**：`newidea-dev/`（dev 分支），`newidea/`（稳定版）
- **用户**：全部改为负责人

## 启动与运行

```bash
cd c:\Users\Zora\Desktop\coding\newidea
python app.py
# → http://localhost:5000
```

Python 路径：`C:\Users\Zora\anaconda3\python.exe`

## 项目结构

```
newidea/
├── app.py              # Flask入口，Waitress生产服务器，16线程
├── config.py           # load_dotenv()加载.env，DEEPSEEK_API_KEY等
├── models.py           # Project / ModuleAssignment / ReviewField / AIUsageLog
├── users.py            # 从文件说明.xlsx「用户与权限」sheet读取用户列表
├── excel_parser.py     # 上传解析：v1/v2/v3三种格式，合并单元格填充
├── excel_writer.py     # 导出：HTML→openpyxl富文本 + 批量翻译 + 多sheet
├── routes/
│   ├── auth.py         # 登录（校验用户列表）+ 登出
│   ├── projects.py     # 项目CRUD、列表筛选、编辑（名称/国家）、软删除
│   ├── upload.py       # 上传+格式识别+解析，重新上传前清旧数据
│   ├── assign.py       # 模块分配(JSON API)
│   ├── review.py       # 审阅工作台+AJAX保存+DeepSeek AI代理
│   ├── export.py       # 异步导出+预览+进度轮询+翻译+下载
│   └── ai_usage.py     # AI用量统计仪表盘
├── templates/
│   ├── base.html       # 基础模板(导航栏+AI用量入口)
│   ├── login.html      # 登录页
│   ├── index.html      # 项目列表
│   ├── project_detail.html  # 项目详情+分配+编辑+导出预览弹窗
│   ├── review.html     # 审阅工作台(三栏+Prompt面板+AI发送)
│   └── ai_usage.html   # AI用量仪表盘
├── static/
│   ├── css/app.css     # 全局样式
│   └── js/review.js    # Quill管理、Tab切换、Prompt生成、AI发送
└── uploads/            # 上传和导出文件
```

## Excel 格式支持（三种）

| 格式 | 列数 | 对照对 | 首列标题 | 识别方式 |
|------|------|--------|---------|---------|
| v1 | 13 | 3（官方/行业通用/内部口径） | l1_标题 | 默认 |
| v2 | 7 | 2（官方规则/行业通用） | 标题Ⅰ | 首列=标题Ⅰ |
| v3 | 10 | 2（官方/行业通用） | l1_标题 | 第5列=实务内容（官方）且无内部口径 |

## 审阅工作台

- URL：`/projects/<id>/review?l2=<index>`
- 布局：顶栏 | 左树(180px可折叠) | 主内容(Tab面板) | Prompt面板(450px可折叠)
- v1: 3个Tab，v2/v3: 2个Tab
- 编辑：点✎→Quill编辑器(inline)，工具栏R(红=修改)/G(绿=增加)/N(蓝=无源)/D(删除线)
- 状态按钮：待审阅/已确认/需修改/待讨论，快捷键1/2/3/4
- 链接：`renderRefText()`渲染，状态标注(有效/失效/待验证)，纠正链接
- 左右方向键切换模块，Esc取消编辑

## AI Prompt 面板

- 点🤖 Prompt打开，`generatePrompt()`生成核对提示词
- **推荐**：📋复制→豆包/DeepSeek对话框（效果比API直接发送好）
- 🚀发送：调用DeepSeek API，结果显示在面板下半部分
- v2/v3格式自动合并两个参考面板的全部链接，标注来源
- Prompt模板在`review.js` `generatePrompt()`函数中

## 导出功能

- 点击📥导出→预览弹窗（Sheet列表/字段数/翻译量/费用/耗时）
- 确认→后台异步导出+实时进度条→完成自动下载
- 中文sheet：直接填审阅内容
- 英文sheet：DeepSeek API批量翻译（每批20条，HTML标签占位符保护）
- 本地语言sheet：跳过不处理
- 翻译失败自动回退中文原文

## AI 用量追踪

- `AIUsageLog` 表：username, project_id, tokens, model, timestamp
- 每次API调用自动记录（审阅发送 + 导出翻译）
- 仪表盘：`/ai-usage`，导航栏📊AI用量入口
- 费用估算：输入¥1/M tokens + 输出¥2/M tokens

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

## 服务器部署

- **地址**：`106.53.56.194:5000`
- **系统**：Ubuntu 22.04，腾讯云轻量服务器
- **服务管理**：`systemctl restart/status review-tool`，开机自启
- **代码同步**：本地改代码 → 双击 `C:\Users\Zora\Desktop\sync.bat` → 自动打包上传重启
- **备份**：Windows 定时任务，每天 18:30 自动下载 `data.db` 到 `C:\Users\Zora\Desktop\backups\`

## GitHub 仓库

- **地址**：https://github.com/yangzhangscut2025/payroll-review-tool
- **默认分支**：`excel-format-v2`（已保护，不能直接 push）
- **开发流程**：`newidea-dev/` 改代码 → push dev → 开 PR → Approve → Merge → git pull → sync.bat
- **SSH 推送**：已配置 SSH Key，无需密码

## 权限

- 项目负责人：可编辑所有模块、分配、上传、删除
- 已分配校验人：仅编辑自己的模块
- `review.py` → `check_permission()`（判断依据是 `project.created_by`，不是角色字段）

## 已知注意事项

- `use_reloader=False` 避免 Flask watchdog 扫描 Anaconda site-packages 导致重启循环
- 修改代码后需手动重启 Flask（本地）/ 运行 sync.bat（服务器）
- 端口占用用任务管理器杀 Python 进程
- `.tmp` 文件会干扰 Edit 工具
- JS 中避免 `?.` 可选链语法（兼容性）
- Jinja 模板中 JS 变量统一用 `{{ value|tojson }}`，不要用 `"{{ value }}"`
- 导出后 openpyxl 读回会丢富文本格式（Excel 本身没问题）
- 后台线程操作 DB 需手动创建 app_context
- Python `.format()` 中 `{` 和 `}` 需转义为 `{{` 和 `}}`
- `link_urls` 持久化：上传时提取保存，渲染时优先读持久化数据，无数据时回退提取

## 其他分支

- **dev**：开发分支，`newidea-dev/` 文件夹
- **trace**：BGE-M3 + ChromaDB 向量搜索实验，不要合并
- **main**：旧版，保留参考