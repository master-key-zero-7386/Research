import os
import sys
import csv
import json
import math
import re
import shutil
import codecs
import requests
import pandas as pd
import subprocess
import traceback
import logging
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for, jsonify, send_file, make_response)
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
from .constants import BASE_DIR, CONFIG_PATH, UPLOAD_FOLDER
from .adapters import AmazonAdapter
from .adapters.amazon_adapter import REGION_CFG
from utils.spapi_client import (get_item_dimensions, load_config, real_signed_request)
from amazon.auth.token_manager import get_access_token
from sp_api.api import Products
from utils.config_loader import cfg, get_debug_mode
from send2trash import send2trash
from flask import url_for 
import sqlite3 

DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
from .a_02extract_asin_list import run_asin_extraction

bp = Blueprint("amazon", __name__)
amazon_bp = bp

TRASH_DIR = os.path.join(BASE_DIR, "tool_trash")  # BASE_DIRはconstantsからimport済み
os.makedirs(TRASH_DIR, exist_ok=True)

amazon_bp = Blueprint("amazon", __name__, url_prefix="/amazon", template_folder="../templates")
from flask import request, jsonify

def get_shop_name_from_seller_id(seller_id, region="sg"):
    try:
        base_urls = {
            "au": "https://www.amazon.com.au/sp?seller=",
            "us": "https://www.amazon.com/sp?seller=",
            "sg": "https://www.amazon.sg/sp?seller=",
            "ca": "https://www.amazon.ca/sp?seller=",
        }
        url = base_urls.get(region, "") + seller_id
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # ✅ より確実なセレクタ（例: <h1 class="a-spacing-none">店舗名</h1>）
            h1_tag = soup.find("h1")
            if h1_tag:
                shop_name = h1_tag.text.strip()
                if shop_name:
                    return shop_name

            # Fallback: タイトルから頑張って抜く
            title_tag = soup.find("title")
            if title_tag:
                title_text = title_tag.text.strip()
                if "Amazon.sg" in title_text:
                    return title_text.replace("Amazon.sg", "").replace(":", "").strip()

        return "取得失敗"
    except Exception as e:
        pass
        return "取得失敗"

def load_config_from_file():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@amazon_bp.route("/save_seller_info", methods=["POST"])  # DB化完了
def save_seller_info():
    try:
        form = request.form
        region = form.get("region", "").lower()
        seller_id = form.get("seller_id") or form.get("manual_seller_id", "")
        shop_name = form.get("shop_name", "")
        remarks = form.get("remarks", "")
        hidden = 1 if form.get("hidden", "") == "TRUE" else 0

        if not region or not seller_id:
            return jsonify({"status": "error", "message": "regionまたはseller_idが指定されていません。"}), 400

        # DBファイルを決定
        db_path = os.path.join(BASE_DIR, "db", "seller_list.db")
        if not os.path.exists(db_path):
            return jsonify({"status": "error", "message": f"DBファイルが存在しません: {db_path}"}), 404

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # セラーが存在するか確認
        cursor.execute(
            "SELECT 1 FROM seller_list WHERE country_code = ? AND seller_id = ?",
            (region.upper(), seller_id)
        )
        
        exists = cursor.fetchone()

        if exists:
            # 更新（last_used の操作はしない）
            cursor.execute(
                "UPDATE seller_list SET shop_name=?, remarks=?, hidden=? WHERE country_code=? AND seller_id=?",
                (shop_name, remarks, hidden, region.upper(), seller_id)
            )
            
        else:
            # 新規追加（last_used の初期値は 0）
            cursor.execute(
                "INSERT INTO seller_list (country_code, seller_id, shop_name, hidden, remarks, review_lifetime, last_used) VALUES (?, ?, ?, ?, ?, ?, 0)",
                (region.upper(), seller_id, shop_name, hidden, remarks, 0)
            )

        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "保存しました。"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@amazon_bp.route("/get_seller_info")  # DB化完了
def get_seller_info():
    try:
        region = request.args.get("region", "").lower()
        seller_id = request.args.get("seller_id", "")

        if not region:
            return jsonify({"status": "error", "message": "region が指定されていません"}), 400

        # DBファイルを確認
        db_path = os.path.join(BASE_DIR, "db", "seller_list.db")
        if not os.path.exists(db_path):
            return jsonify({"status": "error", "message": f"DBファイルが存在しません: {db_path}"}), 404

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if seller_id:
            cursor.execute("""
                SELECT seller_id, shop_name, remarks, hidden
                FROM seller_list
                WHERE country_code = ? AND seller_id = ?
            """, (region.upper(), seller_id))
        else:
            cursor.execute("""
                SELECT seller_id, shop_name, remarks, hidden
                FROM seller_list
                WHERE country_code = ? AND last_used = 1
                LIMIT 1
            """, (region.upper(),))

        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({"status": "not_found"}), 200

        conn.close()

        if row:
            seller_id   = row[0] or ""
            shop_name   = row[1] or ""
            remarks     = row[2] or ""
            hidden      = row[3] or 0

            return jsonify({
                "status": "success",
                "seller_id": seller_id,
                "shop_name": shop_name,
                "remarks": remarks,
                "hidden": "TRUE" if hidden == 1 else ""
            })

        return jsonify({"status": "not_found"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@amazon_bp.route("/get_seller_list")  # DB化完了 + include_hidden対応
def get_seller_list():
    region = request.args.get("region", "").lower() 
    include_hidden = request.args.get("include_hidden", "0") == "1"
    if not region:
        return jsonify({"status": "error", "message": "region is required"}), 400

    db_path = os.path.join(BASE_DIR, "db", "seller_list.db")
    if not os.path.exists(db_path):
        return jsonify({"status": "error", "message": f"DB not found: {db_path}"}), 404

    seller_list = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if include_hidden:
            cursor.execute(
                """
                SELECT seller_id, shop_name
                FROM seller_list
                WHERE country_code = ?
                ORDER BY shop_name ASC
                """,
                (region.upper(),)
            )

        else:
            cursor.execute(
                """
                SELECT seller_id, shop_name
                FROM seller_list
                WHERE country_code = ? AND hidden = 0
                ORDER BY shop_name ASC
                """,
                (region.upper(),)
            )

        rows = cursor.fetchall()
        conn.close()

        for seller_id, shop_name in rows:
            seller_list.append({
                "seller_id": seller_id,
                "seller_name": shop_name
            })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"seller_list": seller_list})

def save_last_used_config(form_data):
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {}

        region = form_data.get("region", "").upper()
        if not region:
            return

        # ✅ last_used を上書き保存（リージョン別にしない）
        config["last_used"] = {
            "region": region,
            "seller_id": form_data.get("seller_id", ""),
            "brand": form_data.get("brand", ""),
            "min_price": form_data.get("min_price", ""),
            "max_price": form_data.get("max_price", ""),
            "step_price": form_data.get("step_price", ""),
            "output_folder": form_data.get("output_folder", ""),
            "confirm_wait": form_data.get("confirm_wait", "")
        }

        config.pop("seller_id_history", None) 

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    except Exception as e:
        pass

@amazon_bp.route("/")
def index():
    seller_list = []
    region = request.args.get("region", "au").lower()
    tab = request.args.get("tab", "research")

    last_used = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                last_used = config.get("last_used", {})
        except Exception as e:
            pass
    
    return render_template(
        "index.html",
        seller_list=seller_list,
        region=region,
        tab=tab,
        last_used=last_used
    )    

