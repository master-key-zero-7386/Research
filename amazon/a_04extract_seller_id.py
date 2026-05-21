import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import csv
import time
import json
import re
import tkinter as tk
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from tkinter import messagebox
from utils.config_loader import cfg, get_debug_mode

DOMAIN_MAP = {
    "us": "www.amazon.com",
    "au": "www.amazon.com.au",
    "sg": "www.amazon.sg",
    "jp": "www.amazon.co.jp",
    "ca": "www.amazon.ca",
}

if get_debug_mode():
    print("✅ Option1 get_seller_id_from_asin.py が起動された！")

# ───── # 📁 定数とグローバル変数定義 ─────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def resolve_path(path_from_config):
    return os.path.normpath(os.path.join(BASE_DIR, path_from_config)) if not os.path.isabs(path_from_config) else path_from_config

# ✅ config.json を読み込み
config_path = os.path.join(BASE_DIR, "config", "config.json")  
with open(config_path, "r", encoding="utf-8-sig") as f:   
    config = json.load(f)

existing_data = {}  # seller_id をキーにした辞書

if len(sys.argv) < 3:
    if get_debug_mode():
        print("Usage: python get_seller_id_from_asin.py [au|us] [csv_path]")
    sys.exit(1)

region = sys.argv[1].lower()
input_file = sys.argv[2]  # ✅ GUIから渡されたCSVパス
lists_dir = resolve_path(config.get("lists_dir", "lists"))
output_file = os.path.join(lists_dir, f"{region}_seller_list.csv") 
output_file = os.path.abspath(output_file)  # 念のため絶対パス化
os.makedirs(os.path.dirname(output_file), exist_ok=True)

if get_debug_mode():
    print("✅ get_seller_id_from_asin.py が起動された！（引数受取）")
    print(f"[DEBUG] region: {region}, csv_path: {input_file}")

# ✅ ウィンドウ位置読み込み
window_pos_file = os.path.join(BASE_DIR, "config", "window_positions.json")
window_x = 0
window_y = 0
try:
    with open(window_pos_file, "r", encoding="utf-8") as f:
        pos_data = json.load(f)
        window_x = pos_data.get("x", 0)
        window_y = pos_data.get("y", 0)
except Exception as e:
    if get_debug_mode():
        print(f"[警告] window_position.jsonの読み込み失敗：{e}")

options = Options()
options.add_argument(f"--window-position={window_x},{window_y}")
options.add_argument("--disable-blink-features=AutomationControlled")

# ✅ プロファイルパス追加（BASE_DIR + Chrome_Profile/{region.upper()}）
profile_path = os.path.join(BASE_DIR, f"Chrome_Profile/{region.upper()}")
# options.add_argument(f"--user-data-dir={profile_path}")

driver = webdriver.Chrome(options=options)

