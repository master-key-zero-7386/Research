# ファイル名：import_seller_list
# 目的：旧DBから新DBへの移植用
# DB合成などに利用できる可能性があるので削除セず残す

# ==========================================
# seller_list 移行ツール
# 旧DB → 新 seller_list.db
# ==========================================

import sqlite3
from pathlib import Path

BASE = Path(__file__).parent

NEW_DB = BASE / "seller_list.db"

OLD_DBS = [
    ("US", BASE / "a_us_seller_list.db"),
    ("AU", BASE / "a_au_seller_list.db"),
    ("CA", BASE / "a_ca_seller_list.db"),
    ("SG", BASE / "a_sg_seller_list.db"),
]

new_conn = sqlite3.connect(NEW_DB)
new_cur = new_conn.cursor()

for country_code, old_db in OLD_DBS:

    if not old_db.exists():
        print(f"SKIP : {old_db.name}")
        continue

    old_conn = sqlite3.connect(old_db)
    old_conn.row_factory = sqlite3.Row
    old_cur = old_conn.cursor()

    rows = old_cur.execute("""
        SELECT
            seller_id,
            shop_name,
            hidden,
            remarks,
            created_at,
            last_used
        FROM seller_list
    """).fetchall()

    count = 0

    for row in rows:

        new_cur.execute("""
            INSERT OR IGNORE INTO seller_list (
                country_code,
                seller_id,
                shop_name,
                hidden,
                remarks,
                created_at,
                last_used
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            country_code,
            row["seller_id"],
            row["shop_name"],
            row["hidden"],
            row["remarks"],
            row["created_at"],
            row["last_used"]

        ))

        if new_cur.rowcount == 1:
            count += 1        

    old_conn.close()

    print(f"{country_code} : {count} 件")

new_conn.commit()
new_conn.close()

print("完了")


