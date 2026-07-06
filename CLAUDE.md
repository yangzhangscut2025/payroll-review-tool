# CLAUDE.md — 薪酬合规审阅工具

## 启动与运行

```bash
cd c:\Users\Zora\Desktop\coding\newidea
python app.py
# → http://localhost:5000
```

Python 路径：`C:\Users\Zora\anaconda3\python.exe`
测试用户：Elara, Hailey, kevin, Leon, Mercury, Touyi, Yee（校验人）/ Zora, Jack（负责人）

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
│   ├── review.py       # 审阅工作台+AJAX保存+l2_index_map预计算
│   └── export.py       # 导出下载
├── templates/
│   ├── base.html       # 基础模板(导航栏)
│   ├── login.html      # 登录页(显示用户列表+datalist)
│   ├── index.html      # 项目列表
│   ├── project_detail.html  # 项目详情+分配(下拉框)
│   └── review.html     # 审阅工作台(Tab+面板+原地编辑)
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
