# ファイル名：amazon/constants.py

import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GPT_KEY_PATH = os.path.join(BASE_DIR, "gpt_key", "gpt_key.txt")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
