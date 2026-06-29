#　ファイル名：routes.py

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
from .constants import BASE_DIR, CONFIG_PATH
from utils.config_loader import cfg, get_debug_mode
from send2trash import send2trash
from flask import url_for 
import sqlite3 

DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
from .a_02extract_asin_list import run_asin_extraction

bp = Blueprint("amazon", __name__)
amazon_bp = bp

TRASH_DIR = os.path.join(BASE_DIR, "tool_trash") 
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

@amazon_bp.route("/delete_seller", methods=["POST"])
def delete_seller():
    try:
        region = request.form.get("region", "").upper()
        seller_id = request.form.get("seller_id", "").strip()

        if not region or not seller_id:
            return jsonify({
                "status": "error",
                "message": "region または seller_id が指定されていません。"
            }), 400

        db_path = os.path.join(BASE_DIR, "db", "seller_list.db")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM seller_list
            WHERE country_code = ?
              AND seller_id = ?
        """, (region, seller_id))

        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "削除しました。"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
        
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
                SELECT seller_id, shop_name, hidden
                FROM seller_list
                WHERE country_code = ?
                ORDER BY shop_name COLLATE NOCASE ASC
                """,
                (region.upper(),)
            )

        else:
            cursor.execute(
                """
                SELECT seller_id, shop_name, hidden
                FROM seller_list
                WHERE country_code = ? AND hidden = 0
                ORDER BY shop_name COLLATE NOCASE ASC
                """,
                (region.upper(),)
            )

        rows = cursor.fetchall()
        conn.close()

        for seller_id, shop_name, hidden in rows:
            seller_list.append({
                "seller_id": seller_id,
                "seller_name": shop_name,
                "hidden": hidden
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