# リサーチ
@amazon_bp.route("/process", methods=["POST"])
def process():

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) 
    data = request.get_json()

    region = data.get("region")
    manual_seller_id = data.get("manual_seller_id", "").strip()
    seller_id = data.get("seller_id")
    brand = data.get("brand")
    min_price = data.get("min_price")
    max_price = data.get("max_price")
    step_price = data.get("step_price")
    confirm_wait = data.get("confirm_wait")
    output_folder = data.get("output_folder")
    remarks = data.get("remarks")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    save_last_used_config(data) 

    # ▼ 最後に追加：AU の場合のみ処理スクリプトを実行
    if region:
        script_name = "a_get_seller_items.py"
        script_path = os.path.join(os.getcwd(), "amazon", script_name)
        step_price = step_price.strip() if step_price else "10"
        remarks = remarks.strip() if remarks else "未入力"
        shop_name = get_shop_name_from_seller_id(seller_id, region) 

        # ✅ 実行ボタン押下時に last_used を更新
        try:
            db_path = os.path.join(BASE_DIR, "db", "seller_list.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE seller_list SET last_used=0 WHERE country_code=?",
                (region.upper(),)
            )
            cursor.execute(
                "UPDATE seller_list SET last_used=1 WHERE country_code=? AND seller_id=?",
                (region.upper(), seller_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print("❌ last_used 更新失敗:", e)        

        args = [
            #"python",
            #script_path,    # sys.argv[]
            seller_id,      # args[0]
            "",             # args[1] = category（空でOK） 未使用
            brand,          # args[2]
            min_price,      # args[3]
            max_price,      # args[4]
            step_price,     # args[5]
            # max_page,     # args[]
            confirm_wait,   # args[6]
            "false",        # args[7]
            output_folder,  # args[8]
            region,         # args[9]
            remarks,        # args[10]
            shop_name       # args[11]
        ]
        # subprocess.Popen(["python", script_path] + args)
        subprocess.Popen([sys.executable, script_path] + args)
        return redirect(url_for('amazon.index', region=region, tab="research", completed="true")) 
        
@amazon_bp.route("/save_config", methods=["POST"])
def save_config():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"status": "error", "message": "JSONデータが空です"}), 400

        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # ✅ フォルダ系の保存（共通）
        if data.get("data_folder"):
            config["data_dir"] = data["data_folder"]
        if data.get("lists_folder"):
            config["lists_dir"] = data["lists_folder"]
        if data.get("log_folder"):
            config["log_dir"] = data["log_folder"]

        # ✅ Chromeプロファイル保存（全マーケット共通）
        for key, value in data.items():
            if key.startswith("profile_dir_") and value:
                config[key] = value

        # ✅ 最終利用設定を保存（リージョン単位ではなく直近1件だけ）
        region = data.get("region", "").upper()  # 大文字で統一
        config["last_used"] = {
            "region": region,
            "seller_id": data.get("seller_id", ""),
            "brand": data.get("brand", ""),
            "min_price": data.get("min_price", ""),
            "max_price": data.get("max_price", ""),
            "step_price": data.get("step_price", ""),
            "output_folder": data.get("output_folder", ""),
            "confirm_wait": data.get("confirm_wait", "")
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@amazon_bp.route("/load_config", methods=["GET"])
def load_config():
    try:
        region = request.args.get("region", "").lower()
        if not region:
            return jsonify({"status": "error", "message": "regionパラメータが必要です"}), 400

        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
        if not os.path.exists(config_path):
            return jsonify({"status": "error", "message": "configファイルが存在しません"}), 500

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        last_used_all = config.get("last_used", {})
        data_dir = config.get("data_dir", "data") 

        return jsonify({
            "status": "success", 
            "last_used": last_used_all,
            "data_dir": data_dir
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@amazon_bp.route("/extract_asin_from_csv", methods=["POST"])
def extract_asin_from_csv():
    try:
        files = request.files.getlist("files")
        region = request.form.get("region", "au")

        save_paths = []
        for file in files:
            filename = secure_filename(file.filename)
            save_path = os.path.join(UPLOAD_DIR, filename)
            file.save(save_path)
            save_paths.append(save_path)

        from .a_02extract_asin_list import run_asin_extraction
        filename, output_path = run_asin_extraction(save_paths, region, DATA_DIR)

        # ✅ ダウンロード用URLを返すよう修正
        download_url = url_for("amazon.download_file",
                               region=region.lower(),
                               filename=filename)

        return jsonify({
            "status": "success",
            "message": "ASIN抽出完了",
            "download_url": download_url  # この行を修正
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@amazon_bp.route("/extract_asin_list", methods=["POST"])
def extract_asin_list_route():
    try:
        data = request.get_json() 

        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "リクエストデータが不正です。"})

        region = data.get("region", "").lower()
        if not region:
            return jsonify({"status": "error", "message": "regionが指定されていません。"})

        files = data.get("files", [])

        if not files:
            return jsonify({"status": "error", "message": "ファイルが指定されていません。"})

        # ✅ 出力先ディレクトリの取得
        config = load_config_from_file()
        data_dir = config.get("data_dir", "data")
        region_dir = os.path.join(data_dir, region)

        asin_set = set()

        for filename in files:
            file_path = os.path.join(region_dir, filename)

            if not os.path.exists(file_path):
                continue
            try:

                df = pd.read_csv(file_path)
                if "ASIN" in df.columns:
                    asin_set.update(df["ASIN"].dropna().astype(str).tolist())
                else:
                    pass

            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({"status": "error", "message": f"{filename} の読み込みに失敗しました: {str(e)}"})
        if not asin_set:
            return jsonify({"status": "error", "message": "ASINが抽出できませんでした。"})

        # ✅ ファイル名：{timestamp}_{REGION}_ASIN_list.csv
        now_jst = datetime.utcnow() + timedelta(hours=9)
        timestamp = now_jst.strftime("%Y%m%d_%H%M")
        filename = f"{region.upper()}_{timestamp}_ASIN_list.csv"  
        output_path = os.path.join(region_dir, filename)

        # ✅ CSV 保存
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # ヘッダーに「ASIN」と「SKU」を並べる
            writer.writerow(["ASIN", "SKU"]) 
            
            # データの行は「ASIN」と「空欄（""）」で書き出す
            for asin in sorted(asin_set):
                writer.writerow([asin, ""]) 

        return jsonify({"status": "success", "message": "ASIN抽出完了", "saved_path": output_path, "original_files": files  })

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)})

@amazon_bp.route("/move_to_trash", methods=["POST"])
def move_to_trash():
    data = request.get_json()
    file_names = data.get("files", [])

    # ✅ configから region_dir を取得
    config = load_config_from_file()
    region = data.get("region") or config.get("last_region", "au")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_DIR = os.path.dirname(BASE_DIR)

    data_dir = config.get("data_dir", "data")
    region_dir = os.path.join(PROJECT_DIR, data_dir, region)

    trash_dir = TRASH_DIR
    os.makedirs(trash_dir, exist_ok=True)

    moved_files = []
    for file_name in file_names:
        clean_name = os.path.basename(file_name)
        src_path = os.path.join(region_dir, clean_name)
        if os.path.exists(src_path):
            try:
                dest_path = os.path.join(trash_dir, clean_name)
                shutil.move(src_path, dest_path)
                moved_files.append(clean_name)
            except Exception as e:
                pass
        else:
            pass

    return jsonify({"status": "success", "moved": moved_files})

# ツール専用ごみ箱内完全削除
@amazon_bp.route("/trash_info", methods=["GET"])
def trash_info():
    from datetime import datetime
    files = []
    total = 0
    if os.path.isdir(TRASH_DIR):
        for name in os.listdir(TRASH_DIR):
            path = os.path.join(TRASH_DIR, name)
            if os.path.isfile(path):
                size = os.path.getsize(path)
                mtime = os.path.getmtime(path)
                files.append({
                    "name": name,
                    "size": size,
                    "mtime": mtime,
                    "mtime_iso": datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
                })
                total += size
    return jsonify({"count": len(files), "bytes": total, "files": files})

@amazon_bp.route("/trash_delete", methods=["POST"])
def trash_delete():
    data = request.get_json(force=True, silent=True) or {}
    names = data.get("files", [])
    deleted, missing, errors = [], [], []

    for name in names:
        path = os.path.join(TRASH_DIR, os.path.basename(name))
        try:
            if os.path.exists(path):
                os.remove(path)
                deleted.append(name)
            else:
                missing.append(name)
        except Exception as e:
            errors.append({"name": name, "error": str(e)})

    return jsonify({"deleted": deleted, "missing": missing, "errors": errors})

@amazon_bp.route("/download/<region>/<filename>")
def download_file(region, filename):
    try:
        config = load_config_from_file() 
        data_dir = config.get("data_dir", "data") 
        file_path = os.path.join(data_dir, region.lower(), filename) 

        if not os.path.isfile(file_path):
            return "ファイルが存在しません。", 404

        return send_file(file_path, as_attachment=False)

    except Exception as e:
        print("[ERROR DOWNLOAD]", str(e), flush=True)
        return f"ダウンロード中にエラーが発生しました: {str(e)}", 500

@amazon_bp.route("/get_asin_file_list/<region>")
def get_asin_file_list(region):
    try:
        config = load_config_from_file()
        data_dir = config.get("data_dir", "data")
        folder = os.path.join(data_dir, region)

        if not os.path.exists(folder):
            return jsonify({"status": "error", "message": "指定のフォルダが存在しません。"})

        # フォルダ内の .csv ファイルをリストアップ（降順）
        file_list = sorted(
            [f for f in os.listdir(folder) if f.endswith(".csv")],
            reverse=True
        )

        return jsonify({"status": "success","files": [{"name": f, "url": f"/amazon/download/{region}/{f}"} for f in file_list]})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ---- marketplaceId から region名を決める ----
def _region_from_mp(mp: str, cfg: dict) -> str:
    for reg, mid in (cfg.get("marketplace") or {}).items():
        if mp == mid:
            return reg.lower()
    return "eu"

