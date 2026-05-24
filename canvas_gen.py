#!/usr/bin/env python3
"""
Generate itinerary-canvas.excalidraw — Excalidraw 行程編排 canvas
排版：左側候選池 (5×6 grid) + 右側 3 days × 4 時段 grid + 標題/說明

用法: python3 canvas_gen.py
輸出: itinerary-canvas.excalidraw (import 到 https://excalidraw.com)
"""
import json
import time
import random

random.seed(42)
NOW = int(time.time() * 1000)

# ── 配色（莫蘭迪暖調，跟 korea-trip-yuki 一致）
COLORS = {
    "food":  "#ffec99",  # 黃 — 食物
    "shop":  "#d0bfff",  # 紫 — 購物
    "med":   "#ffc9c9",  # 粉 — 醫美
    "sauna": "#a5d8ff",  # 藍 — 汗蒸幕
    "spot":  "#b2f2bb",  # 綠 — 景點/區域
    "trans": "#ffd8a8",  # 橘 — 交通/錨點
    "other": "#dee2e6",  # 灰 — 其他
}

# ── 卡片清單：(emoji+name, category, [optional pre-pin: (col, row)])
# col: 0=DAY1, 1=DAY2, 2=DAY3 ; row: 0=上午, 1=中午, 2=下午, 3=晚上
CARDS = [
    # 食物（聖水洞群）
    ("🥯 London Bagel\n安國店", "food"),
    ("🍞 Artist Bakery\n鹽麵包 安國", "food"),
    ("🦀 花蟹世界\n弘大醬蟹", "food"),
    ("🍓 Rafre Fruit\n西村店", "food"),
    ("🍓 Rafre Fruit\n聖水洞本店", "food"),
    ("🍫 杜拜巧克力\n冰淇淋 聖水", "food"),
    ("🍓 韓貞仙杜拜\n巧克力(包草莓)", "food"),
    ("☕ 水蜜桃美式\n+2 shots", "food"),
    ("🍓 No.1 草莓蛋糕\n景福宮分店", "food"),
    ("🍰 杜拜巧克力\n星冰樂 SBUX", "food"),
    ("🧀 明洞烤起司\n年糕", "food"),
    ("🍱 GS25 超商\n必吃清單", "food"),
    # 景點/區域
    ("🏘️ 半天逛\n聖水洞", "spot"),
    ("🚺 聖水洞\n免費女廁", "spot"),
    # 購物
    ("🛍️ Olive Young\n江南旗艦", "shop"),
    ("🐱 OY 寵物香水\nZoa", "shop"),
    ("🧴 大창 신림역店\n(離飯店最近)", "shop"),
    ("🧴 大창 新村本店\n(原推薦)", "shop"),
    ("💜 大창頭髮香水\n₩3000", "shop"),
    ("🧼 大창神級\n家事皂", "shop"),
    ("👕 弘大寶藏\n服飾店", "shop"),
    ("👟 ept 鞋\n兩萬步不痛", "shop"),
    ("💊 藥局 PDRN\n麗珠蘭 痘膏", "shop"),
    ("💊 藥局中文\n藥師", "shop"),
    ("⚡ UNIQLO 感謝祭\n5/30-6/5", "shop"),
    # 醫美
    ("💉 黃金微針\nDr.Evers 明洞", "med"),
    # 汗蒸幕
    ("♨️ 太陽海水\n汗蒸幕(主推)", "sauna"),
    ("♨️ 삼모스포렉스\n(老牌複合館)", "sauna"),
    ("♨️ 우성사우나\n(搓澡大媽最強)", "sauna"),
]

# ── 鐵錨：已固定不能動的卡（直接放進 grid，不在 pool）
ANCHORS = [
    # (text, category, col, row)
    ("✈️ 16:55 抵金浦\n→ 莊藍 check-in", "trans", 0, 2),  # D1 下午
    ("🏨 莊藍 check-in\n(신림站 3 分)", "trans", 0, 2),
    ("💉 14:00 江南醫美\n(必到・已預約)", "med", 1, 2),    # D2 下午
    ("✈️ 17:30 前到金浦\n→ 20:35 IT663 回程", "trans", 2, 3),  # D3 晚上
]

# ── 排版尺寸
CARD_W, CARD_H = 220, 80
GAP_X, GAP_Y = 20, 20

# Pool zone (左): 5 cols × 6 rows = 30 slots
POOL_X0, POOL_Y0 = 20, 180
POOL_COLS = 5
POOL_W = POOL_COLS * (CARD_W + GAP_X)  # 5×240 = 1200

# Grid zone (右): 3 cols × 4 rows
GRID_X0 = POOL_X0 + POOL_W + 80  # 1300
GRID_Y0 = 180
CELL_W = 540
CELL_H = 260
GRID_W = 3 * (CELL_W + GAP_X)

DAYS = ["DAY 1 · 6/4 (四)", "DAY 2 · 6/5 (五)", "DAY 3 · 6/6 (六)"]
SLOTS = ["上午", "中午", "下午", "晚上"]


def gen_id(prefix=""):
    return f"{prefix}{random.randint(10**12, 10**13-1):x}"


def rect(x, y, w, h, color, text_id=None, stroke="#1e1e1e", roughness=1, fillStyle="solid"):
    e = {
        "id": gen_id("r_"),
        "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": color,
        "fillStyle": fillStyle,
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": roughness,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": random.randint(1, 10**9),
        "version": 1,
        "versionNonce": random.randint(1, 10**9),
        "isDeleted": False,
        "boundElements": [{"type": "text", "id": text_id}] if text_id else None,
        "updated": NOW,
        "link": None,
        "locked": False,
    }
    return e


