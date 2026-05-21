import os
import json

# プロジェクトのルートディレクトリを基準に config.json のパスを決定
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.json")

def load_config():
    """config.json を読み込んで dict を返す"""
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

DEBUG_MODE = bool(cfg.get("debug", False))        