# @amazon_bp.route("/extract_seller_ids", methods=["POST"])
# def extract_seller_ids():
#     # 入力チェック
#     region = (request.form.get("region") or "").lower()
#     up_files = request.files.getlist("files") or ([request.files["file"]] if "file" in request.files else [])
#     if not region or not up_files:
#         return jsonify({"status": "error", "message": "プラットフォームとCSVファイルを指定してください。"}), 400  

#     # ----- 同時実行ロック: 開始 -----  
#     runtime_dir = os.path.join(os.getcwd(), "runtime", "locks")            
#     os.makedirs(runtime_dir, exist_ok=True)                                
#     lock_path = os.path.join(runtime_dir, f"extract_seller_ids_{region}.lock")

#     if os.path.exists(lock_path):                                            
#         return jsonify({                                                    
#             "status": "error",                                              
#             "message": "抽出処理がすでに実行中です。完了までお待ちください。"     
#         }), 423  # Locked                                                    

#     # ロック作成（PIDと時刻を記録しておくとデバッグしやすい）               
#     try:                                                                     
#         with open(lock_path, "w", encoding="utf-8") as f:                     
#             f.write(f"pid={os.getpid()} utc={datetime.utcnow().isoformat()}")
#     except Exception:                                                          
#         pass                                                              

#     def _unlock():                                                     
#         try:                                                          
#             if os.path.exists(lock_path):                          
#                 os.remove(lock_path)                                       
#         except Exception:                                                   
#             pass                                                                

#     # 設定と各種パス
#     config = load_config_from_file()
#     base_data_dir = config.get("data_dir", "data")
#     lists_dir = config.get("lists_dir", "lists")
#     os.makedirs(lists_dir, exist_ok=True)

#     # seller_list の候補（どちらかを使う）
#     candidates = [
#         os.path.join(lists_dir, f"{region}_seller_list.csv"),      # 例: au_seller_list.csv
#         os.path.join(lists_dir, f"seller_list_{region}.csv"),      # 例: seller_list_au.csv
#     ]
#     seller_list_path = next((p for p in candidates if os.path.exists(p)), candidates[0])

#     # 事前の件数（重複排除してカウント）
#     def _read_ids(path: str) -> set:
#         ids = set()
#         if os.path.exists(path):
#             with open(path, newline="", encoding="utf-8-sig") as f:
#                 for row in csv.reader(f):
#                     if row:
#                         ids.add(row[0].strip())
#         return ids

#     before_ids = _read_ids(seller_list_path)
#     before = len(before_ids)

#     # アップロードCSVを一時保存
#     upload_dir = os.path.join(base_data_dir, region, "_upload")
#     os.makedirs(upload_dir, exist_ok=True)
#     ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
#     temp_csv = os.path.join(upload_dir, f"asin_upload_{ts}.csv")
#     up_files[0].save(temp_csv)

#     # ASIN→SellerID 抽出スクリプトを同期実行
#     script_path = os.path.join(os.getcwd(), "amazon", "a_04extract_seller_id.py")
#     try:
#         env = os.environ.copy()   
#         env["PYTHONIOENCODING"] = "utf-8"  

#         proc = subprocess.run(
#             [sys.executable, script_path, region, temp_csv],
#             cwd=os.getcwd(), capture_output=True, text=True, check=True, env=env, encoding="utf-8" 
#         )

#         if proc.stdout.strip():
#             logging.debug(f"[extract_seller_ids] stdout: {proc.stdout.strip()}")
#         if proc.stderr.strip():
#             logging.debug(f"[extract_seller_ids] stderr: {proc.stderr.strip()}")
#     except subprocess.CalledProcessError as e:
#         msg = f"抽出スクリプト失敗: {e.stderr.strip() or e.stdout.strip()}"
#         _unlock()
#         return jsonify({"status": "error", "message": msg}), 500

#     # スクリプトが別名で作った場合に備え、存在チェック
#     if not os.path.exists(seller_list_path):
#         other = candidates[1] if seller_list_path == candidates[0] else candidates[0]
#         if os.path.exists(other):
#             seller_list_path = other

#     # 実行後の件数と増分
#     after_ids = _read_ids(seller_list_path)
#     added = max(0, len(after_ids) - before)

#     _unlock() 

#     return jsonify({
#         "status": "success",
#         "message": f"{added} 件のセラーIDを抽出しました。",
#         "extracted": added,
#         "output": seller_list_path
#     })




# @amazon_bp.route("/api/account", methods=["GET"])
# def get_account():
#     """config.json からアカウント情報（JP/US/AU/SG/UK）を返す"""
#     import os, json
#     config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
#     try:
#         with open(config_path, "r", encoding="utf-8") as f:
#             config = json.load(f)
#     except FileNotFoundError:
#         config = {}

#     # 互換: account ブロックが無ければ空文字で初期化
#     account = config.get("account") or {
#         "JP": {"seller_id": "", "refresh_token": ""},
#         "US": {"seller_id": "", "refresh_token": ""},
#         "AU": {"seller_id": "", "refresh_token": ""},
#         "SG": {"seller_id": "", "refresh_token": ""},
#         "UK": {"seller_id": "", "refresh_token": ""},
#         "CA": {"seller_id": "", "refresh_token": ""},
#     }

#     return jsonify({"status": "ok", "account": account}), 200

# @amazon_bp.route("/api/idconfig", methods=["GET"])
# def get_idconfig():
#     try:
#         import json, os
#         cfg_path = os.path.join("config", "config.json")
#         with open(cfg_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return jsonify({"status": "ok", "config": data.get("last_used", {})})
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)})


# @amazon_bp.route("/extract_seller_from_asin", methods=["POST"]) 
# def extract_seller_from_asin():
#     """
#     セラーID抽出処理（ASINリストからSeleniumで抽出）
#     Web版Option機能 a_01extract_seller_id.py を呼び出す予定
#     """
#     try:
#         # 現時点ではベース処理のみ
#         return jsonify({"status": "success", "message": "セラーID抽出処理が開始されました（仮）"})
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)})



# # --- shipping config 読み込み & 送料算定ユーティリティ ---
# __SHIPPING_CFG_CACHE = None  # 単純キャッシュ

# def _load_config():
#     """config.json を一度だけ読み込む（単純キャッシュ）"""
#     global __SHIPPING_CFG_CACHE
#     if __SHIPPING_CFG_CACHE is None:
#         with open(CONFIG_PATH, "r", encoding="utf-8") as f:
#             __SHIPPING_CFG_CACHE = json.load(f)
#     return __SHIPPING_CFG_CACHE

# # --- shipping 寸法情報取得・補正 ---
# def get_shipping_params():
#     """
#     config.json の shipping ブロックを辞書で返す。
#     期待キー: padding_cm, pack_ratio, pack_min_kg, volumetric_divisor, round_step_kg
#     """
#     cfg = _load_config()
#     s = cfg.get("shipping", {})
#     return {
#         "padding_cm": float(s.get("padding_cm", 0.0)),
#         "pack_ratio": float(s.get("pack_ratio", 0.0)),
#         "pack_min_kg": float(s.get("pack_min_kg", 0.0)),
#         "volumetric_divisor": float(s.get("volumetric_divisor", 5000)),
#         "round_step_kg": float(s.get("round_step_kg", 0.5)),
#     }

# def _ceil_to_step(value: float, step: float) -> float:
#     """step刻み（例: 0.5kg）で切り上げ"""
#     if step <= 0:
#         return value
#     return math.ceil(value / step) * step

# def calc_billable_weight(length_cm: float, width_cm: float, height_cm: float, product_weight_kg: float):
#     """
#     送料算定に必要な重量を計算して辞書で返す。
#     - 外箱補正: 各辺に padding_cm を加える（L', W', H'）
#     - 梱包重量: max(product_weight * pack_ratio, pack_min_kg)
#     - 実重量(梱包込): product_weight + 梱包重量
#     - 容積重量: (L' * W' * H') / volumetric_divisor  （単位は kg）
#     - 請求重量: max(実重量(梱包込), 容積重量)
#     - 請求重量(丸め): round_step_kg 刻みへ切り上げ
#     """
#     p = get_shipping_params()

#     # 外箱補正（各辺に +padding_cm）
#     Lp = max(0.0, float(length_cm)) + p["padding_cm"]
#     Wp = max(0.0, float(width_cm)) + p["padding_cm"]
#     Hp = max(0.0, float(height_cm)) + p["padding_cm"]

#     volumetric_kg = (Lp * Wp * Hp) / p["volumetric_divisor"]

#     pack_w_kg = max(float(product_weight_kg) * p["pack_ratio"], p["pack_min_kg"])
#     actual_with_pack_kg = float(product_weight_kg) + pack_w_kg