def text_el(x, y, w, h, content, container_id=None, size=14, align="center", color="#1e1e1e", bold=False):
    e = {
        "id": gen_id("t_"),
        "type": "text",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0,
        "strokeColor": color,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": random.randint(1, 10**9),
        "version": 1,
        "versionNonce": random.randint(1, 10**9),
        "isDeleted": False,
        "boundElements": None,
        "updated": NOW,
        "link": None,
        "locked": False,
        "text": content,
        "fontSize": size,
        "fontFamily": 5,  # Excalifont (rough hand)
        "textAlign": align,
        "verticalAlign": "middle",
        "containerId": container_id,
        "originalText": content,
        "lineHeight": 1.25,
    }
    return e


def make_card(x, y, w, h, color, content):
    """Make a sticky-note style card (rect + bound text)."""
    text_id = gen_id("t_")
    r = rect(x, y, w, h, color, text_id=text_id)
    t = text_el(x + 5, y + 5, w - 10, h - 10, content, container_id=r["id"], size=14)
    t["id"] = text_id
    return [r, t]


def make_label(x, y, w, h, content, size=22, bold=False, color="#1e1e1e"):
    """Standalone text label (no container)."""
    t = text_el(x, y, w, h, content, container_id=None, size=size, color=color)
    return t


elements = []

# ── 標題列
elements.append(make_label(
    20, 20, 2800, 50,
    "🇰🇷 Mandy × 雅雅 · 6/4-6/6 首爾行程 brainstorm",
    size=32, color="#1971c2"
))
elements.append(make_label(
    20, 75, 2800, 40,
    "← 候選池：從這裡拖卡片到右邊 3 days × 4 時段 grid。鐵錨卡(💉 14:00 醫美等)已固定。配色：黃=食/紫=購/粉=醫美/藍=汗蒸幕/綠=景點/橘=錨點",
    size=14, color="#495057"
))

# ── 候選池標題
elements.append(make_label(POOL_X0, POOL_Y0 - 50, 600, 32, "📋 候選池 (Pool)", size=24, color="#1e1e1e"))

# ── 候選池卡片
for idx, (text, cat) in enumerate(CARDS):
    col = idx % POOL_COLS
    row = idx // POOL_COLS
    x = POOL_X0 + col * (CARD_W + GAP_X)
    y = POOL_Y0 + row * (CARD_H + GAP_Y)
    elements.extend(make_card(x, y, CARD_W, CARD_H, COLORS[cat], text))

# ── 3 Days × 4 時段 Grid
# 標題
elements.append(make_label(GRID_X0, GRID_Y0 - 50, 800, 32, "📅 3 Days × 4 時段 Grid", size=24))

# Day headers
for c, day in enumerate(DAYS):
    x = GRID_X0 + c * (CELL_W + GAP_X) + 80  # +80 because left edge has time labels
    elements.append(make_label(x, GRID_Y0, CELL_W, 30, day, size=18, color="#1971c2"))

# Time row labels + cell containers
for r, slot in enumerate(SLOTS):
    y = GRID_Y0 + 50 + r * (CELL_H + GAP_Y)
    # 左邊時段 label
    elements.append(make_label(GRID_X0, y + CELL_H/2 - 15, 70, 30, slot, size=20, color="#495057"))
    # 每個 cell 的虛線框（讓人知道往哪放）
    for c in range(3):
        x = GRID_X0 + 80 + c * (CELL_W + GAP_X)
        cell_rect = rect(x, y, CELL_W, CELL_H, "#f8f9fa", stroke="#adb5bd", roughness=0)
        cell_rect["strokeStyle"] = "dashed"
        cell_rect["roundness"] = {"type": 3}
        elements.append(cell_rect)

# ── 鐵錨卡（pre-pin 到 grid）
anchor_offset = {}  # 同 cell 多張卡片往下堆
for text, cat, col, row in ANCHORS:
    cell_x = GRID_X0 + 80 + col * (CELL_W + GAP_X)
    cell_y = GRID_Y0 + 50 + row * (CELL_H + GAP_Y)
    # offset within cell
    key = (col, row)
    n = anchor_offset.get(key, 0)
    x = cell_x + 10
    y = cell_y + 10 + n * (CARD_H + 10)
    elements.extend(make_card(x, y, CELL_W - 20, CARD_H, COLORS[cat], text))
    anchor_offset[key] = n + 1

# ── 底部說明區
NOTES_Y = max(POOL_Y0 + 6 * (CARD_H + GAP_Y), GRID_Y0 + 50 + 4 * (CELL_H + GAP_Y)) + 60
elements.append(make_label(
    20, NOTES_Y, 2800, 30,
    "💬 討論區（雅雅可在這邊加 sticky / 註解）",
    size=20, color="#1971c2"
))
# 一個大空白框讓他們寫
discuss = rect(20, NOTES_Y + 40, 2800, 250, "#fff9db", stroke="#fab005", roughness=0)
discuss["strokeStyle"] = "dashed"
elements.append(discuss)

# ── 組裝 .excalidraw 檔
doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {
        "gridSize": 20,
        "gridStep": 5,
        "gridModeEnabled": False,
        "viewBackgroundColor": "#ffffff",
    },
    "files": {},
}

OUT = "itinerary-canvas.excalidraw"
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)

print(f"✅ Wrote {OUT}")
print(f"   {len(elements)} elements / {len(CARDS)} pool cards / {len(ANCHORS)} anchors")
print(f"   Import: https://excalidraw.com → Menu → Open → 選 {OUT}")
