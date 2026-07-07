import os
import shutil
import time

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'backups')

os.makedirs(BACKUP_DIR, exist_ok=True)
MAX_BACKUPS = 48  # 保留最近 48 个

if not os.path.exists(DB_PATH):
    print(f'数据库文件不存在: {DB_PATH}')
    exit(1)

ts = time.strftime('%Y%m%d_%H%M%S')
backup_name = f'data_{ts}.db'
backup_path = os.path.join(BACKUP_DIR, backup_name)

shutil.copy2(DB_PATH, backup_path)
print(f'备份完成: {backup_name}')

# 清理旧备份
files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
for old in files[:-MAX_BACKUPS]:
    os.remove(os.path.join(BACKUP_DIR, old))
    print(f'清理旧备份: {old}')