#     billable_kg = max(actual_with_pack_kg, volumetric_kg)
#     billable_kg_rounded = _ceil_to_step(billable_kg, p["round_step_kg"])

#     return {
#         "dims_cm": {"L": Lp, "W": Wp, "H": Hp},
#         "volumetric_weight_kg": volumetric_kg,
#         "actual_weight_with_pack_kg": actual_with_pack_kg,
#         "billable_weight_kg": billable_kg,
#         "billable_weight_kg_rounded": billable_kg_rounded,
#         "params": p,
#     }

# # --- マーケットプレイスのアカウント情報取得 ---
# @amazon_bp.route("/get_account_info", methods=["GET"])
# def get_account_info():
#     from amazon.db import get_conn

#     region = request.args.get("region")
#     if not region:
#         return jsonify({"status": "error", "message": "region is required"}), 400

#     conn = get_conn("a_marketplaces.db")
#     cur = conn.cursor()
#     cur.execute("""
#         SELECT region, display_name, seller_id, refresh_token
#         FROM marketplaces
#         WHERE region = ?
#     """, (region,))
#     row = cur.fetchone()
#     conn.close()

#     if not row:
#         return jsonify({"status": "error", "message": f"region {region} not found"}), 404

#     return jsonify({
#         "status": "success",
#         "region": row["region"],
#         "display_name": row["display_name"],
#         "seller_id": row["seller_id"] or "",
#         "refresh_token": row["refresh_token"] or ""
#     })

# # --- マーケットプレイスのアカウント情報保存 ---
# @amazon_bp.route("/save_account_info", methods=["POST"])
# def save_account_info():
#     from amazon.db import get_conn

#     data = request.get_json()
#     region = data.get("region")
#     seller_id = data.get("seller_id", "")
#     refresh_token = data.get("refresh_token", "")

#     if not region:
#         return jsonify({"status": "error", "message": "region is required"}), 400

#     conn = get_conn("a_marketplaces.db")
#     cur = conn.cursor()
#     cur.execute("""
#         UPDATE marketplaces
#         SET seller_id = ?, refresh_token = ?, updated_at = CURRENT_TIMESTAMP
#         WHERE region = ?
#     """, (seller_id, refresh_token, region))
#     conn.commit()
#     conn.close()

#     return jsonify({"status": "success", "message": f"{region} updated"})

# # --- アカウント設定ページ表示 ---
# @amazon_bp.route("/account", methods=["GET"])
# def account_page():
#     return render_template("account.html")

# # --- マーケットプレイス一覧取得 ---
# @amazon_bp.route("/get_marketplaces", methods=["GET"])
# def get_marketplaces():
#     from amazon.db import get_conn
#     conn = get_conn("a_marketplaces.db")
#     cur = conn.cursor()
#     cur.execute("SELECT region, display_name FROM marketplaces ORDER BY id")
#     rows = cur.fetchall()
#     conn.close()
#     return jsonify([{"region": r["region"], "display_name": r["display_name"]} for r in rows])


# def inject_shipping_into_payload(payload: dict) -> dict:  
#     """
#     payload 内の寸法・重量を探して請求重量の計算結果を payload["shipping"] に追加して返す。
#     対応:
#       - SP-API形式: dimensions.{packageDimensions|itemDimensions}.{length,width,height}.{value,unit}
#                     dimensions.{packageWeight|itemWeight}.{value,unit}
#       - フラット/簡易: length_cm/width_cm/height_cm/weight_kg または mm/g
#     """
#     if not isinstance(payload, dict):
#         return payload

#     try:
#         asin = payload.get("asin") or payload.get("ASIN")
#         region = payload.get("region") or ""   # region 情報を優先的に使う

#         if asin and region:
#             cfg = _load_config()
#             raw_price = get_pricing_summary(asin, region, cfg)
#             summary = parse_pricing_summary(raw_price)

#             # 既存pricingがあれば壊さずマージ
#             pricing = payload.get("pricing") or {}
#             pricing.update({k: v for k, v in summary.items() if v is not None})
#             payload["pricing"] = pricing
#     except Exception as e:
#         # 価格が取れなくても shipping 計算は続行
#         payload["_pricing_error"] = f"{type(e).__name__}: {e}"
#         pass


        
#     # --- 1) まず SP-API 形式を優先して読む ---
#     dims_root = {}
#     weight_root = {}

#     if isinstance(payload.get("dimensions"), dict):
#         dims_root = payload["dimensions"]
#         weight_root = payload["dimensions"]

#     dim_obj = {}
#     if isinstance(dims_root.get("packageDimensions"), dict):
#         dim_obj = dims_root["packageDimensions"]
#     elif isinstance(dims_root.get("itemDimensions"), dict):
#         dim_obj = dims_root["itemDimensions"]

#     wt_obj = {}
#     if isinstance(weight_root.get("packageWeight"), dict):
#         wt_obj = weight_root["packageWeight"]
#     elif isinstance(weight_root.get("itemWeight"), dict):
#         wt_obj = weight_root["itemWeight"]

#     def _dim_to_cm(o: dict, key: str) -> float:
#         if not isinstance(o, dict):
#             return 0.0
#         x = o.get(key) or {}
#         try:
#             val = float(x.get("value") or x.get("Value") or 0)
#         except (TypeError, ValueError):
#             val = 0.0
#         unit = str(x.get("unit") or x.get("Unit") or "").strip().lower()
#         if unit in ("cm", "centimeter", "centimeters"):
#             return val
#         if unit in ("mm", "millimeter", "millimeters"):
#             return val / 10.0
#         if unit in ("in", "inch", "inches"):
#             return val * 2.54
#         if unit in ("m", "meter", "meters"):
#             return val * 100.0
#         return 0.0

#     def _wt_to_kg(o: dict) -> float:
#         if not isinstance(o, dict):
#             return 0.0
#         try:
#             val = float(o.get("value") or o.get("Value") or 0)
#         except (TypeError, ValueError):
#             val = 0.0
#         unit = str(o.get("unit") or o.get("Unit") or "").strip().lower()
#         if unit in ("kg", "kilogram", "kilograms"):
#             return val
#         if unit in ("g", "gram", "grams"):
#             return val / 1000.0
#         if unit in ("lb", "lbs", "pound", "pounds"):
#             return val * 0.45359237
#         if unit in ("oz", "ounce", "ounces"):
#             return val * 0.028349523125
#         return 0.0

#     L = _dim_to_cm(dim_obj, "length")
#     W = _dim_to_cm(dim_obj, "width")
#     H = _dim_to_cm(dim_obj, "height")
#     G = _wt_to_kg(wt_obj)

#     # --- 2) SP-APIで取れなかった場合は従来キーを読む（後方互換） ---
#     if (L == 0 and W == 0 and H == 0) or G == 0:
#         d = {}
#         if isinstance(payload.get("dimensions"), dict):
#             d = payload["dimensions"]

#         def pick_len(prefix):
#             if f"{prefix}_cm" in d: return float(d.get(f"{prefix}_cm", 0))
#             if f"{prefix}_cm" in payload: return float(payload.get(f"{prefix}_cm", 0))
#             if f"{prefix}_mm" in d: return float(d.get(f"{prefix}_mm", 0)) / 10.0
#             if f"{prefix}_mm" in payload: return float(payload.get(f"{prefix}_mm", 0)) / 10.0
#             return 0.0

#         def pick_wt():
#             if "weight_kg" in d: return float(d.get("weight_kg", 0))
#             if "weight_kg" in payload: return float(payload.get("weight_kg", 0))
#             if "weight_g" in d: return float(d.get("weight_g", 0)) / 1000.0
#             if "weight_g" in payload: return float(payload.get("weight_g", 0)) / 1000.0
#             return 0.0

#         L = L or pick_len("length")
#         W = W or pick_len("width")
#         H = H or pick_len("height")
#         G = G or pick_wt()

#     # --- 3) 計算して差し込み ---
#     payload["shipping"] = calc_billable_weight(L, W, H, G)  

#     return payload

# # --- pricing 価格情報取得 ---
# def get_pricing_summary_raw(asin: str, region: str, cfg: dict):
#     """
#     Product Pricing API (offers) を叩いて raw JSON を返す
#     """
#     path = f"/products/pricing/v0/items/{asin}/offers"
#     mpid = _get_mpid(region, cfg)
#     params = {
#         "MarketplaceId": mpid,
#         "marketplaceIds": [mpid],
#         "ItemCondition": "New" 
#     }
#     host = ((cfg.get("marketplace") or {}).get(region.upper()) or {}).get("host")

#     return real_signed_request("GET", path, params=params, host=host, cfg=cfg)

