#!/usr/bin/env python3
"""
楽天トラベル 空室カレンダースクレイパー
HOTEL R9 The Yard いなべ (ホテルNo.183753)
APIキー不要 — カレンダーページを直接取得
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

HOTEL_NO  = "183753"
CAMP_ID   = "5397574"  # スタンダードプラン（1泊〜）
ROOM_TYPE = "double"
DAYS      = 60
OUTPUT    = Path(__file__).parent / "prices.json"
JST       = timezone(timedelta(hours=9))

CALENDAR_URL = "https://hotel.travel.rakuten.co.jp/hotelinfo/plan/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Referer": "https://travel.rakuten.co.jp/",
}


def booking_url(date_str: str) -> str:
    d = date_str.replace("-", "")  # YYYYMMDD
    return (
        f"https://hotel.travel.rakuten.co.jp/hotelinfo/plan/"
        f"?f_no={HOTEL_NO}&f_hizuke={d}"
        f"&f_camp_id={CAMP_ID}&f_otona_su=1&f_syu={ROOM_TYPE}&f_heya_su=1"
    )


def fetch_month(year: int, month: int) -> dict:
    """指定月のカレンダーページから日付別最低価格を取得"""
    resp = requests.get(
        CALENDAR_URL,
        params={
            "f_no":      HOTEL_NO,
            "f_flg":     "PLAN",
            "f_heya_su": "1",
            "f_camp_id": CAMP_ID,
            "f_syu":     ROOM_TYPE,
            "f_hizuke":  f"{year}{month:02d}01",
            "f_otona_su": "1",
            "f_thick":   "1",
            "TB_iframe": "true",
        },
        headers=HEADERS,
        timeout=15,
    )

    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}")
        return {}

    return parse_prices(resp.text, year, month)


def parse_prices(html: str, year: int, month: int) -> dict:
    """HTMLのカレンダーセルから {YYYY-MM-DD: price} を抽出"""
    prices = {}

    for td_html in re.findall(r"<td[^>]*>(.*?)</td>", html, re.DOTALL):
        # 当月の日付セル (class="thisMonth") だけを対象にする
        day_m = re.search(r'class="thisMonth"[^>]*>(\d{1,2})<', td_html)
        if not day_m:
            continue
        day = int(day_m.group(1))

        # 価格を探す（カンマ区切りの数字、1,000〜99,999の範囲）
        # HTMLタグを除いたテキストから抽出
        text = re.sub(r"<[^>]+>", " ", td_html)
        price_m = re.search(r"\b(\d{1,2},\d{3})\b", text)
        if not price_m:
            continue

        price = int(price_m.group(1).replace(",", ""))
        if 1_000 <= price <= 99_999:
            key = f"{year}-{month:02d}-{day:02d}"
            # より安い価格を優先
            if key not in prices or price < prices[key]:
                prices[key] = price

    return prices


def save(prices: dict) -> None:
    OUTPUT.write_text(
        json.dumps(
            {
                "hotelName":   "HOTEL R9 The Yard いなべ",
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
                "prices":      prices,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    print(f"=== 開始 {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')} JST ===")
    print(f"楽天トラベル 空室カレンダー直接スクレイピング (ホテルNo.{HOTEL_NO})")

    today = datetime.now(JST).replace(hour=0, minute=0, second=0, microsecond=0)

    # 今日から60日をカバーする月を列挙
    months = sorted({
        (today.year + (today.month - 1 + i) // 12,
         (today.month - 1 + i) % 12 + 1)
        for i in range(3)
    })

    # 全月のカレンダーを取得
    all_prices: dict[str, int] = {}
    for year, month in months:
        print(f"\n{year}年{month}月 取得中 …", end=" ", flush=True)
        mp = fetch_month(year, month)
        print(f"{len(mp)}日分")
        all_prices.update(mp)
        time.sleep(1.0)

    # 今日以降60日分をまとめる
    prices_out: dict = {}
    for i in range(DAYS):
        date    = today + timedelta(days=i)
        ds      = date.strftime("%Y-%m-%d")
        price   = all_prices.get(ds)
        print(f"  {ds}: {'¥{:,}'.format(price) if price else '空室なし'}")
        prices_out[ds] = {
            "price":         price,
            "cheapestUrl":   booking_url(ds),
            "cheapestSource": "楽天トラベル",
        }

    save(prices_out)

    valid = {d: v for d, v in prices_out.items() if v["price"]}
    print(f"\n完了: {len(valid)}/{DAYS}日分 価格取得")
    if valid:
        cheapest = min(valid, key=lambda k: valid[k]["price"])
        print(f"最安値: ¥{valid[cheapest]['price']:,} ({cheapest})")


if __name__ == "__main__":
    main()
