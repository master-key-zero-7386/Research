# ファイル名：routes_listing.py

from flask import Blueprint, request, jsonify, current_app
import os
from amazon.db import get_conn
from utils.spapi_client import real_signed_request, _get_mpid
from amazon.listing_info.product import build_product_block
from amazon.listing_info.image import build_image_block

listing_bp = Blueprint("listing_bp", __name__)

def _unwrap_catalog(resp):
    """
    Catalog API レスポンスから payload 部分を抽出
    """
    if not resp:
        return {}
    if isinstance(resp, dict):
        return resp.get("payload") or resp
    try:
        return resp.json().get("payload") or resp.json()
    except Exception:
        return resp

@listing_bp.post("/listing/add")
def add_listing():
    try:
        data = request.get_json(force=True, silent=True) or {}
        items  = data.get("items") or []
        region = (data.get("region") or "").strip().upper()

        if not items:
            return jsonify({"status": "error", "message": "No items provided"}), 400
        if region not in ("US", "AU", "SG"):
            return jsonify({"status": "error", "message": "Invalid region"}), 400

        # DBファイル名を決定
        db_name = f"a_{region.lower()}_listed_items.db"
        conn = get_conn(db_name)
        cur = conn.cursor()

        ok = []
        listed = []
        blacklist = []
        errors = []

        for item in items:
            asin = (item.get("asin") or "").strip().upper()
            sku  = (item.get("sku") or "").strip()
            if not asin or not sku:
                errors.append({"asin": asin, "sku": sku, "reason": "ASIN or SKU missing"})
                continue

            # デバッグ: DBに入っているASINを全部確認
            cur.execute("SELECT asin FROM listed_items")
            all_asins = [r[0] for r in cur.fetchall()]

            # 重複チェックはASINだけ
            cur.execute("SELECT 1 FROM listed_items WHERE asin=?", (asin,))
            row = cur.fetchone()


            if row:
                listed.append({"asin": asin, "sku": sku})
                continue

            # 登録
            cur.execute(
                """
                INSERT INTO listed_items 
                    (asin, sku, jp_title, region_title, jp_brand, region_brand, status, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (asin, sku, "", "", "", "", "pre", "")
            )
            ok.append({"asin": asin, "sku": sku})

        conn.commit()

        # Pre-Listing 一覧を取得
        cur.execute("""
            SELECT asin, sku, jp_title, region_title, jp_brand, region_brand, image_url
            FROM listed_items
            WHERE status='pre'
        """)
        pre_items = [{
            "asin": r[0],
            "sku": r[1],
            "jp_title": r[2] or "",
            "region_title": r[3] or "",
            "jp_brand": r[4] or "",
            "region_brand": r[5] or "",
            "image_url": r[6] or ""
        } for r in cur.fetchall()]
        
        return jsonify({
            "status": "success",
            "ok": ok,
            "listed": listed,
            "blacklist": blacklist,
            "errors": errors,
            "pre": pre_items
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@listing_bp.route("/get_prelisting", methods=["GET"])
def get_prelisting():
    try:
        region = request.args.get("region", "").upper()
        db_file = f"a_{region.lower()}_listed_items.db"

        conn = get_conn(db_file)
        cur = conn.cursor()
        cur.execute("""
            SELECT asin, sku, jp_title, region_title, jp_brand, region_brand
            FROM listed_items
            WHERE status='pre'
        """)
        rows = cur.fetchall()
        conn.close()

        pre_items = []
        for row in rows:
            pre_items.append({
                "asin": row[0],
                "sku": row[1],
                "jp_title": row[2],
                "region_title": row[3],
                "jp_brand": row[4],
                "region_brand": row[5],
            })

        return jsonify({"status": "success", "pre": pre_items})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@listing_bp.post("/listing/fetch_item_info")
def fetch_item_info():
    data = request.get_json(force=True)
    asin = (data.get("asin") or "").strip().upper()
    region = (data.get("region") or "").strip().upper()

    if not asin or not region:
        return jsonify({"status": "error", "message": "asin and region required"}), 400

    try:
        # まず DB を確認
        db_file = f"a_{region.lower()}_listed_items.db"
        conn = get_conn(db_file)
        cur = conn.cursor()
        cur.execute("""
            SELECT jp_brand, jp_title, region_brand, region_title, image_url
            FROM listed_items WHERE asin = ?
        """, (asin,))
        row = cur.fetchone()

        if row:
            jp_brand, jp_title, region_brand, region_title, image_url = row
            if all([jp_brand, jp_title, region_brand, region_title, image_url]):
                conn.close()
                return jsonify({
                    "status": "ok",
                    "asin": asin,
                    "jp_brand": jp_brand or "",
                    "jp_title": jp_title or "",
                    "region_brand": region_brand or "",
                    "region_title": region_title or "",
                    "image_url": image_url or ""
                })
        conn.close()

        # ---- ここから下は「欠けている場合だけ」API呼び出し ----

        import json, os
        cfg = current_app.config
        try:
            has_jp = bool(((cfg.get("marketplace") or {}).get("JP") or {}).get("marketplace_id"))
        except Exception:
            has_jp = False
        if not has_jp:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        def _call_catalog(asin_, region_code, locale=None):
            mpid = _get_mpid(region_code, cfg)
            host = ((cfg.get("marketplace") or {}).get(region_code) or {}).get("host") \
                   or "https://sellingpartnerapi-fe.amazon.com"
            path = f"/catalog/2022-04-01/items/{asin_}"
            params = {
                "marketplaceIds": [mpid],
                "includedData": "summaries,attributes,images"
            }
            if locale:
                params["locale"] = locale
            r = real_signed_request("GET", path, params=params, host=host, cfg=cfg)
            return _unwrap_catalog(r)

            try:
                catalog_jp = _call_catalog(asin, "JP", locale="ja_JP")
            except Exception as e:
                print(f"[DEBUG] JP catalog fetch failed for {asin}: {e}", flush=True)
                catalog_jp = {}

            try:
                catalog_rg = _call_catalog(asin, region)
            except Exception as e:
                print(f"[DEBUG] {region} catalog fetch failed for {asin}: {e}", flush=True)
                catalog_rg = {}

        product_data = build_product_block(asin, region, catalog_jp, catalog_rg)
        image_data = build_image_block(asin, region, catalog_jp, catalog_rg)

        return jsonify({
            "status": "ok",
            "asin": asin,
            **product_data,
            **image_data
        })

    except Exception as e:
        return jsonify({"status": "error", "asin": asin, "message": str(e)})





