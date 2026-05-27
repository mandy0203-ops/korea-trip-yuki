#!/usr/bin/env python3
"""
refresh-reel-images.py  v2
═══════════════════════════════════════════════════════════════
Korea Trip Yuki — Reel 卡片圖片永久化腳本
═══════════════════════════════════════════════════════════════

【用法】
  python3 refresh-reel-images.py

【流程】
  1. 讀 HTML，找出所有還是 IG/Threads CDN URL 的 reel 卡圖片
  2. 彈出 Chromium 視窗 → 第一次需要登入 Threads（30 秒內登入）
  3. 對每張失效圖：開新分頁 → 打開 Threads 貼文 → 抓 CDN URL → 下載
  4. 上傳到 GitHub (mandy0203-ops/korea-trip-yuki/assets/)
  5. 更新 HTML src → jsDelivr 永久 URL
  6. 自動 sync.py push 上線

【環境需求】
  pip install playwright && playwright install chromium
"""

import re, os, sys, json, time, base64, hashlib, subprocess, urllib.request
from pathlib import Path
from datetime import datetime

# ── 設定 ──────────────────────────────────────────────────────
HTML_SRC    = Path(__file__).parent.parent / "tars-001" / "korea-trip-yuki.html"
ASSETS_DIR  = Path("/tmp/reel-img-refresh")
SESSION_DIR = Path("/tmp/reel-auth-session")
GH_REPO     = "mandy0203-ops/korea-trip-yuki"
ASSET_PREFIX = "assets"
JSDELIVR_BASE = f"https://cdn.jsdelivr.net/gh/{GH_REPO}@main/{ASSET_PREFIX}"
SKIP_HOSTED  = True   # 已是 jsDelivr URL 的跳過

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def log(msg, emoji=""):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {emoji} {msg}")


def is_cdn_expired(url: str) -> bool:
    """HEAD request 判斷 CDN URL 是否仍有效"""
    if "jsdelivr" in url or "raw.githubusercontent" in url:
        return False   # 永久 URL
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status != 200
    except Exception:
        return True


def upload_to_github(local_path: Path, remote_filename: str) -> str | None:
    """上傳到 GitHub repo，回傳 jsDelivr URL"""
    github_path = f"{ASSET_PREFIX}/{remote_filename}"
    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

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
        input=json.dumps(payload), capture_output=True, text=True
    )
    if result.returncode == 0:
        return f"{JSDELIVR_BASE}/{remote_filename}"
    log(f"Upload failed: {result.stderr[:120]}", "❌")
    return None


def extract_pairs(html: str) -> list[dict]:
    """提取每張 reel card 的 (post_url, img_src, fname)"""
    pat = re.compile(
        r"window\.open\('([^']+)','_blank'\).*?"
        r'src="([^"]*(?:cdninstagram|fbcdn\.net|scontent|jsdelivr)[^"]*)"',
        re.DOTALL
    )
    pairs = []
    for m in pat.finditer(html):
        post_url, img_src = m.group(1), m.group(2)
        fm = re.search(r'/([^/?]+\.jpg)', img_src)
        fname = fm.group(1) if fm else hashlib.md5(img_src.encode()).hexdigest()[:16] + ".jpg"
        pairs.append({"post_url": post_url, "img_src": img_src, "fname": fname})
    return pairs


def pick_best_img(urls: list[str]) -> str | None:
    """從 network 抓到的 CDN URL 清單選出最佳貼文圖片"""
    # 過濾：只要 t51.82787-15（貼文圖），排除 profile pic（t51.2885-19 / t51.82787-19）
    post_imgs = [u for u in urls if "t51.82787-15" in u and "scontent" in u]
    if not post_imgs:
        return None

    # 優先選 CAROUSEL_ITEM / 無縮圖限制的版本
    priority = [u for u in post_imgs if "s320x320" not in u and "s150x150" not in u]
    return (priority or post_imgs)[0]


