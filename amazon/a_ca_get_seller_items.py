import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import csv
import time
import json
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import tkinter as tk
from utils.config_loader import cfg, get_debug_mode
from amazon.brand_master import get_brand_id


if get_debug_mode():
    print("✅ a_ca_get_seller_items.py が起動されました！")
    
# ✅ seller_id の取得
seller_id = sys.argv[1].strip()

def show_deliver_to_confirmation(confirm_wait, brand_filter):
    proceed_flag = {"value": None}

    def on_ok():
        proceed_flag["value"] = True
        win.destroy()

    def on_cancel():
        proceed_flag["value"] = False
        win.destroy()
        sys.exit(20)

    def auto_ok():
        if proceed_flag["value"] is None:
            proceed_flag["value"] = True
            win.destroy()

    win = tk.Tk()
    win.title("配送先確認")
    win.geometry("450x150")
    win.eval('tk::PlaceWindow . center')

    label_text = (
        "以下の内容を確認してください。\n\n"
        "① Deliver to が販売予定の国に設定されている\n"
        f"② ブランド「{brand_filter}」に ✓ が付いている"
    )

    if confirm_wait > 0:
        label_text += f"\n\n（{confirm_wait}秒後に自動で進行）"
    else:
        label_text += "\n\n（手動確認モード：OKボタンでスタート）"

    tk.Label(win, text=label_text, justify="left", pady=10).pack()

    frame = tk.Frame(win)
    frame.pack(pady=10)
    tk.Button(frame, text="OK", width=10, command=on_ok).pack(side="left", padx=10)
    tk.Button(frame, text="キャンセル", width=10, command=on_cancel).pack(side="left", padx=10)

    if confirm_wait > 0:
        win.after(confirm_wait * 1000, auto_ok)

    win.mainloop()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) 

# config読み込み
config_path = os.path.join(BASE_DIR, "config", "config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

# configのoutput_path優先で取得、なければdata_dirから作成
output_folder = config.get("output_path")
if not output_folder:
    raw_data_dir = config.get("data_dir", "data")
    output_folder = os.path.abspath(os.path.join(BASE_DIR, raw_data_dir))
else:
    output_folder = os.path.abspath(output_folder)

region = "ca"  # 実際は引数等から設定してください

# output_folder配下にregionフォルダを追加
output_folder = os.path.join(output_folder, region.lower())

log_dir = os.path.join(BASE_DIR, config.get("log_dir", "log"))
profile_path = os.path.join(BASE_DIR, config.get("chrome_profile_ca", "Chrome_Profile/ca"))

os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, "log_ca_get_seller_items.txt")
jst_now = datetime.utcnow() + timedelta(hours=9)
with open(log_path, "w", encoding="utf-8") as log:
    log.write(f"【CA版ログ】{jst_now.strftime('%Y-%m-%d %H:%M:%S')} JST\n")

# Chrome初期化
options = Options()
options.add_argument(f"--user-data-dir={profile_path}")
# ブラウザの起動設定を強化
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled") # 自動操作フラグを隠す
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
# 本物のブラウザっぽく見せるためのUser-Agent
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# ドライバー起動時にポート固定（クラッシュ対策）
options.add_argument("--remote-debugging-port=9222") 

# 一旦、既存のドライバ生成をこれに差し替えてください
try:
    driver = webdriver.Chrome(options=options)
    # CDPを使って自動操作フラグを完全に消す（さらに強力）
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
      "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
except Exception as e:
    print(f"❌ Chrome起動失敗: {e}")
    sys.exit(1)
        
wait = WebDriverWait(driver, 15)

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

if brand_filter:
    brand_id = get_brand_id(driver, region, brand_filter)

min_price = float(args[3].strip() or 0)
max_price = float(args[4].strip() or float("inf"))
step = float(args[5].strip() or 0)
# max_page = int(args[].strip() or 20)
confirm_wait_str = args[6].strip()
if confirm_wait_str == "手動確認" or confirm_wait_str == "":
    confirm_wait = 0
else:
    confirm_wait = int(confirm_wait_str)

if get_debug_mode():
    print(f"✅ .py側で受け取った confirm_wait: {confirm_wait}")
exclude_fba = args[7].strip().lower() == "true"
_ignored_output_folder = args[8].strip()
region = args[9].strip()
remarks = args[10].strip() if len(args) > 10 else "未入力"
shop_name = args[11].strip() if len(args) > 11 else "Unknown" 

# ステップ分割処理
current_min = min_price
while current_min < max_price:
    current_max = min(current_min + step, max_price)
    # price_filter = f"&rh=p_36%3A{int(current_min*100)}-{int(current_max*100)}"
    
    rh = [f"p_36:{int(current_min*100)}-{int(current_max*100)}"]

    if brand_id:
        rh.append(f"p_123:{brand_id}")

    price_filter = "&rh=" + ",".join(rh)    

    # ✅ seller_id に "すべて" が含まれる場合は me= を含めない
    me_param = f"me={seller_id}&" if seller_id and "すべて" not in seller_id else ""
    
    base_url = f"https://www.amazon.ca/s?{me_param}"

    if brand_filter:
        base_url += f"&k={brand_filter}"  # ✅ ブランド名がある場合のみ検索キーワードに指定
    if brand_id:
        base_url += f"&rh=p_123:{brand_id}"    
    if category_slug and category_slug != "all":
        base_url += f"&i={category_slug}"  # ✅ カテゴリスラッグがある場合は常にi=指定

    base_url += price_filter  # ✅ 最後に価格フィルタ追加

    if get_debug_mode():
        print(f"▶ URL: {base_url}")
    driver.get(base_url)
    time.sleep(2)

    if current_min == min_price:
        show_deliver_to_confirmation(confirm_wait, brand_filter)

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
    category_part = category_slug if category_slug else "all"
    brand_part = brand_filter.lower() if brand_filter else "all"

    now_jst = datetime.utcnow() + timedelta(hours=9)  # ✅ タイムスタンプ生成
    timestamp = now_jst.strftime("%Y%m%d_%H%M")    
    filename = f"CA_{timestamp}_{seller_id}_{category_part}_{brand_part}_{price_range}.csv" 
    csv_path = os.path.join(output_folder, filename)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ASIN", "Brand", "Price", "URL", "Title"])
        writer.writerows(items)

    if get_debug_mode():
        print(f"✅ {filename} 出力完了（{len(items)}件）")
    current_min = current_max

driver.quit()
