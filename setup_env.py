# setup_env.py
# 初回セットアップ用：venv（仮想環境）を作成し、必要なライブラリをインストールする

import os
import sys
import subprocess

# このファイルがある場所（プロジェクトのルート）を基準にする
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "venv")
REQUIREMENTS_PATH = os.path.join(BASE_DIR, "requirements.txt")
PYTHON_EMBED_DIR = os.path.join(BASE_DIR, "python_embed")

def main():
    # Windows：同梱の専用Pythonがある場合は、それをそのまま使う（venv不要）
    if os.path.exists(PYTHON_EMBED_DIR):
        print("同梱の専用Pythonを使ってライブラリをインストールしています...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_PATH],
            check=True
        )
        print("セットアップが完了しました。")
        return

    # Mac等：同梱Pythonが無い場合は、従来通りvenvを作成する
    if not os.path.exists(VENV_DIR):
        print("仮想環境(venv)を作成しています...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
    else:
        print("venvフォルダは既に存在します。作成をスキップします。")

    if sys.platform == "win32":
        venv_python = os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(VENV_DIR, "bin", "python")

    print("必要なライブラリをインストールしています...")
    subprocess.run(
        [venv_python, "-m", "pip", "install", "-r", REQUIREMENTS_PATH],
        check=True
    )
    print("セットアップが完了しました。")


if __name__ == "__main__":
    main()