def fetch_and_download(page, post_url: str, out_path: Path) -> bool:
    """用已開啟的 browser page 抓貼文圖，下載到 out_path"""
    captured = []

    def on_response(response):
        if "t51.82787-15" in response.url and "scontent" in response.url and response.status == 200:
            captured.append(response.url)

    page.on("response", on_response)

    try:
        page.goto(post_url, wait_until="domcontentloaded", timeout=25000)
        # 多等 3 秒讓圖片載入
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        time.sleep(2)
    except Exception as e:
        log(f"頁面導航失敗: {str(e)[:80]}", "⚠️")
    finally:
        page.remove_listener("response", on_response)

    cdn_url = pick_best_img(captured)
    if not cdn_url:
        log("未抓到貼文圖片（可能需要登入或頁面結構變化）", "⚠️")
        return False

    log(f"CDN URL 抓到 ({len(captured)} 個請求中選出)", "🔗")

    try:
        req = urllib.request.Request(cdn_url)
        req.add_header("User-Agent", "Mozilla/5.0 AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        if len(data) < 5000:
            log(f"圖片太小 ({len(data)}b)，略過", "⚠️")
            return False
        out_path.write_bytes(data)
        log(f"下載 {len(data)//1024}KB ✔", "📥")
        return True
    except Exception as e:
        log(f"下載失敗: {e}", "❌")
        return False


def ensure_logged_in(page) -> bool:
    """確認已登入 Threads；若否，等使用者手動登入"""
    log("導航到 Threads 確認登入狀態...", "🔑")
    try:
        page.goto("https://www.threads.com/", timeout=20000)
        # 等待幾秒看 URL 是否停在 login 頁
        time.sleep(3)
        current_url = page.url
        log(f"目前 URL: {current_url[:60]}", "")

        # 若還在 login 相關頁面 → 提示登入
        if any(kw in current_url for kw in ["login", "accounts", "sso"]):
            log("", "")
            log("=" * 55, "")
            log("🔑  請在開啟的瀏覽器視窗中登入 Threads / Instagram", "")
            log("    登入完成後，腳本會自動偵測並繼續（最多等 5 分鐘）", "")
            log("=" * 55, "")

            # 等待 URL 離開 login 頁面
            deadline = time.time() + 300   # 5 分鐘
            while time.time() < deadline:
                time.sleep(2)
                cur = page.url
                if not any(kw in cur for kw in ["login", "accounts", "sso"]):
                    log(f"✅ 登入成功！URL={cur[:50]}", "")
                    return True
            log("登入等待逾時（5 分鐘）", "❌")
            return False
        else:
            log("✅ 已登入", "")
            return True
    except Exception as e:
        log(f"登入確認失敗: {e}", "❌")
        return False


def main():
    from playwright.sync_api import sync_playwright

    log("Korea Trip 圖片永久化腳本 v2 啟動", "🚀")

    html = HTML_SRC.read_text(encoding="utf-8")
    pairs = extract_pairs(html)
    log(f"共 {len(pairs)} 張 reel card 圖", "📋")

    # 過濾出需要處理的（跳過已永久化的）
    to_process = []
    for item in pairs:
        if SKIP_HOSTED and "jsdelivr.net" in item["img_src"]:
            continue
        to_process.append(item)

    log(f"需要處理: {len(to_process)} 張（已永久化 {len(pairs)-len(to_process)} 張跳過）", "📊")

    if not to_process:
        log("全部已永久化，無需處理 ✨", "✅")
        return

    updated = skipped = failed = 0

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=False,
            slow_mo=200,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            ignore_https_errors=True,
        )

        page = ctx.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        })

        # 登入確認（只做一次）
        if not ensure_logged_in(page):
            log("無法確認登入，腳本終止", "❌")
            ctx.close()
            return

        for i, item in enumerate(to_process, 1):
            post_url = item["post_url"]
            img_src  = item["img_src"]
            fname    = item["fname"]
            label    = f"[{i:02d}/{len(to_process)}] {fname[:42]}"

            # 先試直接下載（若 CDN 仍有效）
            local_path = ASSETS_DIR / f"{i:02d}_{fname}"
            if not is_cdn_expired(img_src):
                log(f"{label} → CDN 仍有效，直接下載", "⚡")
                try:
                    req = urllib.request.Request(img_src)
                    req.add_header("User-Agent", "Mozilla/5.0 AppleWebKit/537.36")
                    with urllib.request.urlopen(req, timeout=20) as r:
                        local_path.write_bytes(r.read())
                    dl_ok = local_path.stat().st_size > 5000
                except Exception:
                    dl_ok = False
            else:
                log(f"{label} → CDN 過期，用 Playwright 重抓", "⏰")
                dl_ok = fetch_and_download(page, post_url, local_path)

            if not dl_ok:
                log(f"{label} → 無法取得圖片，略過", "⚠️")
                failed += 1
                continue

            # 上傳 GitHub
            new_url = upload_to_github(local_path, fname)
            if not new_url:
                failed += 1
                continue

            html = html.replace(img_src, new_url)
            log(f"{label} → ✅ 永久化完成", "🎉")
            updated += 1
            time.sleep(0.8)   # 避免 rate limit

        ctx.close()

    # 寫回 HTML
    HTML_SRC.write_text(html, encoding="utf-8")
    log(f"", "")
    log(f"結果：更新 {updated} ｜ 失敗 {failed} ｜ 跳過（已永久）{skipped}", "📊")

    if updated > 0:
        log("執行 sync.py 推上 GitHub Pages...", "🔄")
        sync_py = Path(__file__).parent / "sync.py"
        subprocess.run(
            [sys.executable, str(sync_py), f"refresh-reel-images: {updated}張永久化"],
            cwd=str(Path(__file__).parent)
        )
    else:
        log("無更新，跳過 sync", "ℹ️")


if __name__ == "__main__":
    main()
