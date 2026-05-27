#!/usr/bin/env python3
"""一鍵同步：tars-001/korea-trip-yuki.html → 脫敏 → korea-trip-public/index.html → push GitHub

用法：python3 sync.py "commit message"
"""
import shutil, subprocess, sys
from pathlib import Path

SRC = Path("/Users/xiangyun/Desktop/tars-001/korea-trip-yuki.html")
DST_DIR = Path("/Users/xiangyun/Desktop/korea-trip-public")
DST = DST_DIR / "index.html"
URL = "https://mandy0203-ops.github.io/korea-trip-yuki/"

msg = sys.argv[1] if len(sys.argv) > 1 else "update content"

# 1. 複製
shutil.copy(SRC, DST)
content = DST.read_text()

# 2. 脫敏（敏感資訊永遠不上 GitHub）
REDACTIONS = [
    ('訂位代號 EC66FG', '訂位代號（見 email）'),
    ('訂位代號 S5U7KC', '訂位代號（見 email）'),
    ('Agoda 訂單 #1727608543 / 6/1 自動扣款 NT$3,139',
     'Agoda 訂單見 email / 6/1 自動扣款 NT$3,139'),
    ('Agoda #1727608543 · 2 晚 NT$3,139',
     'Agoda · 2 晚 NT$3,139（訂單號見 email）'),
]
for old, new in REDACTIONS:
    content = content.replace(old, new)

# 3. 健康檢查：確認沒漏
for sensitive in ['EC66FG', 'S5U7KC', '1727608543']:
    assert sensitive not in content, f"❌ 敏感資訊 {sensitive} 仍存在！中止 push"

DST.write_text(content)
print("✅ Sanitized")

# 4. Git push
subprocess.run(["git", "add", "index.html"], cwd=DST_DIR, check=True)
commit = subprocess.run(["git", "commit", "-m", msg], cwd=DST_DIR)
if commit.returncode != 0:
    print("⚠️ No changes to commit (file identical)")
    sys.exit(0)
subprocess.run(["git", "push"], cwd=DST_DIR, check=True)
print(f"✅ Pushed → {URL}")
print("   GitHub Pages 約 30-60 秒後生效")
