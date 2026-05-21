import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from utils.config_loader import get_debug_mode
import csv
import glob
from datetime import datetime
import sqlite3
from collections import Counter

BASE_DIR = os.path.dirname(__file__)
db_dir = os.path.abspath(os.path.join(BASE_DIR, "../db"))

db_files = {}

csv_import_bp = Blueprint("csv_import", __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@csv_import_bp.route("/upload", methods=["POST"])
def upload_csv():
    try:
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "ファイルが見つかりません"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "ファイル名が空です"}), 400

        filename = secure_filename(file.filename)
        upload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
        os.makedirs(upload_folder, exist_ok=True)

        # ✅ save_path を定義してから保存
        save_path = os.path.join(upload_folder, filename)
        file.save(save_path)

        # ✅ ヘッダーチェック
        with open(save_path, newline="", encoding="utf-8-sig") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader, None)

            if headers is None or len(headers) < 2:
                return jsonify({
                    "status": "error",
                    "message": "CSVのヘッダーが不足しています。ASIN,SKU の2列が必要です。"
                }), 400

            if headers[0].strip().upper() != "ASIN" or headers[1].strip().upper() != "SKU":
                return jsonify({
                    "status": "error",
                    "message": "CSVのフォーマットが不正です。1列目は『ASIN』、2列目は『SKU』にしてください。"
                }), 400

        return jsonify({"status": "success", "filename": filename, "path": save_path})
    except Exception as e:

        return jsonify({"status": "error", "message": str(e)}), 500

