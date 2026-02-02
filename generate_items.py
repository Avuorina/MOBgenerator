#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Item Generator for Minecraft RPG Datapack

【使い方】
1. SPREADSHEET_ID / SHEET_GID を設定
2. `python generate_items.py` を実行
"""

import csv
import urllib.request
from pathlib import Path
import re
import json

# ==========================================
# 設定エリア
# ==========================================
SPREADSHEET_ID = "1Muf5Hy6Zq1i8Rty1M26-5u13lalUBsuC-pVXNFXMoYM"
SHEET_GID = "1812502896"

CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}"

SCRIPT_DIR = Path(__file__).parent
DATAPACK_DIR = SCRIPT_DIR.parent / "minecraft_rpg"
BANK_DIR = DATAPACK_DIR / "data" / "bank" / "function" / "item"

# カラム定義 (0-indexed)
IDX_MODEL_DATA = 0
IDX_NAME_JP = 1
IDX_NAME_US = 2
IDX_LORE = 3
IDX_BASE_ITEM = 4
IDX_VANILLA_ATK = 5
IDX_RANGE = 6
IDX_SPEED = 7
IDX_BONUS_ATK = 8
IDX_BONUS_HP = 9
IDX_BONUS_MP = 10
IDX_BONUS_STR = 11
IDX_BONUS_DEF = 12
IDX_BONUS_INT = 13
IDX_BONUS_AGI = 14
IDX_BONUS_LUCK = 15

def fetch_spreadsheet_data():
    print(f"[-] スプレッドシートからデータを取得中...")
    try:
        with urllib.request.urlopen(CSV_URL) as response:
            data = response.read().decode('utf-8')
            return data
    except Exception as e:
        print(f"[!] エラー: {e}")
        return None

def snake_case(text):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()

def safe_float(val, default=0.0):
    if not val: return default
    try:
        return float(val.strip())
    except:
        return default

def safe_int(val, default=0):
    if not val: return default
    try:
        return int(val.strip())
    except:
        return default

def generate_item_file(row, index):
    """行データからアイテムファイルを生成"""
    
    def get_col(idx):
        if idx < len(row): return row[idx]
        return ""

    name_jp = get_col(IDX_NAME_JP).strip()
    if not name_jp: return None
    
    name_us = get_col(IDX_NAME_US).strip() or f"item_{index}"
    simple_id = snake_case(name_us)
    unique_id = f"{index:03d}.{simple_id}"
    
    base_item = get_col(IDX_BASE_ITEM).strip() or 'minecraft:stone'
    if not base_item.startswith('minecraft:'): base_item = f"minecraft:{base_item}"
        
    custom_model_data = safe_int(get_col(IDX_MODEL_DATA))
    
    vanilla_atk = safe_float(get_col(IDX_VANILLA_ATK))
    atk_speed = safe_float(get_col(IDX_SPEED))
    atk_range = safe_float(get_col(IDX_RANGE))
    
    bonus_atk = safe_float(get_col(IDX_BONUS_ATK))
    bonus_hp = safe_float(get_col(IDX_BONUS_HP))
    bonus_mp = safe_float(get_col(IDX_BONUS_MP))
    bonus_str = safe_float(get_col(IDX_BONUS_STR))
    bonus_def = safe_float(get_col(IDX_BONUS_DEF))
    bonus_int = safe_float(get_col(IDX_BONUS_INT))
    bonus_agi = safe_float(get_col(IDX_BONUS_AGI))
    bonus_luck = safe_float(get_col(IDX_BONUS_LUCK))

    lore_raw = get_col(IDX_LORE).strip()
    lore_list = []
    if lore_raw:
        lines = lore_raw.split('\n')
        lore_list = [f'{{"text":"{line}","color":"gray"}}' for line in lines if line]
    lore_nbt = f"[{','.join(lore_list)}]"
    
    file_path = BANK_DIR / unique_id / "register.mcfunction"
    bank_path = f"bank:item/{unique_id}/register"
    
    # 修正: data modify storage <ID> <PATH> ...
    content = f"""# {name_jp}
# ID: {unique_id}
# {bank_path}

# ストレージ初期化
data remove storage rpg_item:tmp

# 基本データ
data modify storage rpg_item:tmp id set value "{base_item}"
data modify storage rpg_item:tmp components set value {{}}
data modify storage rpg_item:tmp count set value 1

# 表示名 & Lore
data modify storage rpg_item:tmp components."minecraft:custom_name" set value '{{"text":"{name_jp}","italic":false}}'
data modify storage rpg_item:tmp components."minecraft:lore" set value {lore_nbt}

# CustomModelData
data modify storage rpg_item:tmp components."minecraft:custom_model_data" set value {{floats:[{custom_model_data}]}}

# 識別用タグ
data modify storage rpg_item:tmp components."minecraft:custom_data".RPGItem.ID set value "{unique_id}"

# --- ステータス設定 (RPG計算用) ---
data modify storage rpg_item:tmp stats.ATK set value {bonus_atk}
data modify storage rpg_item:tmp stats.HP set value {bonus_hp}
data modify storage rpg_item:tmp stats.MP set value {bonus_mp}
data modify storage rpg_item:tmp stats.STR set value {bonus_str}
data modify storage rpg_item:tmp stats.DEF set value {bonus_def}
data modify storage rpg_item:tmp stats.INT set value {bonus_int}
data modify storage rpg_item:tmp stats.AGI set value {bonus_agi}
data modify storage rpg_item:tmp stats.LUCK set value {bonus_luck}

# その他 (Vanilla属性など)
data modify storage rpg_item:tmp stats.VanillaATK set value {vanilla_atk}
data modify storage rpg_item:tmp stats.Range set value {atk_range}
data modify storage rpg_item:tmp stats.Speed set value {atk_speed}

# 保存: rpg_item:bank の中に保存
data modify storage rpg_item:bank {unique_id} set from storage rpg_item:tmp

# [Give Command Example]
# give @s {base_item}[custom_name='{{"text":"{name_jp}","italic":false}}',custom_model_data={{floats:[{custom_model_data}]}},custom_data={{RPGItem:{{ID:"{unique_id}"}}}}]
"""
    return {'path': file_path, 'content': content, 'name': name_jp}

def write_files(files):
    if not files: return
    print(f"\n[-] {len(files)} 個のファイルを生成中...")
    for f in files:
        f['path'].parent.mkdir(parents=True, exist_ok=True)
        with open(f['path'], 'w', encoding='utf-8') as file:
            file.write(f['content'])
    print(f"\n[OK] 完了！ output: {BANK_DIR}")

def main():
    print("Minecraft RPG - Item Generator (v2)")
    csv_data = fetch_spreadsheet_data()
    if not csv_data: return
    rows = list(csv.reader(csv_data.splitlines()))
    data_rows = rows[2:]
    files = []
    for idx, row in enumerate(data_rows, 1):
        if not row: continue
        f_obj = generate_item_file(row, idx)
        if f_obj:
            files.append(f_obj)
            print(f"   [OK] {f_obj['name']}")
    write_files(files)

if __name__ == "__main__":
    main()
