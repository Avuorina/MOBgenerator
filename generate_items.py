#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Item Generator for Minecraft RPG Datapack (Loot Table Edition)

【特徴】
- カラーコード対応
- 各種 Loot Function (set_components, set_name, set_lore, set_attributes) を使用
- WeaponType / 自動ステータス計算
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
DATAPACK_DIR = SCRIPT_DIR.parent / "MinecraftLikeRPG"
ITEM_LOOT_DIR = DATAPACK_DIR / "data" / "bank" / "loot_table" / "item"

IDX_CMD = 0
IDX_NAME_JP = 1
IDX_NAME_US = 2
IDX_LORE = 3
IDX_BASE = 4
IDX_TYPE = 5
IDX_ATK_DMG = 6
IDX_ATK_SPD = 7

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
    if not text: return ""
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

def parse_color_codes(text, default_color="white", default_italic=False):
    if not text:
        return [{"text": "", "color": default_color, "italic": default_italic}]

    colors = {
        '0': 'black', '1': 'dark_blue', '2': 'dark_green', '3': 'dark_aqua',
        '4': 'dark_red', '5': 'dark_purple', '6': 'gold', '7': 'gray',
        '8': 'dark_gray', '9': 'blue', 'a': 'green', 'b': 'aqua',
        'c': 'red', 'd': 'light_purple', 'e': 'yellow', 'f': 'white'
    }
    formats = {
        'k': 'obfuscated', 'l': 'bold', 'm': 'strikethrough',
        'n': 'underlined', 'o': 'italic', 'r': 'reset'
    }

    components = []
    current_style = {
        'color': default_color,
        'bold': False, 'italic': default_italic, 'underlined': False,
        'strikethrough': False, 'obfuscated': False
    }
    
    buffer = ""
    i = 0
    while i < len(text):
        char = text[i]
        
        if char == '&' and i + 1 < len(text):
            code = text[i+1].lower()
            if code in colors or code in formats:
                if buffer:
                    comp = {'text': buffer}
                    comp.update(current_style)
                    components.append(comp)
                    buffer = ""
                
                if code in colors:
                    current_style = {
                        'color': colors[code],
                        'bold': False, 'italic': False, 'underlined': False,
                        'strikethrough': False, 'obfuscated': False
                    }
                elif code in formats:
                    if code == 'r':
                        current_style = {
                            'color': default_color,
                            'bold': False, 'italic': default_italic, 'underlined': False,
                            'strikethrough': False, 'obfuscated': False
                        }
                    else:
                        current_style[formats[code]] = True
                i += 2
                continue
        buffer += char
        i += 1
    
    if buffer:
        comp = {'text': buffer}
        comp.update(current_style)
        components.append(comp)
    
    if not components:
        components.append({"text": "", "color": default_color, "italic": default_italic})
        
    return components

