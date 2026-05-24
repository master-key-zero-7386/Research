# ===========================================================
# セラーリスト CSV 簡易取り込み
# ファイル：C:\zsss_research_dev\db\import_sellerlist_csv.py
# ===========================================================
# CMDで以下を実行
# (research_env) c:\zsss_research_dev>python db\import_sellerlist_csv.py
# --------------------------

import csv
import sqlite3

# ※※　簡易版なのでcountry code ベタ書き変更して利用 保管場所のパスを確認----------------
csv_path = r"c:\zsss_research_dev\lists\ca_seller_list.csv"
db_path = r"c:\zsss_research_dev\db\a_ca_seller_list.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

with open(csv_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)

    for row in reader:

        cur.execute("""
            INSERT OR IGNORE INTO seller_list (
                seller_id,
                shop_name,
                created_at,
                last_used
            )
            VALUES (?, ?, ?, ?)
        """, (
            row["seller_id"],
            row["shop_name"],
            row["first_recorded"],
            row["last_extracted"]
        ))

conn.commit()
conn.close()

print("IMPORT OK")