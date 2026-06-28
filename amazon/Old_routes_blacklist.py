from flask import Blueprint, request, jsonify
from .db import get_conn
import os

blacklist_bp = Blueprint("blacklist_bp", __name__)

def _get_db_path(region=None):
    """対象リージョンに応じたDB名を返す（デフォルトは all）"""
    if region and region.lower() in ("us", "au", "sg"):
        return f"a_{region.lower()}_blacklist_asin.db"
    return "a_all_blacklist_asin.db"

@blacklist_bp.get("/<region>")
def get_blacklist(region):
    db_name = _get_db_path(region)
    conn = get_conn(db_name)
    cur = conn.cursor()
    cur.execute("SELECT id, asin, note, created_at FROM blacklist_asin ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"status": "success", "rows": rows})

@blacklist_bp.post("/<region>")
def post_blacklist(region):
    db_name = _get_db_path(region)
    data = request.get_json(force=True, silent=True) or {}
    asin   = (data.get("asin") or "").strip().upper()
    note   = (data.get("note") or "").strip()

    if not asin:
        return jsonify({"status": "error", "message": "asin required"}), 400

    conn = get_conn(db_name)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO blacklist_asin (asin, note)
        VALUES (?, ?)
        ON CONFLICT(asin) DO UPDATE SET
            note=excluded.note
    """, (asin, note))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@blacklist_bp.delete("/<region>")
def delete_item(region):
    db_name = _get_db_path(region)
    data = request.get_json(force=True, silent=True) or {}
    asin = (data.get("asin") or "").strip().upper()

    if not asin:
        return jsonify({"status": "error", "message": "asin required"}), 400

    conn = get_conn(db_name)
    cur = conn.cursor()
    cur.execute("DELETE FROM blacklist_asin WHERE asin=?", (asin,))
    affected = cur.rowcount
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "deleted": affected})