def generate_loot_table_file(row, index):
    def get_col(idx):
        if idx < len(row): return row[idx]
        return ""

    name_jp = get_col(IDX_NAME_JP).strip()
    if not name_jp: return None
    
    name_us = get_col(IDX_NAME_US).strip() or f"item_{index}"
    
    cmd_raw = get_col(IDX_CMD).strip()
    if cmd_raw:
        try:
            cmd = int(cmd_raw)
            idx_str = f"{cmd:03d}"
        except:
            cmd = index
            idx_str = f"{index:03d}"
    else:
        cmd = index
        idx_str = f"{index:03d}"

    simple_id = snake_case(name_us)
    unique_id = f"{idx_str}.{simple_id}"
    
    # Attributes - REMOVED for Custom System
    # modifiers are no longer used in set_attributes

    # Bonus Stats & Weapon Stats for BankItem
    custom_stats = {}
    
    # Weapon Stats
    weapon_type = get_col(IDX_TYPE).strip().lower()
    is_weapon = weapon_type != "none" and weapon_type != ""
    
    atk_val = safe_float(get_col(IDX_ATK_DMG))
    spd_val = safe_float(get_col(IDX_ATK_SPD))
    
    # Bonus Stats Map
    bonus_map = {
        'HP': IDX_BONUS_HP, 'MP': IDX_BONUS_MP,
        'STR': IDX_BONUS_STR, 'DEF': IDX_BONUS_DEF, 'INT': IDX_BONUS_INT,
        'AGI': IDX_BONUS_AGI, 'LUCK': IDX_BONUS_LUCK
    }
    for key, idx in bonus_map.items():
        val = safe_float(get_col(idx))
        if val != 0:
            custom_stats[key] = val

    # Loot Table Structure
    # Lore Parsing
    lore_raw = get_col(IDX_LORE).strip()
    lore_list = []
    if lore_raw:
        lines = lore_raw.split('\n')
        for line in lines:
            if line:
                parsed = parse_color_codes(line, default_color="gray", default_italic=False)
                # 1.20.5+ set_lore needs a list of components, usually ["", {...}, {...}] works best
                lore_list.append([""] + parsed)

    # Name Parsing
    name_parsed = parse_color_codes(name_jp, default_color="white", default_italic=False)
    name_json = [""] + name_parsed

    function_list = []
    
    # 1. Set Components (Custom Data)
    # BankItem is now a List of Objects
    bank_item_obj = {
        "ID": unique_id,
        "ATK": atk_val,
        "ATKSpeed": spd_val
    }
    # Add bonus stats to the same object or separate?
    # User example only showed ID, ATK, ATKSpeed.
    # We will merge custom_stats into it for now to keep data.
    bank_item_obj.update(custom_stats)

    function_list.append({
        "function": "minecraft:set_components",
        "components": {
            "minecraft:custom_data": {
                "BankItem": [ bank_item_obj ]
            }
        }
    })
    
    # 2. Set Name
    function_list.append({
        "function": "minecraft:set_name",
        "entity": "this",
        "name": name_json[1] if len(name_json) > 1 else {"text": name_jp, "color": "white"} 
        # User example used simple object, parse_color_codes returns list. 
        # We try to use the first parsed component if available, or simple dict.
    })
    
    # 3. Set Lore
    if lore_list:
        # Simplify Lore to list of strings if possible, or keep component list
        # User example: ["text"]
        # Script produces: [["", {"text":...}]]
        # We will keep script behavior but ensure it works. 
        # Actually user example used raw string ["これは..."]
        # We will convert parsed components to simple strings if they are just text for simplicity, 
        # or just use the parsing result. 
        function_list.append({
            "function": "minecraft:set_lore",
            "entity": "this",
            "lore": lore_list,
            "mode": "append"
        })
        
    # 4. Set Custom Model Data
    function_list.append({
        "function": "minecraft:set_custom_model_data",
        "floats": {
            "values": [ int(cmd) ], # Use INT
            "mode": "replace_all"
        }
    })
    
    # 5. Set Attributes - REMOVED

    loot_table = {
        "pools": [
            {
                "rolls": 1,
                "entries": [
                    {
                        "type": "minecraft:item",
                        "name": "minecraft:carrot_on_a_stick", # Fixed Base Item
                        "functions": function_list
                    }
                ]
            }
        ]
    }

    content = json.dumps(loot_table, indent=2, ensure_ascii=False)
    file_path = ITEM_LOOT_DIR / f"{unique_id}.json"
    
    return {'path': file_path, 'content': content, 'name': name_jp}

def write_files(files):
    if not files: return
    print(f"\n[-] {len(files)} 個のファイルを生成中...")
    for f in files:
        f['path'].parent.mkdir(parents=True, exist_ok=True)
        with open(f['path'], 'w', encoding='utf-8') as file:
            file.write(f['content'])
    print(f"\n[OK] 完了！ output: {ITEM_LOOT_DIR}")

def main():
    print("Minecraft RPG - Item Generator (v8 Functions)")
    csv_data = fetch_spreadsheet_data()
    if not csv_data: return
    
    reader = csv.reader(csv_data.splitlines())
    rows = list(reader)
    
    if len(rows) < 3:
        print("エラー: 3行以上必要です")
        return
        
    print(f"[-] {len(rows)} 行読み込み")
    
    files = []
    for idx, row in enumerate(rows[2:], 1):
        if len(row) > 1 and row[1]:
            f_obj = generate_loot_table_file(row, idx)
            if f_obj:
                files.append(f_obj)
                print(f"   [OK] {f_obj['name']}")
            
    write_files(files)

if __name__ == "__main__":
    main()
