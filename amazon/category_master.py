
# category_master.py
# リサーチ用カテゴリーノードID 取得保存

import os
import re
import time
import sqlite3
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.config_loader import get_debug_mode

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
DB_PATH = os.path.join(DB_DIR, "category_master.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_category_node_id(driver, marketplace, category_name):

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
        category_name
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

def _find_matching_node_id(driver, category_name):
    """メニュー内に現在表示されている hmenu-item から、名前が一致するものを探す"""
    links = driver.find_elements(By.CSS_SELECTOR, 'a.hmenu-item[href*="node="]')
    for link in links:
        text = link.text.strip()
        if text.lower() == category_name.lower():
            href = link.get_attribute("href") or ""
            match = re.search(r"node=(\d+)", href)
            if match:
                return match.group(1)
    return None


def _save_debug_screenshot(driver, marketplace):
    try:
        debug_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log")
        os.makedirs(debug_dir, exist_ok=True)

        shot_path = os.path.join(debug_dir, f"category_debug_{marketplace}.png")
        driver.save_screenshot(shot_path)
        print(f"▶ [category] スクリーンショット保存: {shot_path}")

        html_path = os.path.join(debug_dir, f"category_debug_{marketplace}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"▶ [category] ページHTML保存: {html_path}")
    except Exception as e:
        print(f"▶ [category] デバッグ情報保存失敗: {e}")


def fetch_category_node_id(driver, marketplace, category_name):

    domain = {
        "ca": "amazon.ca",
        "us": "amazon.com",
        "au": "amazon.com.au",
        "jp": "amazon.co.jp"
    }[marketplace.lower()]

    # ✅ 検索結果ページの絞り込み欄は表示されたりされなかったりして当てにできないため、
    # ハンバーガーメニュー（すべてのカテゴリー）を実際に開いて部門名とノードIDを取得する。
    # トップレベル項目は href が空で、ホバーして初めて本物の node=ID リンクが読み込まれる。
    if get_debug_mode():
        print(f"▶ [category] 探している部門名: {category_name!r}")

    driver.get(f"https://www.{domain}/")

    wait = WebDriverWait(driver, 15)

    try:
        hamburger = wait.until(
            EC.element_to_be_clickable((By.ID, "nav-hamburger-menu"))
        )
        hamburger.click()
    except Exception as e:
        if get_debug_mode():
            print(f"▶ [category] ハンバーガーメニューを開けませんでした: {e}")
            print(f"▶ [category] ページタイトル: {driver.title!r}")
            _save_debug_screenshot(driver, marketplace)
        return None

    try:
        wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "a.hmenu-item[data-menu-id]")
            )
        )
    except Exception:
        if get_debug_mode():
            print("▶ [category] メニュー項目が見つかりませんでした（タイムアウト）")
            _save_debug_screenshot(driver, marketplace)
        return None

    # トップレベル自体がすでに一致するか（node付きで表示されている場合）先に確認
    node_id = _find_matching_node_id(driver, category_name)

    if not node_id:
        top_items = driver.find_elements(By.CSS_SELECTOR, "a.hmenu-item[data-menu-id]")
        top_count = len(top_items)

        if get_debug_mode():
            print(f"▶ [category] トップレベル項目数: {top_count}")

        for i in range(top_count):
            # ホバーでサブメニューが再描画されDOMが変わるため、毎回取得し直す
            top_items = driver.find_elements(By.CSS_SELECTOR, "a.hmenu-item[data-menu-id]")
            if i >= len(top_items):
                break
            try:
                ActionChains(driver).move_to_element(top_items[i]).perform()
            except Exception:
                continue

            # サブメニューのAJAX読み込みを待ちながら数回チェックする（固定sleepだと間に合わないことがある）
            for _ in range(8):
                node_id = _find_matching_node_id(driver, category_name)
                if node_id:
                    break
                time.sleep(0.25)

            if node_id:
                break

    if get_debug_mode() and not node_id:
        print("▶ [category] 一致する部門リンクなし → 保存されません")
        _save_debug_screenshot(driver, marketplace)

    if not node_id:
        return None

    save_category_node_id(
        marketplace,
        category_name,
        node_id
    )

    if get_debug_mode():
        print(f"▶ [category] 一致・保存完了: node_id={node_id}")

    return node_id
