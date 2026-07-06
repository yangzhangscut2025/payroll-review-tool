# 薪酬合规审阅工具

帮助薪酬合规校验员在线审阅 Excel 表格、标记状态、协作分工、导出带完整审阅标记的 Excel。

## 快速启动

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```

用户列表由 `文件说明.xlsx` 的「用户与权限」sheet 定义。

## 文档

- [需求文档](需求文档.md)
- [使用说明](使用说明.md)

## 技术栈

Python Flask + SQLite + Bootstrap 5 + Quill.js + openpyxl
