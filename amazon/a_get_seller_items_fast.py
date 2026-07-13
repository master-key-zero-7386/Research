# ======================================================
# ファイル名: amazon/a_get_seller_items_fast.py
# 目的: ASIN取得（高速版）
#
# a_get_seller_items.py（Selenium・実ブラウザ版）とは別の取得方式。
# requestsで直接Amazonの検索結果HTMLを取得して解析するため、ブラウザを
# 起動しない分、大幅に高速。ただし以下は非対応：
#   - カテゴリー絞り込み（絞り込みメニューの探索がSeleniumの対話操作前提のため）
#   - 「配送先(Deliver to)」の確認バナー（実ブラウザのログイン済みプロフィールを
#     使わないため、Amazon側のデフォルト表示になる）
# =======================================================

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import csv
import json
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from utils.config_loader import cfg, get_debug_mode
from amazon.brand_master import get_conn as get_brand_conn, save_brand_id

AMAZON_DOMAIN = {
    "au": "www.amazon.com.au",
    "us": "www.amazon.com",
    "ca": "www.amazon.ca",
    "jp": "www.amazon.co.jp",
}

# ✅ ゴミASIN除外用キーワード（a_get_seller_items.pyと同じ判定基準）
SPONSORED_KEYWORDS = ["sponsored", "スポンサー"]
BESTSELLER_KEYWORDS = ["best seller", "ベストセラー"]
OVERALL_PICK_KEYWORDS = ["overall pick", "amazon's choice", "amazonのおすすめ"]

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_junk_reason(product):
    """商品カードがスポンサー枠・ベストセラー等のバッジ付きかどうかを判定する。
    ゴミなら除外理由の文字列を、正常な商品なら None を返す。"""

    if product.get("data-component-type") == "sp-sponsored-result":
        return "sponsored(data-component-type)"

    badge_texts = []
    for selector in ("span.a-color-secondary", "span.a-badge-text"):
        for el in product.select(selector):
            text = el.get_text(strip=True)
            if text:
                badge_texts.append(text)

    joined = " / ".join(badge_texts).lower()

    for kw in SPONSORED_KEYWORDS:
        if kw in joined:
            return f"sponsored(badge:{kw})"
    for kw in BESTSELLER_KEYWORDS:
        if kw in joined:
            return f"bestseller(badge:{kw})"
    for kw in OVERALL_PICK_KEYWORDS:
        if kw in joined:
            return f"overall_pick(badge:{kw})"

    return None


def get_brand_id_http(session, domain, marketplace, brand_name):
    """ブランドIDをDBキャッシュから取得。無ければrequestsでライブ検索して取得・保存する。"""
    conn = get_brand_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT brand_id FROM brand_master
        WHERE marketplace = ? AND LOWER(brand_name)=LOWER(?)
        LIMIT 1
    """, (marketplace, brand_name))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["brand_id"]

    resp = session.get(f"https://{domain}/s?k={quote(brand_name)}", timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    for li in soup.select('li[id^="p_123/"]'):
        text = li.get_text(strip=True)
        if text.lower() == brand_name.lower():
            brand_id = li.get("id").split("/")[1]
            save_brand_id(marketplace, brand_name, brand_id)
            return brand_id

    return None


if get_debug_mode():
    print("✅ a_get_seller_items_fast.py が起動されました！")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

config_path = os.path.join(BASE_DIR, "config", "config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

# 引数受取：8個
# 0:seller_id 1:brand_filter 2:min_price 3:max_price 4:step_price
# 5:country_code 6:remarks 7:shop_name
args = sys.argv[1:]

if len(args) < 6:
    if get_debug_mode():
        print("❌ 引数が不足しています")
    sys.exit(1)

seller_id = args[0].strip()
brand_filter = args[1].strip()

min_price = float(args[2].strip() or 0)
max_price = float(args[3].strip() or float("inf"))
step = float(args[4].strip() or 0)

country_code = args[5].strip().lower()
remarks = args[6].strip() if len(args) > 6 else "未入力"
shop_name = args[7].strip() if len(args) > 7 else "Unknown"

amazon_domain = AMAZON_DOMAIN[country_code]

output_folder = config.get("output_path")
if not output_folder:
    raw_data_dir = config.get("data_dir", "data")
    output_folder = os.path.abspath(os.path.join(BASE_DIR, raw_data_dir))
else:
    output_folder = os.path.abspath(output_folder)

output_folder = os.path.join(output_folder, country_code)

log_dir = os.path.join(BASE_DIR, config.get("log_dir", "log"))
os.makedirs(log_dir, exist_ok=True)

log_path = os.path.join(log_dir, f"log_{country_code}_get_seller_items.txt")

jst_now = datetime.utcnow() + timedelta(hours=9)
with open(log_path, "w", encoding="utf-8") as log:
    log.write(f"【{country_code.upper()}版ログ（高速版）】{jst_now.strftime('%Y-%m-%d %H:%M:%S')} JST\n")

# ✅ Research画面に価格帯ごとの取得状況を表示するための状態ファイル
# （Selenium版と同じファイルを共有。同時に両方は実行しない前提）
status_path = os.path.join(log_dir, f"status_{country_code}.json")
status_bands = []


def write_status(running):
    try:
        now_jst = datetime.utcnow() + timedelta(hours=9)
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump({
                "seller_id": seller_id,
                "region": country_code,
                "step_price": step,
                "running": running,
                "method": "fast",
                "updated_at": now_jst.strftime("%Y-%m-%d %H:%M:%S"),
                "bands": status_bands
            }, f, ensure_ascii=False)
    except Exception:
        pass


write_status(running=True)

session = requests.Session()
session.headers.update(REQUEST_HEADERS)

if brand_filter:
    brand_id = get_brand_id_http(session, amazon_domain, country_code, brand_filter)
else:
    brand_id = None

current_min = min_price
while current_min < max_price:
    current_max = min(current_min + step, max_price)

    rh = [f"p_36:{int(current_min*100)}-{int(current_max*100)}"]
    if brand_id:
        rh.append(f"p_123:{brand_id}")
    price_filter = "&rh=" + ",".join(rh)

    me_param = f"me={seller_id}&" if seller_id and "すべて" not in seller_id else ""
    base_url = f"https://{amazon_domain}/s?{me_param}"
    if brand_filter:
        base_url += f"&k={quote(brand_filter)}"
    base_url += price_filter

    if get_debug_mode():
        print(f"▶ URL: {base_url}")

    items = []
    seen_asins = set()
    page = 1
    while page <= 20:
        try:
            resp = session.get(f"{base_url}&page={page}", timeout=15)
        except Exception as e:
            if get_debug_mode():
                print(f"❌ ページ取得失敗 page={page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        products = soup.select("div.s-main-slot div[data-asin]")
        products = [p for p in products if p.get("data-asin")]

        if not products:
            break

        # ✅ 同じASINに複数のDOM要素がヒットすることがあるため（カートに入れるオーバーレイ等）
        # ASINごとにグループ化し、実際の商品カード（s-search-result）を優先して1件だけ判定する
        candidates_by_asin = {}
        for product in products:
            asin = product.get("data-asin")
            candidates_by_asin.setdefault(asin, []).append(product)

        page_had_new = False
        for asin, candidates in candidates_by_asin.items():
            if asin in seen_asins:
                continue

            product = next(
                (c for c in candidates if c.get("data-component-type") == "s-search-result"),
                candidates[0]
            )

            junk_reason = get_junk_reason(product)
            if junk_reason:
                if get_debug_mode():
                    print(f"⏭ [filter] 除外: asin={asin} reason={junk_reason}")
                continue

            seen_asins.add(asin)
            page_had_new = True

            title_el = product.select_one("h2 span")
            title = title_el.get_text(strip=True) if title_el else ""

            link_el = product.select_one("a.a-link-normal.s-underline-text")
            url = link_el.get("href") if link_el else ""
            if url and url.startswith("/"):
                url = f"https://{amazon_domain}{url}"

            brand_el = product.select_one("a.a-size-base.a-text-bold")
            brand = brand_el.get_text(strip=True) if brand_el else ""

            # ✅ 通貨によっては a-price-whole / a-price-fraction に分かれていない
            # （JPYなど小数を使わない通貨は fraction が存在しない）ため、
            # 読み上げ用の完全な価格文字列を持つ a-offscreen から数値を取り出す
            price = ""
            price_offscreen_el = product.select_one("span.a-price .a-offscreen")
            if price_offscreen_el:
                match = re.search(r"[\d][\d,]*\.?\d*", price_offscreen_el.get_text(strip=True))
                if match:
                    try:
                        price = float(match.group(0).replace(",", ""))
                    except ValueError:
                        price = ""

            items.append([asin, brand, price, url, title])

        if not page_had_new and page > 1:
            # このページで新規ASINが1件も取れなかった＝実質的に末尾に到達
            break

        page += 1
        time.sleep(0.3)  # Amazon側への配慮として最低限の間隔だけ空ける

    # ✅ 20ページ目まで到達した場合、Amazon側の上限（約300件前後）で
    # 打ち切られた可能性が高い＝この価格帯にはまだASINが残っている
    hit_page_cap = page > 20

    os.makedirs(output_folder, exist_ok=True)
    price_range = f"{int(current_min)}-{int(current_max)}"
    brand_part = brand_filter.lower() if brand_filter else "all"

    now_jst = datetime.utcnow() + timedelta(hours=9)
    timestamp = now_jst.strftime("%Y%m%d_%H%M")
    cap_suffix = "_CAPPED要再取得" if hit_page_cap else ""
    filename = f"{country_code.upper()}_{timestamp}_{seller_id}_all_{brand_part}_{price_range}_FAST{cap_suffix}.csv"
    csv_path = os.path.join(output_folder, filename)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ASIN", "Brand", "Price", "URL", "Title"])
        writer.writerows(items)

    if get_debug_mode():
        print(f"✅ {filename} 出力完了（{len(items)}件）")

    if hit_page_cap:
        warning = (
            f"⚠ [cap] price_range={price_range} で20ページ上限に到達しました"
            f"（取得件数={len(items)}件）。この価格帯はまだASINが残っている可能性があります。"
            f" ステップ幅をさらに狭めて再取得してください。"
        )
        print(warning)
        try:
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(warning + "\n")
        except Exception:
            pass

    status_bands.append({
        "range": price_range,
        "count": len(items),
        "capped": hit_page_cap
    })
    write_status(running=True)

    current_min = current_max

write_status(running=False)
