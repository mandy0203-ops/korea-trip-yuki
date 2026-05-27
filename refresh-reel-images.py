#!/usr/bin/env python3
"""
refresh-reel-images.py
═══════════════════════════════════════════════════════════════
Korea Trip Yuki — Reel 卡片圖片永久化腳本
═══════════════════════════════════════════════════════════════

【問題根因】
Instagram/Threads CDN URL 帶有簽名 token (oe= 到期時間戳)，
通常 7 天內失效。直接把這些 URL 寫進 HTML = 技術債。

【解法】
本腳本把圖片下載並上傳到 GitHub repo → jsDelivr CDN，
取得永久不過期的 URL，並自動更新 HTML 的 src。

【使用方式】
  python3 refresh-reel-images.py

【首次執行注意】
  需要在彈出的 Chromium 視窗中登入 Threads/Instagram，
  登入後腳本自動繼續。Session 會存在 /tmp/reel-auth-session/。

【環境需求】
  pip install playwright
  playwright install chromium

【腳本版本】2026-05-27
"""

import re
import os
import sys
import json
import time
import base64
import hashlib
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

# ── 設定 ──────────────────────────────────────────────────────
HTML_SRC   = Path(__file__).parent.parent / "tars-001" / "korea-trip-yuki.html"
ASSETS_DIR = Path("/tmp/reel-img-refresh")
SESSION_DIR = Path("/tmp/reel-auth-session")
GH_REPO    = "mandy0203-ops/korea-trip-yuki"
GH_ASSET_PREFIX = "assets"
JSDELIVR_BASE   = f"https://cdn.jsdelivr.net/gh/{GH_REPO}@main/{GH_ASSET_PREFIX}"
SKIP_IF_ALREADY_HOSTED = True  # 已是 jsdelivr URL 的跳過

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def log(msg, emoji=""):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji} {msg}")


def is_cdn_expired(url: str) -> bool:
    """嘗試 HEAD request，403/200 判斷"""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status != 200
    except Exception:
        return True  # 403 / timeout → 當作過期


def upload_to_github(local_path: Path, remote_filename: str) -> str | None:
    """上傳到 GitHub repo，回傳 jsDelivr URL"""
    github_path = f"{GH_ASSET_PREFIX}/{remote_filename}"

    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    # 檢查是否已存在（取 SHA）
    check = subprocess.run(
        ["gh", "api", f"/repos/{GH_REPO}/contents/{github_path}", "--jq", ".sha"],
        capture_output=True, text=True
    )
    sha = check.stdout.strip()

    payload = {"message": f"reel img: {remote_filename}", "content": content_b64}
    if sha:
        payload["sha"] = sha

    result = subprocess.run(
        ["gh", "api", "-X", "PUT", f"/repos/{GH_REPO}/contents/{github_path}", "--input", "-"],
        input=json.dumps(payload),
        capture_output=True, text=True
    )

    if result.returncode == 0:
        return f"{JSDELIVR_BASE}/{remote_filename}"
    else:
        log(f"Upload failed: {result.stderr[:120]}", "❌")
        return None


def extract_post_img_pairs(html: str) -> list[dict]:
    """從 HTML 提取每張 reel card 的 (post_url, img_src, img_fname)"""
    card_pattern = re.compile(
        r"window\.open\('([^']+)','_blank'\).*?"
        r'src="([^"]+cdninstagram[^"]+|[^"]+fbcdn\.net[^"]+|[^"]+scontent[^"]+|[^"]+jsdelivr[^"]+)"',
        re.DOTALL
    )
    pairs = []
    for m in card_pattern.finditer(html):
        post_url = m.group(1)
        img_src  = m.group(2)
        fname_m  = re.search(r'/([^/?]+\.jpg)', img_src)
        fname    = fname_m.group(1) if fname_m else hashlib.md5(img_src.encode()).hexdigest()[:12] + ".jpg"
        pairs.append({"post_url": post_url, "img_src": img_src, "fname": fname})
    return pairs


