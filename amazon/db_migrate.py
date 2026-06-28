import os
import sqlite3
import glob

# DBフォルダ
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
os.makedirs(DB_DIR, exist_ok=True)

def get_conn(db_name: str):
    """指定DBに接続（なければ新規作成）"""
    db_path = os.path.join(DB_DIR, db_name)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# --- スキーマ定義 ---
LISTED_ITEMS_COLUMNS = {
    "asin": "TEXT NOT NULL",
    "sku": "TEXT NOT NULL",
    "jp_title": "TEXT",
    "region_title": "TEXT",
    "jp_brand": "TEXT",
    "region_brand": "TEXT",
    "image_url": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'pre'",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
}

BLACKLIST_ASIN_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "asin": "TEXT NOT NULL",
    "note": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
}

BLACKLIST_BRAND_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "Brand": "TEXT NOT NULL",
    "Rank": "TEXT",
    "note": "TEXT",
    "JapanBrand": "TEXT",
    "timestamp": "TIMESTAMP"
}

SELLER_LIST_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "country_code": "TEXT DEFAULT ''",
    "seller_id": "TEXT NOT NULL",
    "shop_name": "TEXT",
    "hidden": "INTEGER NOT NULL DEFAULT 0",
    "remarks": "TEXT",
    "review_lifetime": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "last_used": "INTEGER DEFAULT 0"
}

BRAND_MASTER_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "marketplace": "TEXT NOT NULL",
    "brand_name": "TEXT NOT NULL",
    "brand_id": "TEXT NOT NULL",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
}



def get_existing_columns(conn, table_name):
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table_name})")
        return [row[1].lower() for row in cur.fetchall()]  # 小文字化して返す
    except sqlite3.OperationalError:
        return []

def migrate_table(conn, table_name, schema_dict):
    existing = get_existing_columns(conn, table_name)
    cur = conn.cursor()

    if not existing:

        if table_name == "brand_master":
            cur.execute("""
                CREATE TABLE brand_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    marketplace TEXT NOT NULL,
                    brand_name TEXT NOT NULL,
                    brand_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (marketplace, brand_name)
                )
            """)
        else:
            cols_def = ", ".join([f"{col} {dtype}" for col, dtype in schema_dict.items()])
            cur.execute(f"CREATE TABLE {table_name} ({cols_def})")

        print(f"[CREATE] {table_name}")
    else:
        # カラム追加（DEFAULT CURRENT_TIMESTAMP は外す）
        for col, dtype in schema_dict.items():
            if col.lower() not in existing:
                dtype_no_default = dtype.replace("DEFAULT CURRENT_TIMESTAMP", "").strip()
                cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {dtype_no_default}")
                print(f"[ALTER] {table_name}: add {col}")

    conn.commit()

def migrate_db(db_name):
    conn = get_conn(db_name)
    base = os.path.basename(db_name)

    if base == "seller_list.db":
        migrate_table(conn, "seller_list", SELLER_LIST_COLUMNS)

    elif base == "brand_master.db":
        migrate_table(conn, "brand_master", BRAND_MASTER_COLUMNS)

    conn.close()
    print(f"[OK] migrated: {db_name}")

# --- メイン処理 ---
def main():
    os.makedirs(DB_DIR, exist_ok=True)

    migrate_db("seller_list.db")
    migrate_db("brand_master.db")    

if __name__ == "__main__":
    main()