# def parse_pricing_summary(raw: dict) -> dict:
#     """
#     raw から BuyBox / Lowest new / Lowest used を抽出して数値(Amount)だけ返す
#     """
#     try:
#         payload = raw.get("payload") or {}
#         summary = payload.get("Summary") or {}

#         # --- BuyBox（新品のみ） ---
#         bb = None
#         for b in summary.get("BuyBoxPrices") or []:
#             if (b.get("condition") or "").lower() == "new":
#                 bb = (b.get("LandedPrice") or {}).get("Amount")
#                 break

#         # --- Lowest 新品 ---
#         lowest_new = None
#         lowest_new_channel = None
#         for lp in summary.get("LowestPrices") or []:
#             cond = (lp.get("condition") or "").lower()
#             amt = (lp.get("LandedPrice") or {}).get("Amount")
#             if cond == "new" and amt is not None:
#                 if lowest_new is None or amt < lowest_new:
#                     lowest_new = amt
#                     fc = (lp.get("fulfillmentChannel") or "").lower()
#                     lowest_new_channel = "FBA" if fc == "amazon" else "FBM"

#         # --- Lowest 中古 ---
#         lowest_used = None
#         for lp in summary.get("LowestPrices") or []:
#             cond = (lp.get("condition") or "").lower()
#             amt = (lp.get("LandedPrice") or {}).get("Amount")
#             if cond == "used" and amt is not None:
#                 if lowest_used is None or amt < lowest_used:
#                     lowest_used = amt

#         # --- ListPrice（定価） ---
#         list_price = None
#         if summary.get("ListPrice"):
#             list_price = summary["ListPrice"].get("Amount")

#         return {
#             "buybox": bb,
#             "lowest_new": lowest_new,
#             "lowest_new_channel": lowest_new_channel,
#             "lowest_used": lowest_used,
#             "list_price": list_price,
#         }
#     except Exception:
#         return {
#             "buybox": None,
#             "lowest_new": None,
#             "lowest_new_channel": None,
#             "lowest_used": None,
#             "list_price": None,
#         }

# @amazon_bp.route("/api/account", methods=["POST"])
# def save_account():
#     """フロントから受け取ったアカウント情報で config.json の account を上書き保存する"""
#     import os, json
#     payload = request.get_json(silent=True) or {}
#     new_account = payload.get("account", {})

#     # 想定リージョン
#     allowed_keys = {"JP", "US", "AU", "SG", "UK", "CA"}
#     config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")

#     try:
#         if os.path.exists(config_path):
#             with open(config_path, "r", encoding="utf-8") as f:
#                 config = json.load(f)
#         else:
#             config = {}

#         old_account = config.get("account", {})
#         norm = {}
#         for k in allowed_keys:
#             v = new_account.get(k) or {}
#             old = old_account.get(k, {})
#             norm[k] = {
#                 "seller_id": str(v.get("seller_id") or old.get("seller_id", "")),
#                 "refresh_token": str(v.get("refresh_token") or old.get("refresh_token", "")),
#             }

#         config["account"] = norm

#         os.makedirs(os.path.dirname(config_path), exist_ok=True)
#         with open(config_path, "w", encoding="utf-8") as f:
#             json.dump(config, f, ensure_ascii=False, indent=2)

#         return jsonify({"status": "ok"}), 200

#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

# # Debug モードの ON/OFF 切替　読取
# @amazon_bp.route("/api/get_debug", methods=["GET"])
# def get_debug():
#     try:
#         cfg_path = os.path.join(BASE_DIR, "config", "config.json")
#         with open(cfg_path, "r", encoding="utf-8") as f:
#             cfg = json.load(f)
#         return jsonify({"status": "ok", "debug": cfg.get("debug", False)})
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

# # Debug モードの ON/OFF 切替　書込
# @amazon_bp.route("/api/set_debug", methods=["POST"])
# def set_debug():
#     try:
#         data = request.get_json() or {}
#         new_value = bool(data.get("debug", False))

#         cfg_path = os.path.join(BASE_DIR, "config", "config.json")

#         with open(cfg_path, "r", encoding="utf-8") as f:
#             cfg = json.load(f)

#         cfg["debug"] = new_value

#         with open(cfg_path, "w", encoding="utf-8") as f:
#             json.dump(cfg, f, ensure_ascii=False, indent=2)

#         return jsonify({"status": "ok", "debug": new_value})
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500

# @amazon_bp.route("/get_config_account", methods=["GET"])
# def get_config_account():
#     """
#     画面初期表示や保存後の再反映用に、アカウントID／トークン系を返す。
#     """
#     try:
#         config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
#         with open(config_path, "r", encoding="utf-8") as f:
#             config = json.load(f)

#         result = {
#             "account": config.get("account", {}),
#             "last_used_region": config.get("last_used", {}).get("region", None),
#         }
#         return jsonify({"status": "ok", "data": result}), 200  
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500  

# @amazon_bp.route("/get_latest_log")
# def get_latest_log():
#     import os

#     # ✅ base_dir は zsss_web 直下を基準にする
#     base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # ✅ 1つ上の階層に修正

#     log_path = os.path.join(base_dir, "zsss_web", "log", "log_au_get_seller_items.txt") 

#     if not os.path.exists(log_path):
#         return "【AU版ログ】ログファイルが見つかりません", 200

#     try:
#         with open(log_path, "r", encoding="utf-8") as f:
#             lines = f.readlines()
#             for line in reversed(lines):
#                 if line.strip():
#                     return f"【AU版ログ】{line.strip()}", 200
#             return "【AU版ログ】ログが空です", 200
#     except Exception as e:
#         return f"【AU版ログ】エラー: {str(e)}", 500

# def _get_mpid(region: str, cfg: dict) -> str:  
#     """
#     config.json の marketplace セクションからリージョンに対応する marketplaceId を返す
#     """
#     region = (region or "").upper()
#     mp = (cfg.get("marketplace") or {}).get(region, {})

#     return (mp.get("marketplace_id")
#         or mp.get("marketplaceId") 
#         or "")

# def get_item_offers(asin: str, region: str, cfg: dict):
#     """AmazonPricingAdapter に委譲（MarketplaceId は config から解決）"""
#     from amazon.adapters.amazon_adapter import AmazonPricingAdapter
#     adapter = AmazonPricingAdapter()
#     return adapter.get_item_offers(asin=asin, region=region)

# @amazon_bp.route("/product_info", methods=["POST"])
# def product_info():
#     try:
#         data = request.get_json()
#         asin = data.get("asin")

#         # config.json 読み込み
#         config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
#         with open(config_path, "r", encoding="utf-8") as f:
#             config = json.load(f)
        
#         adapter = AmazonAdapter(config)
#         region = ((request.json or {}).get("region") or request.args.get("region") or "JP").upper()
#         if region not in REGION_CFG: 
#             region = "JP" 

#         try:  
#             jp_catalog      = adapter.get_catalog_item(asin, source_region="JP")
#             foreign_catalog = adapter.get_catalog_item(asin, source_region=region)

#             def _unwrap_catalog(c):  
#                 if not isinstance(c, dict):  
#                     return c  
#                 if isinstance(c.get("items"), list) and c["items"]:  
#                     return c["items"][0]  
#                 for k in ("payload", "data", "result", "item", "catalog", "body"):  
#                     v = c.get(k)  
#                     if isinstance(v, dict):  
#                         return v  
#                 return c  

#             jp_catalog = _unwrap_catalog(jp_catalog)  
#             foreign_catalog = _unwrap_catalog(foreign_catalog)  

#             # --- JPがエラー辞書なら直叩きで再取得（ここを新しく挿入） ---
#             if isinstance(jp_catalog, dict) and (jp_catalog.get("status") == "error" or set(jp_catalog.keys()) <= {"status","message","detail"}):
#                 try:
#                     mpid_jp = _get_mpid("JP", config)
#                     host_jp = ((config.get("marketplace") or {}).get("JP") or {}).get("host") or "https://sellingpartnerapi-fe.amazon.com"
#                     path = f"/catalog/2022-04-01/items/{asin}"
#                     params = {
#                         "marketplaceIds": [mpid_jp],
#                         "includedData": "attributes,dimensions,summaries,images,productTypes,salesRanks",
#                         "locale": "ja_JP",
#                     }
#                     r = real_signed_request("GET", path, params=params, host=host_jp, cfg=config)
#                     jp_catalog = _unwrap_catalog(r)

#                 except Exception as _e:
#                     pass
            
#             if not isinstance(jp_catalog, dict) or not isinstance(foreign_catalog, dict):
#                 return jsonify({"status":"error","message":"adapter returned non-dict"}), 500

