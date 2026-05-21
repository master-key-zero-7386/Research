import sqlite3
import csv
import sys
import os

def import_csv_to_db(table, db_path, csv_path):
    if not os.path.exists(csv_path):
        print(f"❌ CSVファイルが見つかりません: {csv_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    added, skipped = 0, 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # ✅ ヘッダーをスキップ
        for row in reader:
            if not row:
                continue

            if table == "blacklist_asin":
                asin = row[0].strip()
                note = row[1].strip() if len(row) > 1 else ""
                if not asin:
                    continue
                cursor.execute("SELECT 1 FROM blacklist_asin WHERE asin = ?", (asin,))
                if cursor.fetchone():
                    skipped += 1
                    continue
                cursor.execute(
                    "INSERT INTO blacklist_asin (asin, note) VALUES (?, ?)",
                    (asin, note)
                )

            elif table == "blacklist_brand":
                brand = row[0].strip()
                note = row[1].strip() if len(row) > 1 else ""
                if not brand:
                    continue
                cursor.execute("SELECT 1 FROM blacklist_brand WHERE brand_name = ?", (brand,))
                if cursor.fetchone():
                    skipped += 1
                    continue
                cursor.execute(
                    "INSERT INTO blacklist_brand (brand_name, note) VALUES (?, ?)",
                    (brand, note)
                )

            elif table == "seller_list":
                # CSV構成: id, seller_id, shop_name, hidden, remarks, review_lifetime, created_at
                seller_id = row[1].strip() if len(row) > 1 else ""
                shop_name = row[2].strip() if len(row) > 2 else ""
                hidden = int(row[3].strip()) if len(row) > 3 and row[3].strip().isdigit() else 0
                remarks = row[4].strip() if len(row) > 4 else ""
                review_lifetime = int(row[5].strip()) if len(row) > 5 and row[5].strip().isdigit() else 0
                if not seller_id:
                    continue
                cursor.execute("SELECT 1 FROM seller_list WHERE seller_id = ?", (seller_id,))
                if cursor.fetchone():
                    skipped += 1
                    continue
                cursor.execute(
                    "INSERT INTO seller_list (seller_id, shop_name, hidden, remarks, review_lifetime) VALUES (?, ?, ?, ?, ?)",
                    (seller_id, shop_name, hidden, remarks, review_lifetime)
                )

            else:
                print(f"❌ 未対応のテーブル指定: {table}")
                conn.close()
                return

            added += 1

    conn.commit()
    conn.close()
    print(f"✅ {table} インポート完了: {added}件追加、{skipped}件スキップ")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("使い方: python import_from_csv.py <table> <db_path> <csv_path>")
        sys.exit(1)

    import_csv_to_db(sys.argv[1], sys.argv[2], sys.argv[3])

