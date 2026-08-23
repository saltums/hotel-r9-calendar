#!/usr/bin/env python3
"""
楽天トラベルAPI → HOTEL R9 The Yard いなべ price scraper
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_ID  = os.environ.get("RAKUTEN_APP_ID", "")
DAYS    = 60
OUTPUT  = Path(__file__).parent / "prices.json"
JST     = timezone(timedelta(hours=9))

KEYWORD_URL = "https://app.rakuten.co.jp/services/api/Travel/KeywordHotelSearch/20170426"
VACANCY_URL = "https://app.rakuten.co.jp/services/api/Travel/VacantHotelSearch/20170426"


def find_hotel_no() -> str:
    resp = requests.get(KEYWORD_URL, params={
        "applicationId": APP_ID,
        "keyword": "HOTEL R9 The Yard いなべ",
        "format": "json",
        "hits": "10",
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    hotels = data.get("hotels", [])
    if not hotels:
        raise RuntimeError("ホテルが見つかりません。キーワードを確認してください。")

    info = hotels[0]["hotel"][0]["hotelBasicInfo"]
    hotel_no = str(info["hotelNo"])
    print(f"ホテル発見: {info['hotelName']} (No. {hotel_no})")
    return hotel_no


def get_day_price(hotel_no: str, check_in: str, check_out: str) -> dict:
    result = {"price": None, "cheapestUrl": None, "cheapestSource": "楽天トラベル"}

    try:
        resp = requests.get(VACANCY_URL, params={
            "applicationId": APP_ID,
            "hotelNo": hotel_no,
            "checkinDate": check_in,
            "checkoutDate": check_out,
            "adultNum": "1",
            "format": "json",
        }, timeout=15)

        if resp.status_code != 200:
            return result

        data = resp.json()
        hotels = data.get("hotels", [])
        if not hotels:
            return result

        hotel_data = hotels[0]["hotel"]
        basic_info = hotel_data[0]["hotelBasicInfo"]
        result["cheapestUrl"] = (
            basic_info.get("planListUrl") or basic_info.get("hotelSpecialUrl")
        )

        min_price = None
        for section in hotel_data:
            for room in section.get("roomInfo", []):
                rb = room.get("roomBasicInfo", {})
                price = rb.get("roomPrice")
                if price and (min_price is None or price < min_price):
                    min_price = price
                    url = rb.get("reserveUrl")
                    if url:
                        result["cheapestUrl"] = url

        result["price"] = min_price

    except Exception as e:
        print(f"  エラー: {e}")

    return result


def save(prices: dict) -> None:
    data = {
        "hotelName":   "HOTEL R9 The Yard いなべ",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "prices":      prices,
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if not APP_ID:
        print("ERROR: 環境変数 RAKUTEN_APP_ID が設定されていません", file=sys.stderr)
        sys.exit(1)

    print(f"=== 開始 {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')} JST ===")

    hotel_no = find_hotel_no()

    prices: dict = {}
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
            prices = existing.get("prices", {})
        except Exception:
            pass

    today = datetime.now(JST).replace(hour=0, minute=0, second=0, microsecond=0)

    for i in range(DAYS):
        date      = today + timedelta(days=i)
        check_in  = date.strftime("%Y-%m-%d")
        check_out = (date + timedelta(days=1)).strftime("%Y-%m-%d")

        print(f"[{i+1:02d}/{DAYS}] {check_in} …", end=" ", flush=True)

        data = get_day_price(hotel_no, check_in, check_out)
        prices[check_in] = data

        print(f"¥{data['price']:,}" if data["price"] else "空室なし")
        save(prices)

        if i < DAYS - 1:
            time.sleep(0.3)

    valid = {d: v for d, v in prices.items() if v.get("price")}
    print(f"\n完了: {len(prices)}日分 / 価格取得 {len(valid)}日")
    if valid:
        cheapest = min(valid, key=lambda k: valid[k]["price"])
        print(f"最安値: ¥{valid[cheapest]['price']:,} ({cheapest})")


if __name__ == "__main__":
    main()