#             def _best_rank(cj, region, cfg):
#                 sr = cj.get("salesRanks") or []
#                 mpid = _get_mpid(region, cfg)
#                 sr0 = next((x for x in sr if x.get("marketplaceId") == mpid), (sr[0] if sr else None))
#                 title, rank = "--", "--"
#                 if isinstance(sr0, dict):
#                     ranks = sr0.get("classificationRanks") or sr0.get("displayGroupRanks") or []
#                     if isinstance(ranks, list) and ranks:
#                         # rank（数値）があるものを優先し、最小値＝最良を採用
#                         nums = [r for r in ranks if isinstance(r.get("rank"), int)]
#                         top = min(nums, key=lambda r: r["rank"]) if nums else ranks[0]
#                         title = top.get("title") or title
#                         rv = top.get("rank")
#                         rank = str(rv) if rv is not None else "--"
#                 return title, rank

#             def _category(cj):
#                 s0 = (cj.get("summaries") or [{}])[0]
#                 return ((s0.get("browseClassification") or {}).get("displayName")) or "--"

#             # JP（左）は config から MarketplaceId を解決
#             jp_category = _category(jp_catalog)
#             _jp_title, jp_rank = _best_rank(jp_catalog, "JP", config)
#             if jp_category == "--":
#                 jp_category = _jp_title

#             # 右（選択リージョン）は fg_catalog から作る
#             fg_category = _category(foreign_catalog)
#             _fg_title, fg_rank = _best_rank(foreign_catalog, region, config)
#             if fg_category == "--":
#                 fg_category = _fg_title
                           
#         except Exception as e:  
#             import traceback  
#             tb = traceback.format_exc()  

#             return jsonify({"status":"error","message":"product_info exception","detail":f"{e.__class__.__name__}: {e}"}), 500  

#         if isinstance((resp := (locals().get("resp") or locals().get("response") or locals().get("catalog_json") or {})), dict) and resp.get("status") == "error":


#             return jsonify(resp), 500    

#         # --- 画像 & カテゴリ 抽出（確定版） ---
#         base_catalog = jp_catalog

#         category = None
#         image_url = None

#         # 汎用：images配列から最初のURL文字列を拾う（キー違い・入れ子対応）
#         def _pick_image_url(images_list):
#             if not isinstance(images_list, list):
#                 return None
#             def scan(obj):
#                 if isinstance(obj, dict):
#                     # よくあるキー名を先にチェック
#                     for k in ("link","url","imageUrl","imageURL","hiRes","large","medium","small"):
#                         v = obj.get(k)
#                         if isinstance(v, str) and v.startswith("http"):
#                             return v
#                     # 入れ子も総当たり
#                     for v in obj.values():
#                         r = scan(v)
#                         if r: return r
#                 elif isinstance(obj, list):
#                     for v in obj:
#                         r = scan(v)
#                         if r: return r
#                 elif isinstance(obj, str):
#                     if obj.startswith("http"):
#                         return obj
#                 return None

#             for itm in images_list:
#                 r = scan(itm)
#                 if r: return r
#             return None

#         def _pick_summary_for_region(summaries, region, cfg):
#             for s in summaries:
#                 if s.get("marketplaceId") == (cfg.get("marketplace", {}).get(region, {}) or {}).get("marketplace_id"):
#                     return s
#             return summaries[0] if summaries else None

#         # summaries[0] から優先的に取る
#         sums = (base_catalog or {}).get("summaries") or []
#         s0 = _pick_summary_for_region(sums, region, config) if sums else None

#         if isinstance(s0, dict):
#             bc = s0.get("browseClassification") or {}
#             category = bc.get("displayName") or s0.get("productType") or category

#         if not image_url:
#             image_url = _pick_image_url((base_catalog or {}).get("images") or [])

#         if not image_url:
#             image_url = _pick_image_url((jp_catalog or {}).get("images") or [])

#         # カテゴリのフォールバック: productTypes -> attributes.item_type_name
#         if not category:
#             pts = (base_catalog or {}).get("productTypes") or []
#             if pts and isinstance(pts[0], dict):
#                 category = pts[0].get("productType")

#         if not category:
#             at = (base_catalog or {}).get("attributes") or {}
#             itn = at.get("item_type_name") or []
#             if itn and isinstance(itn[0], dict):
#                 category = itn[0].get("value")

#         # --- JP カタログ抽出（最小&フォールバック） ---
#         catalog = base_catalog
#         attrs = (catalog or {}).get("attributes") or {}  
#         sums = ((catalog or {}).get("summaries") or [{}])[0] 
#         dimsj = (catalog or {}).get("dimensions") or {}

#         if isinstance(dimsj, list):
#             dimsj = dimsj[0] if dimsj else {} 
#         elif not isinstance(dimsj, dict):  
#             dimsj = {}

#         def _take_text(a, key):
#             v = a.get(key)
#             if isinstance(v, list) and v:
#                 x = v[0];  return (x.get("value") if isinstance(x, dict) else x)
#             if isinstance(v, dict):
#                 return v.get("value")
#             return None

#         def _dim_from_attr(a, key):
#             lst = a.get(key) or []
#             first = lst[0] if isinstance(lst, list) and lst else {}
#             def _val(k):
#                 part = first.get(k) or {}
#                 return part.get("value") if isinstance(part, dict) else None
#             unit = None
#             for k in ("length","width","height"):
#                 part = first.get(k)
#                 if isinstance(part, dict) and part.get("unit"): unit = part.get("unit"); break
#             return {"length": _val("length"), "width": _val("width"), "height": _val("height"), "unit": unit}

#         def _dim_from_dims(d):  # dimensions.item / dimensions.package
#             def _val(k):
#                 part = d.get(k)
#                 return part.get("value") if isinstance(part, dict) else None
#             unit = None
#             for k in ("length","width","height"):
#                 part = d.get(k)
#                 if isinstance(part, dict) and part.get("unit"): unit = part.get("unit"); break
#             return {"length": _val("length"), "width": _val("width"), "height": _val("height"), "unit": unit}

#         def _weight_from_attr(a, key):
#             lst = a.get(key) or []
#             first = lst[0] if isinstance(lst, list) and lst else {}
#             w = first.get("weight") if isinstance(first, dict) else None
#             if isinstance(w, dict):
#                 return {"value": w.get("value"), "unit": w.get("unit")}
#             return {"value": first.get("value") if isinstance(first, dict) else None,
#                     "unit": first.get("unit")  if isinstance(first, dict) else None}

#         def _weight_from_dims(d):  # dimensions.item.weight 等
#             w = d.get("weight")
#             if isinstance(w, dict):
#                 return {"value": w.get("value"), "unit": w.get("unit")}
#             return {"value": None, "unit": None}

#         title = sums.get("itemName") or _take_text(attrs, "item_name")
#         brand = sums.get("brand")    or _take_text(attrs, "brand")

#         catalog = locals().get("resp")
#         if not (isinstance(catalog, dict) and any(k in catalog for k in ("summaries", "attributes", "images"))):
#             catalog = locals().get("jp_catalog") or locals().get("catalog_json") or {}

#         # ★ カテゴリ・ランキング抽出
#         mpid_jp = _get_mpid("JP", config)
#         jp_summary = next((s for s in (((jp_catalog or {}).get("summaries") or []))
#                            if (s.get("marketplaceId") or s.get("marketplace_id")) == mpid_jp), None)
#         jp_category = "--"
#         jp_rank = "--"

#         s0 = jp_summary or {} 

#         # browseClassification からカテゴリ
#         if "browseClassification" in s0:
#             bc = s0["browseClassification"]
#             jp_category = bc.get("displayName") or bc.get("classification") or "--"  

#         # salesRanks からランキング
#         ranks = (jp_catalog or {}).get("salesRanks") or [] 
#         if ranks:
#             r0 = next((r for r in ranks if (r.get("marketplaceId") or r.get("marketplace_id")) == mpid_jp), ranks[0])

#             cranks = r0.get("classificationRanks") or []
#             dranks = r0.get("displayGroupRanks") or []   

#             if cranks:
#                 top = cranks[0]
#                 jp_category = top.get("title") or jp_category
#                 val = top.get("rank")
#                 if val is None:
#                     jp_rank = "--"
#                 else:
#                     r = str(val).replace(",", "").strip()
#                     jp_rank = r if r.isdigit() else str(val)

#             elif dranks:
#                 top = dranks[0]
#                 jp_category = top.get("title") or jp_category
#                 val = top.get("rank")
#                 if val is None:
#                     jp_rank = "--"
#                 else:
#                     r = str(val).replace(",", "").strip()
#                     jp_rank = r if r.isdigit() else str(val)

#         item_dimensions    = _dim_from_attr(attrs, "item_dimensions")
#         package_dimensions = _dim_from_attr(attrs, "package_dimensions")
#         item_weight        = _weight_from_attr(attrs, "item_weight")
#         package_weight     = _weight_from_attr(attrs, "package_weight")

