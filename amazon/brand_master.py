
# brand_master.py
# リサーチ用ブランドID 取得保存

import os
import re
import html
import time
import sqlite3
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote
from utils.config_loader import get_debug_mode

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

    # ✅ 完全一致以外は自動採用しない。曖昧一致は誤登録・誤選択の原因になるため、
    # 完全一致しなかった場合は必ずライブ検索→確認ポップアップ（fetch_brand_id内）を経由する。
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

def _save_debug_screenshot(driver, marketplace):
    try:
        debug_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "log")
        os.makedirs(debug_dir, exist_ok=True)

        shot_path = os.path.join(debug_dir, f"brand_debug_{marketplace}.png")
        driver.save_screenshot(shot_path)
        print(f"▶ [brand] スクリーンショット保存: {shot_path}")

        html_path = os.path.join(debug_dir, f"brand_debug_{marketplace}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"▶ [brand] ページHTML保存: {html_path}")
    except Exception as e:
        print(f"▶ [brand] デバッグ情報保存失敗: {e}")


def _brand_match_score(name, brand_name):
    """候補の並び替え用スコア（小さいほど有力）。自動保存には使わず、順番の目安としてのみ使う。"""
    name_lower = name.lower()
    brand_name_lower = brand_name.lower()
    # "シマノ(SHIMANO)" のように括弧書き（英語表記等）が付いた表示名を除いた形でも比較する
    name_no_paren = re.sub(r"[\(（].*?[\)）]\s*$", "", name).strip().lower()

    if name_lower == brand_name_lower or name_no_paren == brand_name_lower:
        return 0
    if name_lower.startswith(brand_name_lower):
        return 1
    if brand_name_lower in name_lower:
        return 2
    return 3


def _collect_brand_candidates(brands):
    """絞り込み欄に表示されている全ブランドを (表示名, brand_id) のリストとして集める"""
    candidates = []
    for brand in brands:
        text = brand.text.strip()
        name = text.split("\n")[0].strip()
        parts = (brand.get_attribute("id") or "").split("/")
        if name and len(parts) > 1:
            candidates.append((name, parts[1]))
    return candidates


def _prompt_user_to_pick_brand(driver, brand_name, candidates):
    """一致するブランドが見つからなかった場合、候補一覧をブラウザ画面上に表示してユーザーに選んでもらう。
    選んだ候補の (公式表示名, brand_id) を返す。キャンセルされたら (None, None) を返す。"""

    unique = {}
    for name, brand_id in candidates:
        if name not in unique:
            unique[name] = brand_id

    if not unique:
        return None, None

    options_html = "".join(
        '<button class="rt_brand_btn" data-brand-id="%s" '
        'style="display:block;width:100%%;text-align:left;margin:4px 0;padding:10px;'
        'font-size:15px;background:#fff;border:1px solid #ccc;border-radius:4px;cursor:pointer;">%s</button>'
        % (html.escape(brand_id), html.escape(name))
        for name, brand_id in unique.items()
    )

    safe_brand_name = html.escape(brand_name)

    banner_script = """
    var overlay = document.createElement('div');
    overlay.id = 'rt_brand_picker';
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
    box.innerHTML = '<h3>「%s」のブランド候補が見つかりました。<br>該当するものを選んでください（一番上が最有力候補です）：</h3>%s' +
        '<button id="rt_brand_cancel" style="display:block;width:100%%;margin-top:12px;padding:10px;background:#eee;border:1px solid #ccc;border-radius:4px;cursor:pointer;">キャンセル（ブランド絞り込みなしで続行）</button>';

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    window.__rt_brand_id = null;
    window.__rt_brand_cancelled = false;

    var btns = box.querySelectorAll('.rt_brand_btn');
    for (var i = 0; i < btns.length; i++) {
        btns[i].onclick = function() {
            window.__rt_brand_id = this.getAttribute('data-brand-id');
        };
    }
    document.getElementById('rt_brand_cancel').onclick = function() {
        window.__rt_brand_cancelled = true;
    };
    """ % (safe_brand_name, options_html)

    driver.execute_script(banner_script)

    if get_debug_mode():
        print(f"▶ [brand] 候補{len(unique)}件を画面に表示。ユーザーの選択を待機中: {list(unique.keys())!r}")

    while True:
        brand_id = driver.execute_script("return window.__rt_brand_id;")
        cancelled = driver.execute_script("return window.__rt_brand_cancelled;")
        if brand_id or cancelled:
            break
        time.sleep(0.5)

    driver.execute_script("""
        var o = document.getElementById('rt_brand_picker');
        if (o) o.remove();
    """)

    if not brand_id:
        return None, None

    # 選ばれた brand_id から公式表示名を逆引きする
    chosen_name = next((name for name, bid in unique.items() if bid == brand_id), brand_name)
    return chosen_name, brand_id


def fetch_brand_id(driver, marketplace, brand_name):

    domain = {
        "ca": "amazon.ca",
        "us": "amazon.com",
        "au": "amazon.com.au",
        "jp": "amazon.co.jp"
    }[marketplace.lower()]

    if get_debug_mode():
        print(f"▶ [brand] 検索URL: https://www.{domain}/s?k={quote(brand_name)}")
        print(f"▶ [brand] 探しているブランド名: {brand_name!r}")

    driver.get(f"https://www.{domain}/s?k={quote(brand_name)}")

    wait = WebDriverWait(driver, 10)

    try:
        wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, 'li[id^="p_123/"]')
            )
        )
    except:
        if get_debug_mode():
            print("▶ [brand] ブランド絞り込み欄が見つかりませんでした（タイムアウト）")
            print(f"▶ [brand] ページタイトル: {driver.title!r}")
            _save_debug_screenshot(driver, marketplace)
        return None

    brands = driver.find_elements(
        By.CSS_SELECTOR,
        'li[id^="p_123/"]'
    )

    if get_debug_mode():
        print(f"▶ [brand] 見つかったブランド一覧: {[b.text.strip().split(chr(10))[0] for b in brands]!r}")

    # ✅ 曖昧一致で自動保存すると誤登録の原因になるため、自動保存はしない。
    # 候補は「有力そうなもの」を先頭に並べてユーザーに見せ、必ず本人に選ばせてから保存する。
    candidates = _collect_brand_candidates(brands)
    candidates.sort(key=lambda c: _brand_match_score(c[0], brand_name))

    chosen_name, brand_id = _prompt_user_to_pick_brand(driver, brand_name, candidates)

    if brand_id and chosen_name:
        # ✅ 検索に使った生の入力文字列ではなく、選ばれた公式表示名をキーとして保存する
        save_brand_id(
            marketplace,
            chosen_name,
            brand_id
        )
        if get_debug_mode():
            print(f"▶ [brand] ユーザー選択・保存完了: {chosen_name!r} → brand_id={brand_id}")
        return brand_id

    if get_debug_mode():
        print("▶ [brand] ユーザーが選択しなかったため保存されません")

    return None