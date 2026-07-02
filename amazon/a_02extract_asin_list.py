import os
import pandas as pd
from datetime import datetime, timedelta
import os, shutil, tempfile
from utils.config_loader import cfg, get_debug_mode

if get_debug_mode():
    print("✅ 【ASIN抽出（統合）機能】a_02extract_asin_list.py 起動")
    print("[MODULE]", os.path.abspath(__file__))
    # print("[TRASH_DIR_ACTIVE]", TOOL_TRASH_DIR)

TOOL_TRASH_DIR = r"C:\Research_Trash"


def run_asin_extraction(input_files, region, data_dir):
    asin_set = set()

    for file_path in input_files:
        try:
            df = pd.read_csv(file_path, dtype=str)

            # ASIN列の候補を探す
            asin_column = None
            for col in df.columns:
                if col.strip().lower() == "asin":
                    asin_column = col
                    break
                if "asin" in col.strip().lower():
                    asin_column = col
                    break

            if asin_column:
                asin_set.update(df[asin_column].dropna().astype(str).str.strip().tolist())

        except Exception as e:
            if get_debug_mode():
                print(f"❌ 読み込み失敗: {file_path} - {e}")

    # 重複排除されたASINリスト
    asin_list = sorted(asin_set)

    # 最終出力データ構成（ASIN + 空のBrand, Note）
    output_df = pd.DataFrame({
        "ASIN": asin_list,
        "Brand": [""] * len(asin_list),
        "Note": [""] * len(asin_list),
    })

    # 日本時間のタイムスタンプでファイル名生成
    now_jst = datetime.utcnow() + timedelta(hours=9)
    timestamp = now_jst.strftime("%Y%m%d_%H%M")
    filename = f"{region.upper()}_{timestamp}_ASIN_list.csv" 

    # 保存
    output_path = os.path.join(data_dir, region.lower(), filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    output_df.to_csv(output_path, index=False, encoding="utf-8-sig") 

    # 元CSVを専用ごみ箱へ退避（削除の代替）
    for src in input_files:  
        if os.path.exists(src):
            os.remove(src) 


    return filename, output_path


# 専用ごみ箱への移動処理

def _ensure_tool_trash(): 
    os.makedirs(TOOL_TRASH_DIR, exist_ok=True) 

def move_to_tool_trash(src_path: str):  
    """削除せず C:\Research_Tool_Trash へ退避""" 
    if not os.path.exists(src_path):  
        return  
    _ensure_tool_trash() 
    base = os.path.basename(src_path) 
    dst = os.path.join(TOOL_TRASH_DIR, base)  
    name, ext = os.path.splitext(dst)  
    i = 1  
    while os.path.exists(dst):  
        dst = f"{name}({i}){ext}"  
        i += 1  
    try:  
        shutil.move(src_path, dst)  
        if get_debug_mode():
            print(f"[INFO] moved to tool trash: {dst}") 
    except Exception as e:  
        if get_debug_mode():
            print(f"[WARN] tool trash move failed: {e}")  
