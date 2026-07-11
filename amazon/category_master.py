
# category_master.py
# リサーチ用カテゴリーノードID 取得保存

import os
import re
import html
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

    # ✅ 完全一致以外は自動採用しない。曖昧一致は誤選択の原因になるため、
    # 完全一致しなかった場合は必ずライブ探索→確認ポップアップ（fetch_category_node_id内）を経由する。
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


def _collect_candidates(driver):
    """メニュー内に現在表示されている hmenu-item を (表示名, node_id) のリストとして集める"""
    candidates = []
    for link in driver.find_elements(By.CSS_SELECTOR, 'a.hmenu-item[href*="node="]'):
        text = link.text.strip()
        href = link.get_attribute("href") or ""
        match = re.search(r"node=(\d+)", href)
        if text and match:
            candidates.append((text, match.group(1)))
    return candidates


def _prompt_user_to_pick_category(driver, category_name, candidates):
    """完全一致が見つからなかった場合、候補一覧をブラウザ画面上に表示してユーザーに選んでもらう。
    選んだ候補の (公式表示名, node_id) を返す。キャンセルされたら (None, None) を返す。"""

    # 表示名が重複している候補はまとめる（同じテキストが複数回集まることがあるため）
    unique = {}
    for text, node_id in candidates:
        if text not in unique:
            unique[text] = node_id

    if not unique:
        return None, None

    options_html = "".join(
        '<button class="rt_cat_btn" data-node-id="%s" '
        'style="display:block;width:100%%;text-align:left;margin:4px 0;padding:10px;'
        'font-size:15px;background:#fff;border:1px solid #ccc;border-radius:4px;cursor:pointer;">%s</button>'
        % (html.escape(node_id), html.escape(text))
        for text, node_id in unique.items()
    )

    safe_category_name = html.escape(category_name)

    banner_script = """
    var overlay = document.createElement('div');
    overlay.id = 'rt_category_picker';
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100%%';
    overlay.style.height = '100%%';
    overlay.style.background = 'rgba(0,0,0,0.6)';
    overlay.style.zIndex = '999999';
    overlay.style.display = 'flex';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';

    var box = document.createElement('div');
    box.style.background = '#fff';
    box.style.padding = '20px';
    box.style.width = '480px';
    box.style.maxWidth = '90%%';
    box.style.maxHeight = '80%%';
    box.style.overflowY = 'auto';
    box.style.borderRadius = '8px';
    box.innerHTML = '<h3>「%s」に完全一致するカテゴリーが見つかりませんでした。<br>近いものを選んでください：</h3>%s' +
        '<button id="rt_cat_cancel" style="display:block;width:100%%;margin-top:12px;padding:10px;background:#eee;border:1px solid #ccc;border-radius:4px;cursor:pointer;">キャンセル（カテゴリー絞り込みなしで続行）</button>';

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    window.__rt_category_node_id = null;
    window.__rt_category_cancelled = false;

    var btns = box.querySelectorAll('.rt_cat_btn');
    for (var i = 0; i < btns.length; i++) {
        btns[i].onclick = function() {
            window.__rt_category_node_id = this.getAttribute('data-node-id');
        };
    }
    document.getElementById('rt_cat_cancel').onclick = function() {
        window.__rt_category_cancelled = true;
    };
    """ % (safe_category_name, options_html)

    driver.execute_script(banner_script)

    if get_debug_mode():
        print(f"▶ [category] 候補{len(unique)}件を画面に表示。ユーザーの選択を待機中: {list(unique.keys())!r}")

    while True:
        node_id = driver.execute_script("return window.__rt_category_node_id;")
        cancelled = driver.execute_script("return window.__rt_category_cancelled;")
        if node_id or cancelled:
            break
        time.sleep(0.5)

    driver.execute_script("""
        var o = document.getElementById('rt_category_picker');
        if (o) o.remove();
    """)

    if not node_id:
        return None, None

    # 選ばれた node_id から公式表示名を逆引きする
    chosen_text = next((text for text, nid in unique.items() if nid == node_id), category_name)
    return chosen_text, node_id


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
    all_candidates = []

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

            # 完全一致しなくても、このサブメニューで表示された候補は後で提案用に集めておく
            all_candidates.extend(_collect_candidates(driver))

            if node_id:
                break

    picked_by_user = False
    save_name = category_name

    if not node_id and all_candidates:
        if get_debug_mode():
            print("▶ [category] 完全一致する部門なし。候補をユーザーに提示します")
        chosen_text, node_id = _prompt_user_to_pick_category(driver, category_name, all_candidates)
        picked_by_user = node_id is not None
        if picked_by_user:
            # ✅ 検索に使った生の入力文字列ではなく、選ばれた公式表示名をキーとして保存する
            save_name = chosen_text

    if get_debug_mode() and not node_id:
        print("▶ [category] 一致する部門リンクなし → 保存されません")
        _save_debug_screenshot(driver, marketplace)

    if not node_id:
        return None

    save_category_node_id(
        marketplace,
        save_name,
        node_id
    )

    if get_debug_mode():
        tag = "ユーザー選択・保存完了" if picked_by_user else "一致・保存完了"
        print(f"▶ [category] {tag}: {save_name!r} → node_id={node_id}")

    return node_id
