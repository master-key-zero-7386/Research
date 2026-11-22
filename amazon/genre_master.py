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