#         # dimensions 正規化（list対応） 
#         if isinstance(dimsj, list):  
#             dimsj = dimsj[0] if dimsj else {}
#         elif not isinstance(dimsj, dict):
#             dimsj = {}

#         # フォールバック：attributesで取れなければ dimensions から補完
#         itm = dimsj.get("item") or {} 
#         if isinstance(itm, list):  
#             itm = itm[0] if itm else {}  
#         pkg = dimsj.get("package") or {} 
#         if isinstance(pkg, list):  
#             pkg = pkg[0] if pkg else {}  


#         if not any(v for k,v in item_dimensions.items() if k!="unit"):
#             item_dimensions = _dim_from_dims(itm)
#         if not any(v for k,v in package_dimensions.items() if k!="unit"):
#             package_dimensions = _dim_from_dims(pkg)
#         if not item_weight.get("value"):
#             item_weight = _weight_from_dims(itm)
#         if not package_weight.get("value"):
#             package_weight = _weight_from_dims(pkg)
        
#         # 単位正規化：cm / kg へ統一
#         def _dim_to_cm_inplace(d):
#             if not isinstance(d, dict):
#                 return
#             u = (d.get("unit") or "").lower()
#             def to_cm(v):
#                 if v is None:
#                     return None
#                 if u in ("millimeter", "millimeters", "mm"):
#                     return v / 10.0
#                 if u in ("centimeter", "centimeters", "cm"):
#                     return v
#                 if u in ("meter", "meters", "m"):
#                     return v * 100.0
#                 if u in ("inch", "inches", "in"):
#                     return v * 2.54
#                 if u in ("foot", "feet", "ft"):
#                     return v * 30.48
#                 if u in ("yard", "yards", "yd"):
#                     return v * 91.44
#                 return v

#             for k in ("length", "width", "height"):
#                 val = d.get(k)
#                 if isinstance(val, (int, float)):
#                     d[k] = to_cm(val)
#                     if isinstance(d[k], (int, float)):
#                         d[k] = round(d[k], 1)
                
                    
#             if d:
#                 d["unit"] = "centimeters"

#         def _weight_to_kg_inplace(w):
#             if not isinstance(w, dict):
#                 return     
#             u = (w.get("unit") or "").lower()
#             v = w.get("value")
#             if isinstance(v, (int, float)):
#                 if u in ("kilogram", "kilograms", "kg"):
#                     w["value"] = v
#                 elif u in ("gram", "grams", "g"):
#                     w["value"] = v / 1000.0
#                 elif u in ("pound", "pounds", "lb", "lbs"):
#                     w["value"] = v * 0.45359237
#                 elif u in ("ounce", "ounces", "oz"):
#                     w["value"] = v / 35.27396195
#                 else:
#                     w["value"] = v
#                 w["unit"] = "kilograms"
#                 w["value"] = round(w["value"], 3) 

#         _dim_to_cm_inplace(item_dimensions)
#         _dim_to_cm_inplace(package_dimensions)
#         _weight_to_kg_inplace(item_weight)
#         _weight_to_kg_inplace(package_weight)

#         # 画面表示用：package を優先して上書き用の値を作る  
#         _use_dim = package_dimensions if any(v for k, v in package_dimensions.items() if k != "unit") else item_dimensions
#         _use_w   = package_weight if package_weight.get("value") else item_weight

#         jp_pkg_len_cm = _use_dim.get("length")  
#         jp_pkg_wid_cm = _use_dim.get("width")   
#         jp_pkg_hei_cm = _use_dim.get("height")  
#         jp_pkg_wt_kg  = _use_w.get("value")                 

#         # --- EAN/JAN 抽出（強化版） ---
#         def _first_value_any(x):
#             # list[{"value":..}] / list["..."] / "..." / 数値 を安全に文字列化
#             if isinstance(x, list) and x:
#                 head = x[0]
#                 if isinstance(head, dict) and "value" in head:
#                     v = head.get("value")
#                     return "" if v is None else str(v)
#                 return "" if head is None else str(head)
#             if isinstance(x, (str, int, float)):
#                 return "" if x is None else str(x)
#             return ""

#         # --- JP価格（参考）: attributes から候補を集め最安を返す ---
#         def _num_or_none(x):
#             try:
#                 return float(str(x).replace(",", "").strip())
#             except Exception:
#                 return None

#         def _extract_candidate_prices_jpy(attrs: dict):
#             if not isinstance(attrs, dict):
#                 return []
#             keys = (
#                 "standard_price","standardPrice",
#                 "list_price","listPrice","msrp",
#                 "price","item_price","itemPrice",
#                 "recommendedRetailPrice","manufacturer_suggested_retail_price",
#             )
#             out = []
#             for k in keys:
#                 node = attrs.get(k)
#                 if isinstance(node, list) and node:
#                     n0 = node[0]
#                     if isinstance(n0, dict):
#                         # 1) {"currency":"JPY","value":3619} or {"Currency":..,"Amount":..}
#                         cur = n0.get("currency") or n0.get("Currency")
#                         val = n0.get("value") or n0.get("amount") or n0.get("Value") or n0.get("Amount")
#                         if cur and str(cur).upper() == "JPY":
#                             v = _num_or_none(val)
#                             if v is not None: out.append(v); continue
#                         # 2) {"value":{"currency":"JPY","amount":3619}}
#                         if isinstance(n0.get("value"), dict):
#                             v0 = n0["value"]
#                             cur = v0.get("currency") or v0.get("Currency")
#                             amt = v0.get("amount") or v0.get("value") or v0.get("Amount") or v0.get("Value")
#                             if cur and str(cur).upper() == "JPY":
#                                 v = _num_or_none(amt)
#                                 if v is not None: out.append(v); continue
#                         # 3) {"value":"3619"} / {"value":3619}
#                         v = _num_or_none(n0.get("value"))
#                         if v is not None: out.append(v); continue
#                     # 4) ["3619"] / [3619]
#                     v = _num_or_none(n0)
#                     if v is not None: out.append(v)
#                 elif node is not None:
#                     v = _num_or_none(node)
#                     if v is not None: out.append(v)
#             # 重複除去して昇順
#             return sorted(set(out))

#         jp_price_candidates = _extract_candidate_prices_jpy(attrs)
#         jp_price = jp_price_candidates[0] if jp_price_candidates else None

#         def _pick_ean_from_attrs(attrs: dict) -> str:
#             if not isinstance(attrs, dict):
#                 return ""
#             # よく使われるキー名（snake/camel両対応）
#             preferred = (
#                 "jan","ean","gtin","gtin13","gtin_13","gtin14","gtin_14",
#                 "external_product_id","externalproductid","externalProductId",
#                 "product_id","productid","productId",
#                 "upc","barcode","barCode"
#             )
#             pref_norm = {k.replace("_","").lower() for k in preferred}

#             # 1) 優先キーでヒットすれば採用
#             for key, seq in attrs.items():
#                 norm = key.replace("_","").lower()
#                 if norm in pref_norm:
#                     v = re.sub(r"\D", "", _first_value_any(seq) or "")
#                     if 12 <= len(v) <= 14:
#                         return v

#             # 2) ダメなら attributes を深掘りして 12–14桁の連続数字を探索
#             def dfs(obj):
#                 if isinstance(obj, dict):
#                     for v in obj.values():
#                         res = dfs(v)
#                         if res: return res
#                 elif isinstance(obj, list):
#                     for v in obj:
#                         res = dfs(v)
#                         if res: return res
#                 else:
#                     s = re.sub(r"\D", "", str(obj))
#                     if 12 <= len(s) <= 14:
#                         return s
#                 return ""

#             return dfs(attrs) or ""

#         # attributes から EAN/JAN を決定
#         ean_value = _pick_ean_from_attrs(attrs)

#         offers = get_item_offers(asin, region, config)
#         from amazon.adapters.amazon_adapter import AmazonPricingAdapter

#         # 日本側と海外側で別々に取得
#         jp_pricing = AmazonPricingAdapter().get_pricing_summary(asin, "JP", config) 
#         fg_pricing = AmazonPricingAdapter().get_pricing_summary(asin, region, config) 


#         def _pick_summary_for_region(summaries, region: str, cfg: dict):
#             if not summaries:
#                 return None
#             mpid = _get_mpid(region, cfg)
#             for s in summaries:
#                 try:
#                     if (s.get("marketplaceId") or s.get("marketplace_id") or "").strip() == mpid:
#                         return s
#                 except Exception:
#                     pass
#             for s in summaries:
#                 txt = (str(s) or "").lower()
#                 if "ja_jp" in txt or "japan" in txt or "jp" in txt:
#                     return s
#             return None

