# ファイル名：utils\config_loader
 
import os
import json

# プロジェクトのルートディレクトリを基準に config.json のパスを決定
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.json")

# ✅ config.json が無い環境（配布先での初回起動など）向けのデフォルト値。
#    advanced_mode は必ず False＝簡易UI（詳細リサーチ非表示）で生成する。
DEFAULT_CONFIG = {
    "debug": False,
    "advanced_mode": False,
    "data_dir": "data",
    "lists_dir": "lists",
    "log_dir": "log",
    "last_used": {
        "region": "US",
        "seller_id": "",
        "brand": "",
        "category": "",
        "category_node_id_manual": "",
        "min_price": "",
        "max_price": "",
        "step_price": "10",
        "output_folder": "",
        "confirm_wait": ""
    }
}

def load_config():
    """config.json を読み込んで dict を返す。存在しない場合は配布用デフォルト値で新規作成する。"""
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# 起動時に一度読み込む（通常の設定参照用）
cfg = load_config()

def get_debug_mode() -> bool:
    """最新の config.json を確認して debug フラグを返す"""
    try:
        cfg_now = load_config()
        return bool(cfg_now.get("debug", False))
    except Exception:
        return False

def get_advanced_mode() -> bool:
    """最新の config.json を確認して advanced_mode フラグを返す（キーが無ければFalse＝簡易UI）"""
    try:
        cfg_now = load_config()
        return bool(cfg_now.get("advanced_mode", False))
    except Exception:
        return False

DEBUG_MODE = bool(cfg.get("debug", False))
