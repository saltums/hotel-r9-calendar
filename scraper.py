#!/usr/bin/env python3
"""
Trivago price scraper — HOTEL R9 The Yard いなべ
ホテルID: 27992002

GitHub Actions から実行し prices.json を自動更新します。
最安値と最安サイトへの直リンクを取得します。
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────
HOTEL_ID   = "27992002"
HOTEL_SLUG = (
    "%E3%83%9B%E3%83%86%E3%83%AB-%EF%BD%88%EF%BD%8F%EF%BD%94%EF%BD%85%EF%BD%8C"
    "-%EF%BD%92-%EF%BD%94%EF%BD%88%EF%BD%85-%EF%BD%99%EF%BD%81%EF%BD%92%EF%BD%84"
    "-%E3%81%84%E3%81%AA%E3%81%B9-%E3%81%84%E3%81%AA%E3%81%B9%E5%B8%82"
)
DAYS       = 60
OUTPUT     = Path(__file__).parent / "prices.json"
JST        = timezone(timedelta(hours=9))


def trivago_url(date: datetime) -> str:
    nxt = date + timedelta(days=1)
    fmt = lambda d: d.strftime("%Y%m%d")
    return (
        f"https://www.trivago.jp/ja/lm/{HOTEL_SLUG}"
        f"?search=100-{HOTEL_ID};dr-{fmt(date)}-{fmt(nxt)}"
    )


def extract_price(text: str) -> int | None:
    """ページテキストから最初の妥当なホテル価格を抽出する"""
    for m in re.finditer(r"[￥¥]([\d,]+)", text):
        price = int(m.group(1).replace(",", ""))
        if 3_000 <= price <= 50_000:
            return price
    return None


def scrape_date(page, date: datetime) -> dict:
    """
    1日分の価格と最安サイトURLを取得する。
    戻り値: { price, cheapestUrl, cheapestSource }
    """
    url = trivago_url(date)
    result = {"price": None, "cheapestUrl": url, "cheapestSource": None}

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(2_000)

        # ── Step 1: 最低価格をページテキストから取得 ──────
        text  = page.inner_text("body")
        price = extract_price(text)
        result["price"] = price

        # ── Step 2: 「料金を表示」ボタンをクリックして最安サイトを探す ──
        try:
            show_btn = page.locator(
                'button:has-text("料金を表示"), '
                '[data-qa*="show-rate"], '
                '[class*="showRate"], '
                'a:has-text("料金を表示")'
            ).first()

            if show_btn.is_visible(timeout=4_000):
                show_btn.click()
                page.wait_for_timeout(2_500)

                # 最安エントリの外部リンクを取得
                deal_selectors = [
                    '[data-qa="deal"] a[href]',
                    '[class*="deal"] a[href]',
                    '[class*="rate"] a[href]',
                    '[class*="booking"] a[href]',
                    'a[class*="CTA"], a[class*="cta"]',
                ]
                for sel in deal_selectors:
                    links = page.locator(sel)
                    if links.count() > 0:
                        href = links.first().get_attribute("href")
                        if href and href.startswith("http"):
                            result["cheapestUrl"] = href
                            break

                # プロバイダー名
                provider_sel = [
                    '[data-qa="provider-name"]',
                    '[class*="providerName"]',
                    '[class*="provider-name"]',
                    '[class*="BookingProvider"]',
                ]
                for sel in provider_sel:
                    el = page.locator(sel).first()
                    if el.is_visible(timeout=1_000):
                        src = el.text_content().strip()
                        if src:
                            result["cheapestSource"] = src
                            break

        except Exception as btn_err:
            # 「料金を表示」が見つからなくても price は取得済みなので続行
            pass

    except Exception as e:
        print(f"  WARN: {e}")

    return result


def scrape_all() -> dict:
    from playwright.sync_api import sync_playwright

    today  = datetime.now(JST).replace(hour=0, minute=0, second=0, microsecond=0)
    prices: dict = {}

    # 既存データを読み込み
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
            prices   = existing.get("prices", {})
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
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
            timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 800},
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )

        page = ctx.new_page()

        for i in range(DAYS):
            date     = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            print(f"[{i+1:02d}/{DAYS}] {date_str} …", end=" ", flush=True)

            data = scrape_date(page, date)
            prices[date_str] = data

            p_str = f"¥{data['price']:,}" if data["price"] else "N/A"
            s_str = f" / {data['cheapestSource']}" if data.get("cheapestSource") else ""
            print(f"{p_str}{s_str}")

            _save(prices)

            if i < DAYS - 1:
                page.wait_for_timeout(1_500)

        browser.close()

    return prices


def _save(prices: dict) -> None:
    data = {
        "hotelName":   "HOTEL R9 The Yard いなべ",
        "hotelId":     HOTEL_ID,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "prices":      prices,
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    print(f"=== 開始 {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')} JST ===")
    prices = scrape_all()
    _save(prices)

    valid = {d: v for d, v in prices.items() if isinstance(v, dict) and v.get("price")}
    print(f"\n完了: {len(prices)}日分 / 価格取得済み {len(valid)}日")
    if valid:
        cheapest_date = min(valid, key=lambda k: valid[k]["price"])
        print(f"最安値: ¥{valid[cheapest_date]['price']:,} ({cheapest_date})")


if __name__ == "__main__":
    main()