@csv_import_bp.route("/check", methods=["POST"])
def check_csv():
    try:
        # region と file を取得
        region = request.form.get("region")
        file = request.files.get("file")
        if not file or not region:
            return jsonify({"status": "error", "message": "ファイルまたはリージョンが指定されていません"}), 400

        # uploads/ に一時保存
        filename = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)

        # CSV 読み込み
        with open(save_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            asin_list = [row[0].strip() for row in reader if row]

        # DBチェック結果格納用
        ok_asins = []
        listed_asins = []
        blacklist_asins = {}

        # ブラックリストDBを自動検出
        import glob
        base_dir = os.path.dirname(__file__)
        db_dir = os.path.abspath(os.path.join(base_dir, "../db"))

        db_files = {}
        # 共通ブラックリスト
        all_db = os.path.join(db_dir, "a_all_blacklist_asin.db")
        if os.path.exists(all_db):
            db_files["All Blacklist"] = all_db

        # 国別ブラックリスト（a_xx_blacklist_asin.db を自動検出）
        for path in glob.glob(os.path.join(db_dir, "a_*_blacklist_asin.db")):
            parts = os.path.basename(path).split("_")
            if len(parts) >= 3 and parts[1] != "all":
                region_code = parts[1].upper()
                db_files[f"{region_code} Blacklist"] = path

        # ブラックリストチェック
        for asin in asin_list:
            reasons = []
            for reason, db_path in db_files.items():
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    cur = conn.cursor()
                    cur.execute("SELECT 1 FROM blacklist_asin WHERE asin = ?", (asin,))
                    if cur.fetchone():
                        reasons.append(reason)
                    conn.close()
            if reasons:
                blacklist_asins[asin] = " / ".join(reasons)

        # 出品済みDB確認
        listed_db = os.path.join(db_dir, f"a_{region.lower()}_listed_items.db")
        if os.path.exists(listed_db):
            conn = sqlite3.connect(listed_db)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS listed_items (
                    asin TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    brand TEXT,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (asin, sku)
                )
            """)
            for asin in asin_list:
                cur.execute("SELECT 1 FROM listed_items WHERE asin = ?", (asin,))
                if cur.fetchone():
                    listed_asins.append(asin)
            conn.close()

        # 出品可能ASIN = 全体 − ブラックリスト − 出品済み
        ok_asins = [
            asin for asin in asin_list
            if asin not in blacklist_asins and asin not in listed_asins
        ]

        # 完全削除
        os.remove(save_path)

        return jsonify({
            "status": "success",
            "ok": [
                {"asin": rec["asin"], "sku": rec["sku"]}
                for rec in records
                if rec["asin"] not in blacklist_asins and rec["asin"] not in listed_asins
            ],
            "blacklist": [
                {"asin": a, "reason": r}
                for a, r in blacklist_asins.items()
            ],
            "listed": [
                {"asin": asin, "sku": next((rec["sku"] for rec in records if rec["asin"] == asin), "")}
                for asin in listed_asins
            ]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# UI表示・仕分 & Pre-Listing登録
@csv_import_bp.route("/csv_import", methods=["POST"])
def import_csv():
    try:
        if "file" not in request.files and request.form.get("mode", "check") == "check":
            return jsonify({"status": "error", "message": "ファイルが見つかりません"}), 400

        # ▼ リージョン取得
        region = request.form.get("region", "").upper()
        if region not in ["US", "AU", "SG"]:
            return jsonify({"status": "error", "message": "不正なリージョンです"}), 400

        condition = request.form.get("condition", "NEW001")
        mode = request.form.get("mode", "check")

        listed_db = os.path.join(db_dir, f"a_{region.lower()}_listed_items.db")
        conn = sqlite3.connect(listed_db)
        cur = conn.cursor()

        if mode == "check":
            # ▼ CSVアップロードして仕分け
            file = request.files["file"]
            if file.filename == "":
                return jsonify({"status": "error", "message": "ファイル名が空です"}), 400

            # ▼ ファイル名チェック（先頭2文字とregion一致）
            filename = secure_filename(file.filename)
            if not filename[:2].upper() == region:
                return jsonify({
                    "status": "error",
                    "message": f"リージョンとファイル名が一致しません（リージョン={region}, ファイル={filename}）"
                }), 400

            save_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(save_path)

            asin_list = []
            with open(save_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f, delimiter=",")
                headers = next(reader, None)

                # ✅ ヘッダーチェック
                if headers is None or len(headers) < 2:
                    return jsonify({
                        "status": "error",
                        "message": "CSVのヘッダーが不足しています。ASIN,SKU の2列が必要です。"
                    }), 400

                if headers[0].strip().upper() != "ASIN" or headers[1].strip().upper() != "SKU":
                    return jsonify({
                        "status": "error",
                        "message": "CSVのフォーマットが不正です。1列目は『ASIN』、2列目は『SKU』にしてください。"
                    }), 400

                # ▼ データ読み込み (ASIN + SKU)
                records = []
                for row in reader:
                    if row and row[0].strip():
                        asin = row[0].strip()         
                        sku  = row[1].strip() if len(row) > 1 and row[1].strip() else ""
                        records.append({"asin": asin, "sku": sku})

                # ✅ ASIN重複チェック
                from collections import Counter
                asin_counter = Counter([r["asin"] for r in records])
                if any(count > 1 for count in asin_counter.values()):
                    return jsonify({
                        "status": "error",
                        "message": "CSVにASINの重複があります。"
                    }), 400

                # ✅ SKU重複チェック（空白は無視）
                sku_values = [r["sku"] for r in records if r["sku"]]
                sku_counter = Counter(sku_values)
                if any(count > 1 for count in sku_counter.values()):
                    return jsonify({
                        "status": "error",
                        "message": "CSVにSKUの重複があります。"
                    }), 400

            # ▼ ブラックリストチェック
            blacklist_asins = {}
            all_db = os.path.join(db_dir, "a_all_blacklist_asin.db")
            region_db = os.path.join(db_dir, f"a_{region.lower()}_blacklist_asin.db")
            blacklist_paths = [p for p in [all_db, region_db] if os.path.exists(p)]

            for rec in records:
                asin = rec["asin"]
                reasons = []
                for db_path in blacklist_paths:
                    conn_bl = sqlite3.connect(db_path)
                    cur_bl = conn_bl.cursor()
                    cur_bl.execute("SELECT 1 FROM blacklist_asin WHERE asin = ?", (asin,))
                    if cur_bl.fetchone():
                        reasons.append(os.path.basename(db_path))
                    conn_bl.close()
                if reasons:
                    blacklist_asins[asin] = " / ".join(reasons)

            # ▼ 出品済みチェック
            listed_asins = {}
            for rec in records:
                asin = rec["asin"]
                cur.execute("SELECT 1 FROM listed_items WHERE asin = ?", (asin,))
                if cur.fetchone():
                    listed_asins[asin] = rec.get("sku", "")

            # ▼ SKU割り振り
            today = datetime.now().strftime("%Y%m%d")
            for rec in records:
                if not rec["sku"]:
                    rec["sku"] = f"Z_{region}_{rec['asin']}_{today}_{condition}"

            # ▼ 出品可能ASIN（仕分け結果）
            ok_asins = [
                {"asin": rec["asin"], "sku": rec["sku"]}
                for rec in records
                if rec["asin"] not in blacklist_asins and rec["asin"] not in listed_asins
            ]

            os.remove(save_path)
            conn.close()

            return jsonify({
                "status": "success",
                "ok": ok_asins,
                "blacklist": [{"asin": a, "sku": "", "reason": r} for a, r in blacklist_asins.items()],
                "listed": [{"asin": a, "sku": s, "reason": "ASIN already exists"} for a, s in listed_asins.items()],
                "total_count": len(records),
            })

        elif mode == "commit":
            # ▼ OKタブのASINとSKUを受け取る
            asins = request.form.getlist("asins[]")
            skus = request.form.getlist("skus[]")  # ← フロントから一緒に送る想定
            today = datetime.now().strftime("%Y%m%d")

            for asin, sku in zip(asins, skus):
                if not sku:  # 空欄なら自動割り振り
                    sku = f"Z_{region}_{asin}_{today}_{condition}"

                cur.execute("""
                    INSERT OR IGNORE INTO listed_items (asin, sku, status, created_at, updated_at)
                    VALUES (?, ?, 'pre', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (asin, sku))

            conn.commit()
            conn.close()
            return jsonify({"status": "success", "count": len(asins)})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# 保存先は zsss_web/uploads 固定
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


