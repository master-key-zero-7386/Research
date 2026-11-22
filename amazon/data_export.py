# data_export.py
# 各データ（セラー一覧／ブランドマスタ／カテゴリーマスタ／ジャンル分析データ）の
# エクスポート（バックアップ・他PCへの移行用）とインポートをまとめたモジュール。

from datetime import datetime
from amazon.db_migrate import get_conn

DATASETS = ["seller_list", "brand_master", "category_master", "genre_master"]


def _rows_to_dicts(cur):
    return [dict(row) for row in cur.fetchall()]


def get_counts(regions=None):
    """regions: 大文字の国コード一覧（["AU","US"]）。空/Noneなら全件対象。"""
    upper_regions = [r.upper() for r in regions] if regions else []
    lower_regions = [r.lower() for r in regions] if regions else []
    counts = {}

    conn = get_conn("seller_list.db")
    cur = conn.cursor()
    if upper_regions:
        placeholders = ",".join("?" for _ in upper_regions)
        cur.execute(f"SELECT COUNT(*) FROM seller_list WHERE country_code IN ({placeholders})", upper_regions)
    else:
        cur.execute("SELECT COUNT(*) FROM seller_list")
    counts["seller_list"] = cur.fetchone()[0]
    conn.close()

    for db_name, table in (("brand_master.db", "brand_master"), ("category_master.db", "category_master")):
        conn = get_conn(db_name)
        cur = conn.cursor()
        if lower_regions:
            placeholders = ",".join("?" for _ in lower_regions)
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE marketplace IN ({placeholders})", lower_regions)
        else:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cur.fetchone()[0]
        conn.close()

    conn = get_conn("genre_master.db")
    cur = conn.cursor()
    if lower_regions:
        placeholders = ",".join("?" for _ in lower_regions)
        cur.execute(f"SELECT COUNT(*) FROM genre_master WHERE marketplace IN ({placeholders})", lower_regions)
    else:
        cur.execute("SELECT COUNT(*) FROM genre_master")
    counts["genre_master"] = cur.fetchone()[0]

    if lower_regions:
        placeholders = ",".join("?" for _ in lower_regions)
        cur.execute(f"SELECT COUNT(*) FROM genre_history WHERE marketplace IN ({placeholders})", lower_regions)
    else:
        cur.execute("SELECT COUNT(*) FROM genre_history")
    counts["genre_history"] = cur.fetchone()[0]
    conn.close()

    return counts


def export_data(datasets, regions=None):
    """datasets: DATASETSのキーのリスト。regions: 大文字の国コード一覧（空/Noneなら全件）。"""
    upper_regions = [r.upper() for r in regions] if regions else []
    lower_regions = [r.lower() for r in regions] if regions else []

    payload = {
        "tool": "research_tool",
        "export_version": 1,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "data": {},
    }

    if "seller_list" in datasets:
        conn = get_conn("seller_list.db")
        cur = conn.cursor()
        if upper_regions:
            placeholders = ",".join("?" for _ in upper_regions)
            cur.execute(
                f"SELECT country_code, seller_id, shop_name, hidden, remarks, last_used "
                f"FROM seller_list WHERE country_code IN ({placeholders})",
                upper_regions,
            )
        else:
            cur.execute("SELECT country_code, seller_id, shop_name, hidden, remarks, last_used FROM seller_list")
        payload["data"]["seller_list"] = _rows_to_dicts(cur)
        conn.close()

    if "brand_master" in datasets:
        conn = get_conn("brand_master.db")
        cur = conn.cursor()
        if lower_regions:
            placeholders = ",".join("?" for _ in lower_regions)
            cur.execute(
                f"SELECT marketplace, brand_name, brand_id FROM brand_master WHERE marketplace IN ({placeholders})",
                lower_regions,
            )
        else:
            cur.execute("SELECT marketplace, brand_name, brand_id FROM brand_master")
        payload["data"]["brand_master"] = _rows_to_dicts(cur)
        conn.close()

    if "category_master" in datasets:
        conn = get_conn("category_master.db")
        cur = conn.cursor()
        if lower_regions:
            placeholders = ",".join("?" for _ in lower_regions)
            cur.execute(
                f"SELECT marketplace, category_name, node_id FROM category_master "
                f"WHERE marketplace IN ({placeholders})",
                lower_regions,
            )
        else:
            cur.execute("SELECT marketplace, category_name, node_id FROM category_master")
        payload["data"]["category_master"] = _rows_to_dicts(cur)
        conn.close()

    if "genre_master" in datasets:
        conn = get_conn("genre_master.db")
        cur = conn.cursor()
        if lower_regions:
            placeholders = ",".join("?" for _ in lower_regions)
            cur.execute(
                f"SELECT marketplace, category_name, node_id, item_count FROM genre_master "
                f"WHERE marketplace IN ({placeholders})",
                lower_regions,
            )
        else:
            cur.execute("SELECT marketplace, category_name, node_id, item_count FROM genre_master")
        genres = _rows_to_dicts(cur)

        if lower_regions:
            cur.execute(
                f"SELECT marketplace, seller_id, category_name, node_id, item_count, run_at "
                f"FROM genre_history WHERE marketplace IN ({placeholders})",
                lower_regions,
            )
        else:
            cur.execute(
                "SELECT marketplace, seller_id, category_name, node_id, item_count, run_at FROM genre_history"
            )
        history = _rows_to_dicts(cur)
        conn.close()

        payload["data"]["genre_master"] = {"genres": genres, "history": history}

    return payload


