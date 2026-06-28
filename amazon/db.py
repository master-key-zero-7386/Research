# ファイル名：db.py

import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
os.makedirs(DATA_DIR, exist_ok=True)

def get_conn(db_name):
    """指定されたDBに接続（なければ新規作成）"""
    db_path = os.path.join(DATA_DIR, db_name)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn



