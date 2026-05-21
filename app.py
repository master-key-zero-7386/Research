import sys
import os
from amazon.routes import amazon_bp
from amazon.routes_blacklist import blacklist_bp
from tools.dhl_routes import dhl_bp
from tools.pdf_routes import pdf_bp
from flask import Flask, render_template, jsonify, request 
import json
import codecs
from utils.config_loader import cfg, get_debug_mode
from amazon.routes import amazon_bp
from amazon.csv_import import csv_import_bp
from amazon.routes_listing import listing_bp
import amazon.db_migrate as db_migrate  

# TEST

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json") 

# ✅ コマンド引数から実行モードを判定（デフォルトは "dev"）
mode = sys.argv[1] if len(sys.argv) > 1 else "dev"

# ✅ configファイルの切り替え
if mode == "server":
    CONFIG_PATH = os.path.join("config", "config_server.json")
else:
    CONFIG_PATH = os.path.join("config", "config.json")

def _load_config(): 
    try: 
        if not os.path.exists(CONFIG_PATH):
            return {} 
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True) 
    with open(CONFIG_PATH, "w", encoding="utf-8") as f: 
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ✅ Flaskアプリ初期化
app = Flask(__name__)
app.debug = True 

base_dir = os.path.abspath(os.path.dirname(__file__))

sys.path.append(os.path.dirname(__file__))  # ← zsss_web を明示的に検索パスに追加

app.secret_key = 'your-secret-key'  
app.config['UPLOAD_FOLDER'] = 'uploads'

# Blueprint 登録
app.register_blueprint(amazon_bp, url_prefix="/amazon")
app.register_blueprint(blacklist_bp, url_prefix="/blacklist")
app.register_blueprint(dhl_bp, url_prefix="/tools/dhl") 
app.register_blueprint(pdf_bp, url_prefix="/tools/pdf") 
app.register_blueprint(csv_import_bp, url_prefix="/amazon")
app.register_blueprint(listing_bp, url_prefix="/amazon")

@app.route("/")
def index():
    # config 読み込みとか既存処理で使ってるやつを流用
    return render_template("index.html",
                           last_used={},   # 必要ならちゃんとcfgから読み込む
                           cfg={})   

if __name__ == "__main__":
    db_migrate.main()
    app.run(host="0.0.0.0", port=5002, debug=True)