def fetch_image_url_via_playwright(post_url: str) -> str | None:
    """用 Playwright 開啟貼文頁面，從 network requests 抓圖片 CDN URL"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        log(f"瀏覽器啟動 → {post_url[:60]}...", "🌐")

        ctx = p.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=True,
            args=["--disable-web-security", "--no-sandbox"],
        )
        page = ctx.new_page()

        captured = []

        def on_response(response):
            url = response.url
            if (
                "t51.82787-15" in url
                and "scontent" in url
                and response.status == 200
            ):
                captured.append(url)

        page.on("response", on_response)

        try:
            page.goto(post_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)  # 等圖片載入完成
        except Exception as e:
            log(f"頁面載入失敗: {e}", "⚠️")
        finally:
            ctx.close()

        if not captured:
            return None

        # 優先找 CAROUSEL_ITEM 或較大解析度的
        # 排除 profile pic (t51.2885-19)
        post_imgs = [
            u for u in captured
            if "t51.82787-15" in u
        ]

        if not post_imgs:
            return None

        # 選最大的（通常 stp 裡沒有 s320x320 的才是原圖）
        best = None
        for u in post_imgs:
            if "s320x320" not in u and "s150x150" not in u:
                best = u
                break
        if not best:
            best = post_imgs[0]

        return best


def run_headless_fetch(post_url: str, out_path: Path) -> bool:
    """嘗試用 Playwright 抓圖，下載到 out_path"""
    cdn_url = fetch_image_url_via_playwright(post_url)
    if not cdn_url:
        log(f"Playwright 未能抓到圖片", "❌")
        return False

    log(f"抓到 CDN URL: {cdn_url[:80]}...", "🔗")

    try:
        req = urllib.request.Request(cdn_url)
        req.add_header("User-Agent", "Mozilla/5.0 AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=20) as r:
            with open(out_path, "wb") as f:
                f.write(r.read())
        size = out_path.stat().st_size
        if size < 5000:
            log(f"圖片太小 ({size}b)，可能是錯誤頁", "⚠️")
            return False
        log(f"下載成功 {size//1024}KB", "📥")
        return True
    except Exception as e:
        log(f"下載失敗: {e}", "❌")
        return False


def main():
    log("Korea Trip 圖片永久化腳本啟動", "🚀")

    # 讀 HTML
    html = HTML_SRC.read_text(encoding="utf-8")
    pairs = extract_post_img_pairs(html)
    log(f"找到 {len(pairs)} 張 reel card 圖片", "📋")

    updated = 0
    skipped = 0
    failed  = 0

    for i, item in enumerate(pairs, 1):
        post_url = item["post_url"]
        img_src  = item["img_src"]
        fname    = item["fname"]
        log_prefix = f"[{i:02d}/{len(pairs)}] {fname[:45]}"

        # 已是 jsDelivr / GitHub 永久 URL？
        if SKIP_IF_ALREADY_HOSTED and "jsdelivr.net" in img_src:
            log(f"{log_prefix} → 已是永久 URL，跳過", "✅")
            skipped += 1
            continue

        # 嘗試直接 curl（若 CDN URL 仍有效）
        local_path = ASSETS_DIR / f"{i:02d}_{fname}"
        if not is_cdn_expired(img_src):
            log(f"{log_prefix} → CDN 仍有效，直接下載", "⚡")
            try:
                req = urllib.request.Request(img_src)
                req.add_header("User-Agent", "Mozilla/5.0 AppleWebKit/537.36")
                with urllib.request.urlopen(req, timeout=20) as r:
                    local_path.write_bytes(r.read())
                dl_ok = local_path.stat().st_size > 5000
            except Exception:
                dl_ok = False

            if not dl_ok:
                log(f"{log_prefix} → 直接下載失敗，改用 Playwright", "🔄")
                dl_ok = run_headless_fetch(post_url, local_path)
        else:
            log(f"{log_prefix} → CDN 已過期，用 Playwright 重抓", "⏰")
            dl_ok = run_headless_fetch(post_url, local_path)

        if not dl_ok:
            log(f"{log_prefix} → 圖片無法取得，保留現有 URL", "⚠️")
            failed += 1
            continue

        # 上傳到 GitHub
        new_url = upload_to_github(local_path, fname)
        if not new_url:
            failed += 1
            continue

        # 更新 HTML
        html = html.replace(img_src, new_url)
        log(f"{log_prefix} → 永久 URL：{new_url[:70]}", "🎉")
        updated += 1
        time.sleep(0.5)  # 避免 GitHub API rate limit

    # 寫回 HTML
    HTML_SRC.write_text(html, encoding="utf-8")
    log(f"\n{'='*50}", "")
    log(f"完成！更新 {updated} 張 ｜ 跳過 {skipped} 張 ｜ 失敗 {failed} 張", "📊")
    log(f"請執行 sync.py 推上 GitHub Pages", "📤")

    # 自動 sync
    if updated > 0:
        log("自動執行 sync.py...", "🔄")
        sync_py = Path(__file__).parent / "sync.py"
        subprocess.run(
            [sys.executable, str(sync_py), f"refresh-reel-images: {updated} 張永久化"],
            cwd=str(Path(__file__).parent)
        )


if __name__ == "__main__":
    main()
