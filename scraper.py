#!/usr/bin/env python3
"""
Trivago Playwright スクレイパー
HOTEL R9 The Yard いなべ (hotel ID: 27992002)
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

HOTEL_ID   = "27992002"
HOTEL_SLUG = (
    "%E3%83%9B%E3%83%86%E3%83%AB-%EF%BD%88%EF%BD%8F%EF%BD%94%EF%BD%85%EF%BD%8C"
    "-%EF%BD%92-%EF%BD%94%EF%BD%88%EF%BD%85-%EF%BD%99%EF%BD%81%EF%BD%92%EF%BD%84"
    "-%E3%81%84%E3%81%AA%E3%81%B9-%E3%81%84%E3%81%AA%E3%81%B9%E5%B8%82"
)
DAYS   = 60
OUTPUT = Path(__file__).parent / "prices.json"
JST    = timezone(timedelta(hours=9))


def trivago_url(date_str: str) -> str:
    d   = date_str.replace("-", "")
    d1  = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    return (
        f"https://www.trivago.jp/ja/lm/{HOTEL_SLUG}"
        f"?search=100-{HOTEL_ID};dr-{d}-{d1};drs-40;rc-1-1"
    )


_debug_done = False

def fetch_price(page, date_str: str):
    global _debug_done
    url = trivago_url(date_str)
    try:
        page.goto(url, wait_until="load", timeout=40000)

        # 初回のみデバッグ: ページタイトルと本文冒頭を出力
        if not _debug_done:
            _debug_done = True
            title = page.title()
            body  = page.inner_text("body")[:400].replace("\n", " ")
            print(f"\n  [debug] title: {title}")
            print(f"  [debug] body:  {body}\n")

        # 価格が表示されるまで最大35秒待機
        page.wait_for_selector('[data-testid="recommended-price"]', timeout=35000)
        text = page.locator('[data-testid="recommended-price"]').first.text_content() or ""
        m = re.search(r"[¥￥]([0-9,]+)", text)
        if m:
            price = int(m.group(1).replace(",", ""))
            if 1_000 <= price <= 99_999:
                return price, url
    except PWTimeout:
        print(f"  タイムアウト: {date_str}")
    except Exception as e:
        print(f"  エラー ({date_str}): {e}")
    return None, url


def main():
    print(f"=== 開始 {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')} JST ===")
    today = datetime.now(JST).replace(hour=0, minute=0, second=0, microsecond=0)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ja-JP",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept-Language": "ja-JP,ja;q=0.9",
            },
        )
        # navigator.webdriver を隠す
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = ctx.new_page()

        prices_out: dict = {}
        ok = 0

        for i in range(DAYS):
            date    = today + timedelta(days=i)
            ds      = date.strftime("%Y-%m-%d")
            print(f"  {ds} ...", end=" ", flush=True)

            price, url = fetch_price(page, ds)
            if price:
                print(f"¥{price:,}")
                ok += 1
            else:
                print("空室なし / データなし")

            prices_out[ds] = {
                "price":         price,
                "cheapestUrl":   url,
                "cheapestSource": "Trivago",
            }
            if i < DAYS - 1:
                time.sleep(1.5)

        page.close()
        ctx.close()
        browser.close()

    OUTPUT.write_text(
        json.dumps(
            {
                "hotelName":   "HOTEL R9 The Yard いなべ",
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
                "prices":      prices_out,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n完了: {ok}/{DAYS}日分 価格取得")
    if ok:
        best = min((v["price"], k) for k, v in prices_out.items() if v["price"])
        print(f"最安値: ¥{best[0]:,} ({best[1]})")


if __name__ == "__main__":
    main()
