
# category_master.py
# リサーチ用カテゴリーノードID 取得保存

import os
import re
import sqlite3
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
DB_PATH = os.path.join(DB_DIR, "category_master.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_category_node_id(driver, marketplace, category_name, seller_id=None, brand_filter=None):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT node_id
        FROM category_master
        WHERE marketplace = ?
          AND LOWER(category_name)=LOWER(?)
        LIMIT 1
    """,(marketplace,category_name))

    row=cur.fetchone()

    conn.close()

    if row:
        return row["node_id"]

    return fetch_category_node_id(
        driver,
        marketplace,
        category_name,
        seller_id,
        brand_filter
    )


def save_category_node_id(marketplace, category_name, node_id):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO category_master
        (
            marketplace,
            category_name,
            node_id
        )
        VALUES (?, ?, ?)

        ON CONFLICT(marketplace, category_name)

        DO UPDATE SET
            node_id = excluded.node_id,
            updated_at = CURRENT_TIMESTAMP
    """, (marketplace, category_name, node_id))

    conn.commit()
    conn.close()

def fetch_category_node_id(driver, marketplace, category_name, seller_id=None, brand_filter=None):

    domain = {
        "ca": "amazon.ca",
        "us": "amazon.com",
        "au": "amazon.com.au",
        "jp": "amazon.co.jp"
    }[marketplace.lower()]

    # ✅ 実際の検索（セラー・ブランド）の絞り込み結果ページから部門を探す。
    # カテゴリー名自体をキーワード検索すると、無関係な結果になり部門が一致しない。
    parts = []
    if seller_id and "すべて" not in seller_id:
        parts.append(f"me={seller_id}")
    if brand_filter:
        parts.append(f"k={quote(brand_filter)}")
    query = "&".join(parts) if parts else f"k={quote(category_name)}"

    driver.get(f"https://www.{domain}/s?{query}")

    wait = WebDriverWait(driver, 10)

    # 左メニューの部門(Department)絞り込みリンクは href に rh=n%3A<ノードID> を含む
    try:
        wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, 'a[href*="rh=n%3A"]')
            )
        )
    except:
        return None

    links = driver.find_elements(
        By.CSS_SELECTOR,
        'a[href*="rh=n%3A"]'
    )

    for link in links:

        text = link.text.strip()

        if text.lower() == category_name.lower():

            href = link.get_attribute("href") or ""

            match = re.search(r"rh=n%3A(\d+)", href)
            if not match:
                continue

            node_id = match.group(1)

            save_category_node_id(
                marketplace,
                category_name,
                node_id
            )

            return node_id

    return None
