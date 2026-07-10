# ======================================================
# ファイル名: amazon/a_get_seller_items.py
# 目的: ASIN取得
# =======================================================

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import csv
import time
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.config_loader import cfg, get_debug_mode
from amazon.brand_master import get_brand_id
from amazon.category_master import get_category_node_id

AMAZON_DOMAIN = {
    "au": "www.amazon.com.au",
    "us": "www.amazon.com",
    "ca": "www.amazon.ca",
    "jp": "www.amazon.co.jp",
}

if get_debug_mode():
    print("✅ a_get_seller_items.py が起動されました！")

def show_deliver_to_confirmation(driver, confirm_wait, brand_filter):
    # Amazonの画面の中に、確認用の帯（バナー）を表示する
    wait_note = f"{confirm_wait}秒後に自動で続行します" if confirm_wait > 0 else "確認できたら「OK」を押してください"

    banner_script = """
    var banner = document.createElement('div');
    banner.id = 'rt_confirm_banner';
    banner.style.position = 'fixed';
    banner.style.bottom = '0';
    banner.style.left = '0';
    banner.style.width = '100%%';
    banner.style.zIndex = '999999';
    banner.style.background = '#ffcc00';
    banner.style.color = '#000';
    banner.style.fontSize = '18px';
    banner.style.padding = '16px';
    banner.style.textAlign = 'center';
    banner.style.boxShadow = '0 -2px 8px rgba(0,0,0,0.3)';
    banner.innerHTML = '配送先(Deliver to)が販売予定の国になっているか確認してください。<br>%s' +
        '<br><button id="rt_ok_btn" style="margin-top:8px;padding:8px 24px;font-size:16px;">OK</button>' +
        '<button id="rt_cancel_btn" style="margin-top:8px;margin-left:12px;padding:8px 24px;font-size:16px;">キャンセル</button>';
    document.body.appendChild(banner);

    document.getElementById('rt_ok_btn').onclick = function() {
        window.__rt_confirmed = true;
        banner.remove();
    };
    document.getElementById('rt_cancel_btn').onclick = function() {
        window.__rt_cancelled = true;
        banner.remove();
    };
    window.__rt_confirmed = false;
    window.__rt_cancelled = false;
    """ % (wait_note)

    driver.execute_script(banner_script)

    # OKボタンが押されるか、キャンセルが押されるか、指定秒数が経過するまで待つ
    waited = 0
    while True:
        confirmed = driver.execute_script("return window.__rt_confirmed;")
        cancelled = driver.execute_script("return window.__rt_cancelled;")
        if confirmed or cancelled:
            break
        if confirm_wait > 0 and waited >= confirm_wait:
            break
        time.sleep(0.5)
        waited += 0.5

    # バナーが残っていたら消しておく
    driver.execute_script("""
        var b = document.getElementById('rt_confirm_banner');
        if (b) b.remove();
    """)

    # ✅ キャンセルが押されたかどうかを呼び出し元に伝える（True＝続行、False＝中止）
    return not cancelled

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) 

# config読み込み
config_path = os.path.join(BASE_DIR, "config", "config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

# 引数受取：13個受け取る完全版
args = sys.argv[1:]

if len(args) < 11:
    if get_debug_mode():
        print("❌ 引数が不足しています")
    sys.exit(1)

seller_id = args[0].strip()
category_slug = args[1].strip() or "all"
if category_slug in ["すべて（all）", "すべて", "all"]:
    category_slug = "all"

brand_filter = args[2].strip()

min_price = float(args[3].strip() or 0)
max_price = float(args[4].strip() or float("inf"))
step = float(args[5].strip() or 0)

confirm_wait_str = args[6].strip()
if confirm_wait_str == "手動確認" or confirm_wait_str == "":
    confirm_wait = 0
else:
    confirm_wait = int(confirm_wait_str)

if get_debug_mode():
    print(f"✅ .py側で受け取った confirm_wait: {confirm_wait}")

exclude_fba = args[7].strip().lower() == "true"
_ignored_output_folder = args[8].strip()
country_code = args[9].strip().lower()
remarks = args[10].strip() if len(args) > 10 else "未入力"
shop_name = args[11].strip() if len(args) > 11 else "Unknown"
category_filter = args[12].strip() if len(args) > 12 else ""

amazon_domain = AMAZON_DOMAIN[country_code]

# configのoutput_path優先で取得、なければdata_dirから作成
output_folder = config.get("output_path")
if not output_folder:
    raw_data_dir = config.get("data_dir", "data")
    output_folder = os.path.abspath(os.path.join(BASE_DIR, raw_data_dir))
else:
    output_folder = os.path.abspath(output_folder)

output_folder = os.path.join(output_folder, country_code)

log_dir = os.path.join(BASE_DIR, config.get("log_dir", "log"))
profile_path = os.path.join(
    BASE_DIR,
    config.get(
        f"chrome_profile_{country_code}",
        f"Chrome_Profile/{country_code}"
    )
)

os.makedirs(log_dir, exist_ok=True)

log_path = os.path.join(
    log_dir,
    f"log_{country_code}_get_seller_items.txt"
)

jst_now = datetime.utcnow() + timedelta(hours=9)
with open(log_path, "w", encoding="utf-8") as log:
    log.write(f"【{country_code.upper()}版ログ】{jst_now.strftime('%Y-%m-%d %H:%M:%S')} JST\n")

# Chrome初期化
options = Options()
options.add_argument(f"--user-data-dir={profile_path}")
cache_dir = os.path.join(tempfile.gettempdir(), f"chrome_cache_{country_code}")  
os.makedirs(cache_dir, exist_ok=True)  
options.add_argument(f"--disk-cache-dir={cache_dir}")

# ブラウザの起動設定を強化
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
options.add_argument("--remote-debugging-port=9222")

try:
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
except Exception as e:
    print(f"❌ Chrome起動失敗: {e}")
    sys.exit(1)

wait = WebDriverWait(driver, 15)

if brand_filter:
    brand_id = get_brand_id(driver, country_code, brand_filter)
else:
    brand_id = None

if category_filter:
    category_node_id = get_category_node_id(driver, country_code, category_filter, seller_id, brand_filter)
else:
    category_node_id = None

# ステップ分割処理
current_min = min_price
while current_min < max_price:
    current_max = min(current_min + step, max_price)

    rh = [f"p_36:{int(current_min*100)}-{int(current_max*100)}"]

    if brand_id:
        rh.append(f"p_123:{brand_id}")

    if category_node_id:
        rh.append(f"n:{category_node_id}")

    price_filter = "&rh=" + ",".join(rh)
    
    # ✅ seller_id に "すべて" が含まれる場合は me= を含めない
    me_param = f"me={seller_id}&" if seller_id and "すべて" not in seller_id else ""

    base_url = f"https://{amazon_domain}/s?{me_param}"

    if brand_filter:
        base_url += f"&k={brand_filter}"
    if brand_id:
        base_url += f"&rh=p_123:{brand_id}"
    if category_slug and category_slug != "all":
        base_url += f"&i={category_slug}"

    base_url += price_filter
    
    if get_debug_mode():
        print(f"▶ URL: {base_url}")
    driver.get(base_url)
    time.sleep(2)
    
    if current_min == min_price:
        proceed = show_deliver_to_confirmation(driver, confirm_wait, brand_filter)
        if not proceed:
            if get_debug_mode():
                print("❌ ユーザーがキャンセルを押したため処理を中止します")
            driver.quit()
            sys.exit(0)

    items = []
    page = 1
    while page <= 20:
        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.s-main-slot div[data-asin]:not([data-asin=''])")))
            products = driver.find_elements(By.CSS_SELECTOR, "div.s-main-slot div[data-asin]:not([data-asin=''])")

            for product in products:
                # ✅ スポンサーブロック除外（data-component-type方式）
                if product.get_attribute("data-component-type") == "sp-sponsored-result":
                    continue  # ✅ この行を修正

                # ✅ バッジ除外処理
                try:
                    badge1 = product.find_element(By.CSS_SELECTOR, "span.a-color-secondary")
                    if "Sponsored" in badge1.text:
                        continue
                except:
                    pass
                try:
                    badge2 = product.find_element(By.CSS_SELECTOR, "span.a-badge-text")
                    if "Best Seller" in badge2.text:
                        continue
                except:
                    pass
                try:
                    badge3 = product.find_element(By.CSS_SELECTOR, "span.a-badge-text")
                    if "Overall Pick" in badge3.text:
                        continue
                except:
                    pass

                asin = product.get_attribute("data-asin")
                if not asin:
                    continue

                try:
                    title_el = product.find_element(By.CSS_SELECTOR, "h2 span")
                    title = title_el.text.strip()
                except:
                    title = ""

                try:
                    link_el = product.find_element(By.CSS_SELECTOR, "a.a-link-normal.s-underline-text")
                    url = link_el.get_attribute("href")
                except:
                    url = ""

                try:
                    brand_el = product.find_element(By.CSS_SELECTOR, "a.a-size-base.a-text-bold")
                    brand = brand_el.text.strip()
                except:
                    brand = ""

                try:
                    price_whole = product.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.replace(",", "")
                    price_frac = product.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text
                    price = float(f"{price_whole}.{price_frac}")
                except:
                    price = ""

                items.append([asin, brand, price, url, title])

            next_btn = driver.find_element(By.CSS_SELECTOR, "a.s-pagination-next")
            if "s-pagination-disabled" in next_btn.get_attribute("class"):
                break
            next_btn.click()
            page += 1
            time.sleep(2)
        except:
            break

    os.makedirs(output_folder, exist_ok=True)
    price_range = f"{int(current_min)}-{int(current_max)}"
    category_part = category_filter.lower() if category_filter else (category_slug if category_slug else "all")
    brand_part = brand_filter.lower() if brand_filter else "all"

    now_jst = datetime.utcnow() + timedelta(hours=9)  # ✅ タイムスタンプ生成 # この行は新規追加
    timestamp = now_jst.strftime("%Y%m%d_%H%M")       # この行は新規追加
    filename = f"{country_code.upper()}_{timestamp}_{seller_id}_{category_part}_{brand_part}_{price_range}.csv"
    csv_path = os.path.join(output_folder, filename)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ASIN", "Brand", "Price", "URL", "Title"])
        writer.writerows(items)
    if get_debug_mode():
        print(f"✅ {filename} 出力完了（{len(items)}件）")
    current_min = current_max

driver.quit()

# 終了時にService Worker等の肥大化しやすいゴミだけ削除（Cookie・住所設定は消えない）
for folder_name in ["Service Worker", "Code Cache", "GPUCache"]:
    target = os.path.join(profile_path, "Default", folder_name)
    if os.path.exists(target):
        shutil.rmtree(target, ignore_errors=True)
        print(f"🧹 終了処理：削除しました: {target}")
    else:
        print(f"⏭ 終了処理：対象なし（スキップ）: {target}")