# ✅ 入力CSV読み込み
asins = []
try:
    with open(input_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if row and row[0]:
                asins.append(row[0].strip())
except Exception as e:
    if get_debug_mode():
        print(f"[エラー] 入力CSV読み込み失敗：{e}")
    driver.quit()
    sys.exit(1)

today = datetime.now().strftime("%Y/%m/%d %H:%M")
new_rows = []

# ✅ 既存出力読み込み
existing_ids = set()
existing_rows = []

# ───── # 🧠 セクション2：既存CSVを辞書に読み込み ─────
if os.path.exists(output_file):
    with open(output_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if row and len(row) >= 3:
                while len(row) < 9:
                    row.append("")
                seller_id = row[2].strip()
                existing_data[seller_id] = row

# ───── # 🔄 セクション3：new_rows で重複チェック・更新 ─────
for row in new_rows:
    if len(row) < 3:
        continue  # セラーIDがなければスキップ

    # ✅ セル数が不足していたら空文字で補完（破壊しない）
    while len(row) < 9:
        row.append("")

    seller_id = row[2].strip()
    shop_name_new = row[3]
    last_extracted = row[1]

    if seller_id in existing_data:
        if get_debug_mode():
            print(f"[スキップ] 既存セラー: {seller_id}") 
        existing_row = existing_data[seller_id]
        if shop_name_new.strip():  # ✅ 空白でない場合だけ上書き
            existing_row[3] = shop_name_new  # ✅ この行を修正
        existing_row[1] = last_extracted
    else:
        if get_debug_mode():
            print(f"[追加予定] 新規セラー: {seller_id}")
        existing_data[seller_id] = row
 
# ───── # 🌍 セクション4：Deliver to 確認ポップアップ ─────
def show_deliver_to_popup(confirm_wait=120):
    def on_ok():
        win.destroy()

    def on_cancel():
        driver.quit()
        win.destroy()
        sys.exit()

    win = tk.Tk()
    win.title("配送先確認")
    win.geometry("450x120")
    win.eval('tk::PlaceWindow . center')

    tk.Label(win, text="Deliver to が販売予定の国に設定されていますか？", pady=10).pack()
    tk.Label(win, text=f"OKを押すと処理を開始します（{confirm_wait}秒後に自動で進行）").pack()

    frame = tk.Frame(win)
    frame.pack(pady=10)
    tk.Button(frame, text="OK", width=10, command=on_ok).pack(side="left", padx=10)
    tk.Button(frame, text="キャンセル", width=10, command=on_cancel).pack(side="left", padx=10)

    win.after(confirm_wait * 1000, on_ok)
    win.mainloop()
if asins:
    domain = DOMAIN_MAP.get(region, "www.amazon.com")
    url = f"https://{domain}/dp/{asins[0]}"
    driver.get(url)
    time.sleep(2)

    show_deliver_to_popup()

# ───── # 🔖 セクション5：new_idsセットを初期化 ─────
new_ids = set()
for asin in asins:
    try:
        domain = DOMAIN_MAP.get(region, "www.amazon.com")
        url = f"https://{domain}/dp/{asin}"
        driver.get(url)
        time.sleep(2)

        # ✅ セラーリンクからID
        seller_id = ""
        shop_name = ""
        try:
            seller_link = driver.find_element(By.XPATH, "//a[contains(@href, '/shops/') or contains(@href, 'seller=')]")
            href = seller_link.get_attribute("href")

            if "seller=" in href:
                seller_id = href.split("seller=")[-1].split("&")[0]
            else:
                continue

            # ✅ セラーショップページから正式なショップ名を取得
            domain = DOMAIN_MAP.get(region, "www.amazon.com")
            shop_url = f"https://{domain}/sp?seller={seller_id}"
            driver.get(shop_url)
            time.sleep(2)

            try:
                name_el = driver.find_element(By.XPATH, '//h1 | //span[@id="sellerName"]')
                shop_name = name_el.text.strip()
            except:
                shop_name = "不明"
        except:
            if get_debug_mode():
                print(f"[警告] セラーリンク取得失敗：{asin}")
            continue

        if not seller_id or seller_id in new_ids:
            continue

        # ✅ 既存IDなら last_extracted を更新
        updated = False
        for row in existing_rows:
            if row[2].strip() == seller_id:
                row[1] = today
                updated = True
                break

        # ✅ 新規IDなら行を追加
        if not updated:
            review_lifetime = ""

            try:
                domain = DOMAIN_MAP.get(region, "www.amazon.com")
                shop_url = f"https://{domain}/sp?seller={seller_id}"
                driver.get(shop_url)
                time.sleep(2)

                # ✅ レビュー件数（例: 177 ratings）
                rating_el = driver.find_element(By.XPATH, '//span[contains(text(), "ratings")]')
                review_lifetime = rating_el.text.strip().split(" ")[0]

            except Exception as e:
                if get_debug_mode():
                    print(f"[レビュー取得失敗] {shop_name}: {e}")


            row = [today, today, seller_id, shop_name, "", "", "", review_lifetime, shop_url]  # ✅ この行を修正
            new_rows.append(row)
            existing_data[seller_id] = row
            new_ids.add(seller_id)
            if get_debug_mode():
                print(f"[取得] {seller_id} / {shop_name} → レビュー: {review_lifetime}件")

    except Exception as e:
        if get_debug_mode():
            print(f"[エラー] ASIN {asin} の処理失敗: {e}")



# ✅ ヘッダーを既存ファイルから読み込み（なければ初期化）
if os.path.exists(output_file):
    with open(output_file, newline='', encoding="utf-8-sig") as rf:
        reader = csv.reader(rf)
        headers = next(reader, [])
else:
    headers = [
        "first_recorded", "last_extracted", "seller_id", "shop_name",
        "review_1m", "review_3m", "review_12m", "review_lifetime", "shop_url",
        "hidden", "remarks"  # ✅ 将来列が増えたときはここにだけ足す
    ]

# ✅ データを書き出す（列数不足は空欄で補完）
with open(output_file, "w", newline="", encoding="utf-8-sig") as wf:
    writer = csv.writer(wf)
    writer.writerow(headers)

    for row in existing_data.values():
        row = list(row)  # 念のためリストに変換
        if len(row) < len(headers):
            row += [""] * (len(headers) - len(row))
        elif len(row) > len(headers):
            row = row[:len(headers)]
        writer.writerow(row)

if get_debug_mode():
    print(f"\n✅ 完了：{len(new_rows)} 件追加 → {output_file}")


root = tk.Tk()
root.withdraw()
messagebox.showinfo("完了", "セラーID抽出が完了しました。")
root.destroy()

driver.quit()


