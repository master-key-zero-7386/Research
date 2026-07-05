# start_app.py
# 起動用：venv内のPythonでapp.pyを実行し、自動でブラウザを開く

import os
import sys
import subprocess
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "venv")
APP_PATH = os.path.join(BASE_DIR, "app.py")

URL = "http://127.0.0.1:5002/amazon/"

PYTHON_EMBED_DIR = os.path.join(BASE_DIR, "python_embed")

def main():
    if os.path.exists(PYTHON_EMBED_DIR):
        # Windows：同梱の専用Pythonをそのまま使う
        python_exe = sys.executable
    else:
        # Mac等：venv内のPythonを使う
        if sys.platform == "win32":
            python_exe = os.path.join(VENV_DIR, "Scripts", "python.exe")
        else:
            python_exe = os.path.join(VENV_DIR, "bin", "python")

        if not os.path.exists(python_exe):
            print("エラー: venvが見つかりません。先にセットアップ（setup）を実行してください。")
            sys.exit(1)

    process = subprocess.Popen([python_exe, APP_PATH], cwd=BASE_DIR)
    time.sleep(2)
    webbrowser.open(URL)
    process.wait()


if __name__ == "__main__":
    main()