#         # --- 最終フォールバック（ここだけ追加） ---
#         if not category: 
#             category = (fg_category if region != "JP" else jp_category) 
#         if not image_url:
#             # 外国→JPの順で、トップ階層imagesから拾う 
#             cand = ((foreign_catalog or {}).get("images") or []) + ((jp_catalog or {}).get("images") or [])  
#             image_url = _pick_image_url(cand)  
        
#         # --- 画像：summaries内imagesも最終フォールバックで見る ---
#         if not image_url:  
#             s0b = _pick_summary_for_region((base_catalog or {}).get("summaries") or [], region, config) or (((base_catalog or {}).get("summaries") or [{}])[0])  
#             if isinstance(s0b, dict):  
#                 image_url = _pick_image_url(s0b.get("images") or [])  

#         # --- カテゴリ：JP側 summaries の productType を最終フォールバック ---
#         if (not category) or category == "--":  
#             s0j = _pick_summary_for_region((jp_catalog or {}).get("summaries") or [], "JP", config) or (((jp_catalog or {}).get("summaries") or [{}])[0])  
#             if isinstance(s0j, dict):  
#                 category = s0j.get("productType") or category  


#         # --- タイトル・ブランド（海外側） ---
#         fg_summary = _pick_summary_for_region(foreign_catalog.get("summaries") or [], region, config)

#         # --- UI互換のキーも同梱して返す（status: 'ok' を含める） ---
#         resp = {
#             "status": "ok",
#             "ok": True,
#             "region": region,
#             "asin": asin,

#             # 日本側
#             "jp_title": title,
#             "jp_brand": brand,
#             "title": title,
#             "brand": brand,
#             "manufacturer": (
#                 (attrs.get("manufacturer") or [{}])[0].get("value", "")
#                 if isinstance(attrs.get("manufacturer"), list)
#                 else attrs.get("manufacturer", "")
#             ),
            
#             # 寸法・重量（共通）
#             "item_dimensions": item_dimensions,
#             "package_dimensions": package_dimensions,
#             "item_weight": item_weight,
#             "package_weight": package_weight,
#             "length": _use_dim.get("length"),
#             "width":  _use_dim.get("width"),
#             "height": _use_dim.get("height"),
#             "weight": _use_w.get("value"),
#             "jp_pkg_len_cm": _use_dim.get("length"),
#             "jp_pkg_wid_cm": _use_dim.get("width"),
#             "jp_pkg_hei_cm": _use_dim.get("height"),
#             "jp_pkg_wt_kg":  _use_w.get("value"),

#             "attributes_raw": attrs,
#             "source": "sp-api/catalog-items/2022-04-01",

#             # EAN   
#             "ean": ean_value,
#             "fg_ean": _pick_ean_from_attrs((foreign_catalog or {}).get("attributes") or {}),

#             # --- 価格関連 ---
#             "jp_price": jp_pricing.get("list_price"), 
#             "price_cart_jpy": jp_pricing.get("buybox"), 
#             "price_lowest_new_jpy": jp_pricing.get("lowest_new"),  
#             "price_lowest_used_jpy": jp_pricing.get("lowest_used"),
#             "price_lowest_new_channel": jp_pricing.get("lowest_new_channel"), 
#             "jp_cart_seller": jp_pricing.get("cart_seller_name"),            

#             "fg_price": fg_pricing.get("list_price"),
#             "price_cart_foreign": fg_pricing.get("buybox"),
#             "price_lowest_new_foreign": fg_pricing.get("lowest_new"),
#             "price_lowest_used_foreign": fg_pricing.get("lowest_used"),
#             "price_lowest_new_channel_foreign": fg_pricing.get("lowest_new_channel"),
#             "fg_cart_seller": fg_pricing.get("cart_seller_name"), 

#             # --- タイトル・ブランド（海外側） ---
#             "fg_title": (fg_summary or {}).get("itemName") or "--",
#             "fg_brand": (fg_summary or {}).get("brand") or "--",
#             "fg_manufacturer": (fg_summary or {}).get("manufacturer") or "--",

#             # --- 外箱サイズ・重量（海外側） ---
#             "fg_pkg_len_cm": _use_dim.get("length"),
#             "fg_pkg_wid_cm": _use_dim.get("width"),
#             "fg_pkg_hei_cm": _use_dim.get("height"),
#             "fg_pkg_wt_kg":  _use_w.get("value"),                       

#             "category": category,
#             "image_url": image_url,

#             # ランキング情報
#             "jp_category": jp_category,
#             "jp_rank": jp_rank,
#             "fg_category": fg_category,
#             "fg_rank": fg_rank,

#             # --- 出品オファー情報（将来の大量ASIN処理用） ---
#             "offers": offers,

#             "message": None
#         }


#         # # ---- shipping を同梱（config反映の請求重量計算） ----
#         # L = float(resp.get("length") or 0.0)
#         # W = float(resp.get("width") or 0.0)
#         # H = float(resp.get("height") or 0.0)
#         # G = float(resp.get("weight") or 0.0)
#         # resp["shipping"] = calc_billable_weight(L, W, H, G)
#         # # -----------------------------------------------

#         return jsonify(resp), 200

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return jsonify({"status": "error", "message": str(e)}), 500        

# @amazon_bp.get("/api/get_dimensions") 
# def api_get_dimensions():
#     """
#     ASINとregion（US/AU/SG）を受け取り、Catalog Items 2022-04-01 から
#     dimensions（item/package の寸法・重量）を取得して返すテスト用API。
#     例: /amazon/api/get_dimensions?asin=B000XXXXXX&region=US
#     """
#     asin = (request.args.get("asin") or "").strip()
#     region = (request.args.get("region") or "").strip().upper()

#     if not asin or not region:
#         return jsonify({
#             "status": "error",
#             "message": "asin と region は必須です（region は US/AU/SG）"
#         }), 400

#     try:
#         data = get_item_dimensions(asin=asin, region=region)
#         resp = {
#             "status": "ok",
#             "asin": asin,
#             "region": region,
#             "dimensions": {
#                 "itemDimensions": data.get("itemDimensions"),
#                 "itemWeight": data.get("itemWeight"),
#                 "packageDimensions": data.get("packageDimensions"),
#                 "packageWeight": data.get("packageWeight"),
#             }
#         }
#         resp = inject_shipping_into_payload(resp)
#         return jsonify(resp), 200
#     except Exception as e:
#         return jsonify({
#             "status": "error",
#             "message": str(e)
#         }), 500


# # ブランドゲート
# SKIP_SELLERS_CHECK = True
# @amazon_bp.route("/api/brand_gate_check", methods=["POST"])
# def api_brand_gate_check():
#     try:
#         data = request.get_json(force=True) or {}
#         print("[DEBUG] brand_gate_check received:", data, flush=True)
#         asins = data.get("asins") or []
#         region = data.get("region")

#         # 循環参照回避のため関数内 import
#         from amazon.adapters.brand_gate_adapter import AmazonBrandGateAdapter

#         adapter = AmazonBrandGateAdapter(skip_sellers_check=True)
#         result = adapter.check_brand_gate(asins=asins, region=region)

#         status_code = 200 if result.get("status") == "ok" else 500
#         return jsonify(result), status_code

#     except Exception as e:
#         import traceback; traceback.print_exc()
#         return jsonify({"status": "error", "message": str(e)}), 500

# @amazon_bp.route("/_debug_inject")
# def _debug_inject():
#     asin = request.args.get("asin", "B0046EC9ZK")
#     region = request.args.get("region", "JP")
#     payload = {"asin": asin, "region": region}
#     result = inject_shipping_into_payload(payload)
#     return jsonify(result)

# @amazon_bp.route("/_debug_price")
# def _debug_price():
#     asin = request.args.get("asin", "B0046EC9ZK")
#     region = request.args.get("region", "JP")
#     cfg  = _load_config()
#     raw  = get_pricing_summary_raw(asin, region, cfg)
#     return jsonify(raw)

# @amazon_bp.route("/unlock_seller_ids", methods=["POST"])
# def unlock_seller_ids():
#     region = (request.json.get("region") or "").lower()
#     if not region:
#         return jsonify({"status": "error", "message": "regionが指定されていません"}), 400

#     lock_path = os.path.join(os.getcwd(), "runtime", "locks", f"extract_seller_ids_{region}.lock")
#     try:
#         if os.path.exists(lock_path):
#             os.remove(lock_path)
#             return jsonify({"status": "success", "message": f"{region} のロックを解除しました。"})
#         else:
#             return jsonify({"status": "success", "message": "ロックは存在しません。"})
#     except Exception as e:
#         return jsonify({"status": "error", "message": str(e)}), 500
