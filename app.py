import sys
import os
import secrets
from amazon.routes import amazon_bp
from flask import Flask, render_template, jsonify, request 
import json
import codecs
from utils.config_loader import cfg, get_debug_mode
import amazon.db_migrate as db_migrate  

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json") 

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

base_dir = os.path.abspath(os.path.dirname(__file__))

sys.path.append(os.path.dirname(__file__))  

app.secret_key = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Blueprint 登録
app.register_blueprint(amazon_bp, url_prefix="/amazon")


@app.route("/")
def index():
    return render_template("index.html",
                           last_used={},   
                           cfg={})   

if __name__ == "__main__":
    db_migrate.main()
    app.run(host="0.0.0.0", port=5002, debug=False)