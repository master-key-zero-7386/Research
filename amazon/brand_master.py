
# brand_master.py
# リサーチ用ブランドID 取得保存

import os
import sqlite3
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
DB_PATH = os.path.join(DB_DIR, "brand_master.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_brand_id(driver, marketplace, brand_name):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT brand_id
        FROM brand_master
        WHERE marketplace = ?
          AND LOWER(brand_name)=LOWER(?)
        LIMIT 1
    """,(marketplace,brand_name))

    row=cur.fetchone()

    conn.close()

    if row:
        return row["brand_id"]

    return fetch_brand_id(
        driver,
        marketplace,
        brand_name
    )


def save_brand_id(marketplace, brand_name, brand_id):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO brand_master
        (
            marketplace,
            brand_name,
            brand_id
        )
        VALUES (?, ?, ?)

        ON CONFLICT(marketplace, brand_name)

        DO UPDATE SET
            brand_id = excluded.brand_id,
            updated_at = CURRENT_TIMESTAMP
    """, (marketplace, brand_name, brand_id))

    conn.commit()
    conn.close()

def fetch_brand_id(driver, marketplace, brand_name):

    domain = {
        "ca": "amazon.ca",
        "us": "amazon.com",
        "au": "amazon.com.au"
    }[marketplace.lower()]

    driver.get(f"https://www.{domain}/s?k={quote(brand_name)}")

    wait = WebDriverWait(driver, 10)

    try:
        wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, 'li[id^="p_123/"]')
            )
        )
    except:
        return None

    brands = driver.find_elements(
        By.CSS_SELECTOR,
        'li[id^="p_123/"]'
    )

    for brand in brands:

        text = brand.text.strip()

        name = text.split("\n")[0].strip()

        if name.lower() == brand_name.lower():

            brand_id = brand.get_attribute("id").split("/")[1]

            save_brand_id(
                marketplace,
                brand_name,
                brand_id
            )

            return brand_id

    return None