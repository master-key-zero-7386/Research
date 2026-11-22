# ======================================================
# ファイル名: amazon/a_get_seller_genre_summary.py
# 目的: セラーIDだけを入力に、そのセラーが出品しているジャンル（Department）
#       と、ジャンルごとの出品件数を調べる（自分用・市場分析機能）。
#
# 「ブランド名一覧を正確に全部出す」機能は、Amazon側にブランド絞り込み欄が
# 無くなった今、全商品を1件ずつスクレイピングするしかなく現実的な時間で
# 終わらない（出品数が多いセラーだと数時間かかる）ため見送った。
# 代わりに「ジャンルごとの件数」だけなら、ジャンルごとに検索結果ページを
# 1回開いて上部の件数表示を読むだけで済むので、商品を1件ずつ見るより
# 大幅に速い（ジャンル数×1ページぶんの読み込みで済む）。
# =======================================================

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import re
import csv
import time
import json
import tempfile
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.config_loader import get_debug_mode
from amazon.category_master import save_category_node_id

AMAZON_DOMAIN = {
    "au": "www.amazon.com.au",
    "us": "www.amazon.com",
    "ca": "www.amazon.ca",
    "jp": "www.amazon.co.jp",
}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

args = sys.argv[1:]
if len(args) < 2:
    if get_debug_mode():
        print("❌ 引数が不足しています（seller_id, country_code が必要）")
    sys.exit(1)

seller_id = args[0].strip()
country_code = args[1].strip().lower()
amazon_domain = AMAZON_DOMAIN[country_code]

raw_data_dir = config.get("data_dir", "data")
output_folder = os.path.abspath(os.path.join(BASE_DIR, raw_data_dir, country_code))
os.makedirs(output_folder, exist_ok=True)

log_dir = os.path.join(BASE_DIR, config.get("log_dir", "log"))
os.makedirs(log_dir, exist_ok=True)

profile_path = os.path.join(
    BASE_DIR,
    config.get(f"chrome_profile_{country_code}", f"Chrome_Profile/{country_code}")
)

status_path = os.path.join(log_dir, f"genre_status_{country_code}.json")


def write_status(running, genres=None, total_count=None, saved_path=None, error=None):
    try:
        now_jst = datetime.utcnow() + timedelta(hours=9)
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump({
                "seller_id": seller_id,
                "region": country_code,
                "running": running,
                "updated_at": now_jst.strftime("%Y-%m-%d %H:%M:%S"),
                "genres": genres or [],
                "total_count": total_count,
                "saved_path": saved_path,
                "error": error,
            }, f, ensure_ascii=False)
    except Exception:
        pass


def _save_debug_screenshot(driver, tag):
    try:
        shot_path = os.path.join(log_dir, f"genre_debug_{country_code}_{tag}.png")
        driver.save_screenshot(shot_path)
        html_path = os.path.join(log_dir, f"genre_debug_{country_code}_{tag}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        if get_debug_mode():
            print(f"▶ [genre] デバッグ情報保存: {shot_path}")
    except Exception as e:
        if get_debug_mode():
            print(f"▶ [genre] デバッグ情報保存失敗: {e}")


def parse_result_count(driver):
    """検索結果ページ上部の「1-16 of over 20,000 results」等から合計件数を読み取る。
    正確なCSSセレクタに依存すると表記ゆれで壊れやすいため、ページ全体のテキストから
    正規表現で拾う（取れなければ None）。"""
    try:
        text = driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return None

    m = re.search(r"of\s+(?:over\s+)?([\d,]+)\s+results", text, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(",", ""))

    # 件数が少ない場合は「1-12 of 12 results」のような表記になることもある
    m = re.search(r"([\d,]+)\s+results", text, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(",", ""))

    return None


def collect_departments(driver):
    """検索結果ページ左側の「Department」絞り込み欄から、このセラーが実際に
    出品しているジャンル名とnode IDを集める。
    （ブランド絞り込み欄(p_123)は無くなったが、Department絞り込み欄(n)は
    brand_master.py の時点のスクリーンショットでもまだ存在が確認できている）"""
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li[id^="n/"]'))
        )
    except Exception:
        return []

    items = driver.find_elements(By.CSS_SELECTOR, 'li[id^="n/"]')

    seen = {}
    for item in items:
        text = item.text.strip()
        name = text.split("\n")[0].strip()
        parts = (item.get_attribute("id") or "").split("/")
        if name and len(parts) > 1 and parts[1] not in seen:
            seen[parts[1]] = name

    return [{"name": name, "node_id": node_id} for node_id, name in seen.items()]


write_status(running=True)

options = Options()
options.add_argument(f"--user-data-dir={profile_path}")
cache_dir = os.path.join(tempfile.gettempdir(), f"chrome_cache_genre_{country_code}")
os.makedirs(cache_dir, exist_ok=True)
options.add_argument(f"--disk-cache-dir={cache_dir}")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

try:
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
except Exception as e:
    write_status(running=False, error=f"Chrome起動失敗: {e}")
    sys.exit(1)

try:
    base_url = f"https://{amazon_domain}/s?me={seller_id}"
    driver.get(base_url)
    time.sleep(2)

    total_count = parse_result_count(driver)
    departments = collect_departments(driver)

    # ✅ ついでに発見したジャンル名→node_idをcategory_master.dbにも保存しておく。
    #    「詳細設定」タブのカテゴリー名欄が、ライブ探索なしでこのnode_idを再利用できるようになる。
    for dept in departments:
        try:
            save_category_node_id(country_code, dept["name"], dept["node_id"])
        except Exception as e:
            if get_debug_mode():
                print(f"▶ [genre] category_master保存失敗: {dept['name']!r} ({e})")

    if not departments:
        _save_debug_screenshot(driver, "no_departments")
        write_status(
            running=False,
            genres=[],
            total_count=total_count,
            error="ジャンル（Department）の絞り込み欄が見つかりませんでした。Amazon側の表示が変わっている可能性があります。"
        )
        driver.quit()
        sys.exit(0)

    genres = []
    for dept in departments:
        node_url = f"https://{amazon_domain}/s?me={seller_id}&rh=n:{dept['node_id']}"
        driver.get(node_url)
        time.sleep(1.5)
        count = parse_result_count(driver)
        genres.append({
            "name": dept["name"],
            "node_id": dept["node_id"],
            "count": count if count is not None else 0,
        })
        # ✅ 途中経過を画面に反映できるよう、1件集計するごとに状態ファイルを更新
        write_status(running=True, genres=sorted(genres, key=lambda g: g["count"], reverse=True), total_count=total_count)

    genres.sort(key=lambda g: g["count"], reverse=True)

    now_jst = datetime.utcnow() + timedelta(hours=9)
    timestamp = now_jst.strftime("%Y%m%d_%H%M%S")
    filename = f"{country_code.upper()}_{timestamp}_{seller_id}_GENRE_SUMMARY.csv"
    csv_path = os.path.join(output_folder, filename)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Department", "NodeID", "件数"])
        for g in genres:
            writer.writerow([g["name"], g["node_id"], g["count"]])

    write_status(running=False, genres=genres, total_count=total_count, saved_path=csv_path)

except Exception as e:
    _save_debug_screenshot(driver, "error")
    write_status(running=False, error=str(e))
finally:
    driver.quit()