def import_data(payload):
    """エクスポートされたJSONを取り込む。既存と同じキー（セラーID・ブランド名等）は上書き更新、
    無ければ追加する。ジャンル分析履歴（genre_history）は上書きキーを持たないログのため、
    同一内容の再取り込みは重複登録しない（INSERT OR IGNORE + 専用UNIQUE INDEX）。
    戻り値: 取り込んだデータセットごとの件数。"""
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    result = {}

    if "seller_list" in data:
        conn = get_conn("seller_list.db")
        n = 0
        for row in data["seller_list"]:
            conn.execute(
                """
                INSERT INTO seller_list (country_code, seller_id, shop_name, hidden, remarks, last_used)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(country_code, seller_id) DO UPDATE SET
                    shop_name = excluded.shop_name,
                    hidden = excluded.hidden,
                    remarks = excluded.remarks,
                    last_used = excluded.last_used
                """,
                (
                    row.get("country_code", ""),
                    row.get("seller_id", ""),
                    row.get("shop_name"),
                    row.get("hidden", 0),
                    row.get("remarks"),
                    row.get("last_used", 0),
                ),
            )
            n += 1
        conn.commit()
        conn.close()
        result["seller_list"] = n

    if "brand_master" in data:
        conn = get_conn("brand_master.db")
        n = 0
        for row in data["brand_master"]:
            conn.execute(
                """
                INSERT INTO brand_master (marketplace, brand_name, brand_id)
                VALUES (?, ?, ?)
                ON CONFLICT(marketplace, brand_name) DO UPDATE SET
                    brand_id = excluded.brand_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (row.get("marketplace"), row.get("brand_name"), row.get("brand_id")),
            )
            n += 1
        conn.commit()
        conn.close()
        result["brand_master"] = n

    if "category_master" in data:
        conn = get_conn("category_master.db")
        n = 0
        for row in data["category_master"]:
            conn.execute(
                """
                INSERT INTO category_master (marketplace, category_name, node_id)
                VALUES (?, ?, ?)
                ON CONFLICT(marketplace, category_name) DO UPDATE SET
                    node_id = excluded.node_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (row.get("marketplace"), row.get("category_name"), row.get("node_id")),
            )
            n += 1
        conn.commit()
        conn.close()
        result["category_master"] = n

    if "genre_master" in data:
        genre_data = data["genre_master"] or {}
        conn = get_conn("genre_master.db")

        n_genres = 0
        for row in genre_data.get("genres", []):
            conn.execute(
                """
                INSERT INTO genre_master (marketplace, category_name, node_id, item_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(marketplace, category_name) DO UPDATE SET
                    node_id = excluded.node_id,
                    item_count = excluded.item_count,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (row.get("marketplace"), row.get("category_name"), row.get("node_id"), row.get("item_count")),
            )
            n_genres += 1

        n_history = 0
        for row in genre_data.get("history", []):
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO genre_history
                (marketplace, seller_id, category_name, node_id, item_count, run_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("marketplace"),
                    row.get("seller_id"),
                    row.get("category_name"),
                    row.get("node_id"),
                    row.get("item_count"),
                    row.get("run_at"),
                ),
            )
            if cur.rowcount:
                n_history += 1

        conn.commit()
        conn.close()
        result["genre_master"] = n_genres
        result["genre_history"] = n_history

    return result
