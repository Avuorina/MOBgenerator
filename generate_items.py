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
IDX_BASE = 3
IDX_LORE = 4
IDX_TYPE = 5
IDX_ATK_DMG = 6
IDX_ATK_SPD = 7

IDX_BONUS_HP = 8
IDX_BONUS_MP = 9
IDX_BONUS_STR = 10
IDX_BONUS_DEF = 11
IDX_BONUS_INT = 12
IDX_BONUS_AGI = 13
IDX_BONUS_LUCK = 14

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
    weapon_type_raw = get_col(IDX_TYPE).strip().lower()
    
    # Mapping for numeric types (if used)
    weapon_type_map = {
        "1": "spear",
        "4": "sword",
        "7": "axe"
    }
    
    weapon_type = weapon_type_map.get(weapon_type_raw, weapon_type_raw)
    
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
        "ATKSpeed": spd_val,
        "WeaponType": weapon_type
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
    final_lore = []
    
    # Custom Description (from Spreadsheet)
    if lore_list:
        final_lore.extend(lore_list)
        final_lore.append([""]) # Spacer
        
    # Stats Display
    # リーチ(攻撃範囲)のマッピング
    reach_map = {
        "sword": 3.0,
        "axe": 2.5,
        "spear": 7.5,
        "bow": 20.0
    }
    reach_val = reach_map.get(weapon_type, 2.0)
    
    # 武器種とリーチの表示 (RPGっぽく)
    if is_weapon:
        weapon_name_map = {
            "sword": "剣",
            "axe": "斧",
            "spear": "槍",
            "bow": "弓"
        }
        w_name = weapon_name_map.get(weapon_type, "不明")
        final_lore.append([
            "",
            {"text": f"◆ 武器種 : ", "color": "gray", "italic": False},
            {"text": w_name, "color": "gold", "italic": False}
        ])
        final_lore.append([
            "",
            {"text": "◆ 攻撃範囲 : ", "color": "gray", "italic": False},
            {"text": f"{reach_val:.1f}", "color": "white", "italic": False}
        ])
        final_lore.append([""]) # Spacer

    # 攻撃力 & 攻撃速度
    if atk_val > 0:
        final_lore.append([
            "",
            {"text": "__U_E005__ 攻撃力 : ", "color": "gray", "italic": False},
            {"text": f"{atk_val:.1f}", "color": "red", "italic": False}
        ])
    
    if spd_val > 0:
        final_lore.append([
            "",
            {"text": "__U_E00B__ 攻撃速度 : ", "color": "gray", "italic": False},
            {"text": f"{spd_val:.1f}", "color": "blue", "italic": False}
        ])
        
    # ボーナスステータス
    stat_display_config = {
        "HP": {"color": "red", "label": "__U_E001__ HP"},
        "MP": {"color": "aqua", "label": "__U_E003__ MP"},
        "STR": {"color": "dark_red", "label": "__U_E007__ STR"},
        "DEF": {"color": "blue", "label": "__U_E006__ DEF"},
        "INT": {"color": "light_purple", "label": "__U_E008__ INT"},
        "AGI": {"color": "green", "label": "__U_E009__ AGI"},
        "LUCK": {"color": "yellow", "label": "__U_E00A__ LUCK"}
    }
    
    for stat_key, stat_val in custom_stats.items():
        if stat_val != 0:
            conf = stat_display_config.get(stat_key, {"color": "white", "label": stat_key})
            sign = "+" if stat_val > 0 else ""
            final_lore.append([
                "",
                {"text": f"{conf['label']} : ", "color": "gray", "italic": False},
                {"text": f"{sign}{stat_val:.1f}", "color": conf["color"], "italic": False}
            ])

    if final_lore:
        function_list.append({
            "function": "minecraft:set_lore",
            "entity": "this",
            "lore": final_lore,
            "mode": "append"
        })
        
    # 4. Custom Model Data の設定
    function_list.append({
        "function": "minecraft:set_custom_model_data",
        "floats": {
            "values": [ int(cmd) ], # INT型を使用
            "mode": "replace_all"
        }
    })
    
    # 5. Attributes 設定 - 削除済み

    # 武器種指定の有無でベースアイテムを切り替え
    if is_weapon:
        base_item_id = "minecraft:carrot_on_a_stick"
    else:
        base_item_raw = get_col(IDX_BASE).strip()
        if not base_item_raw:
            base_item_raw = "stick" # 万が一のフォールバック
        base_item_id = base_item_raw if ":" in base_item_raw else f"minecraft:{base_item_raw}"

    loot_table = {
        "pools": [
            {
                "rolls": 1,
                "entries": [
                    {
                        "type": "minecraft:item",
                        "name": base_item_id,
                        "functions": function_list
                    }
                ]
            }
        ]
    }

    content = json.dumps(loot_table, indent=2, ensure_ascii=False)
    
    # アイコンの手動Unicodeエスケープ処理
    # プレースホルダーをリテラルのエスケープシーケンスに置換
    # __U_XXXX__ -> \uXXXX
    import re
    def replace_unicode_placeholder(match):
        code = match.group(1)
        return f"\\u{code}"
        
    content = re.sub(r"__U_([0-9A-F]{4})__", replace_unicode_placeholder, content)
    
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
