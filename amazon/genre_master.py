# genre_master.py
# 「ジャンル分析」が自動検出した大分類（Department）の保存・取得。
# 手動で登録するcategory_master.dbとは別のDBに分けて、混ざらないようにしている。

import os
import sqlite3

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
DB_PATH = os.path.join(DB_DIR, "genre_master.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_genre(marketplace, category_name, node_id, item_count=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO genre_master
        (
            marketplace,
            category_name,
            node_id,
            item_count
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(marketplace, category_name)

        DO UPDATE SET
            node_id = excluded.node_id,
            item_count = excluded.item_count,
            updated_at = CURRENT_TIMESTAMP
    """, (marketplace, category_name, node_id, item_count))

    conn.commit()
    conn.close()


def save_genre_history(marketplace, seller_id, category_name, node_id, item_count, run_at):
    """1回のジャンル分析実行の結果を1行として履歴に残す（上書きしない）。"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO genre_history
        (marketplace, seller_id, category_name, node_id, item_count, run_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (marketplace, seller_id, category_name, node_id, item_count, run_at))
    conn.commit()
    conn.close()


def get_genre_history(marketplace, seller_id):
    """このセラーに対するジャンル分析の実行履歴を、実行日時ごとにまとめて返す。
    戻り値: [{"run_at": "...", "genres": [{"name":..., "node_id":..., "count":...}, ...]}, ...]
    新しい実行が先頭に来るよう降順で返す。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT run_at, category_name, node_id, item_count
        FROM genre_history
        WHERE marketplace = ? AND seller_id = ?
        ORDER BY run_at DESC, item_count DESC
    """, (marketplace, seller_id))
    rows = cur.fetchall()
    conn.close()

    runs = {}
    order = []
    for row in rows:
        run_at = row["run_at"]
        if run_at not in runs:
            runs[run_at] = []
            order.append(run_at)
        runs[run_at].append({
            "name": row["category_name"],
            "node_id": row["node_id"],
            "count": row["item_count"],
        })

    return [{"run_at": run_at, "genres": runs[run_at]} for run_at in order]


def get_genre_list(marketplace):
    """この marketplace でこれまでに検出済みの大分類一覧を (category_name, node_id) で返す。"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT category_name, node_id
        FROM genre_master
        WHERE marketplace = ?
        ORDER BY category_name COLLATE NOCASE
    """, (marketplace,))

    rows = cur.fetchall()
    conn.close()

    return [{"name": row["category_name"], "node_id": row["node_id"]} for row in rows]
