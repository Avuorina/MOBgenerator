#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOB Generator for Minecraft RPG Datapack

【このツールは何？】
Google スプレッドシートに書かれた MOB のステータスや見た目のデータを読み込んで、
Minecraft のデータパック（datapack）に必要なファイルを自動で作ってくれるプログラムです。

【使い方】
1. Google スプレッドシートを編集する
2. このフォルダで `python generate_mobs.py` を実行する
3. Minecraft で `/reload` する
   → これだけで新しい MOB がゲームに追加されます！

【仕組み】
1. ネット経由でスプレッドシートのデータをCSV形式でダウンロード
2. データを1行ずつ読み込んで、MOBの設定（名前、HP、装備など）を解析
3. データパックの `data/bank/...` や `data/mob/spawn/...` に `.mcfunction` ファイルを作成
"""

import csv
import urllib.request
from pathlib import Path
import json
import re
import time

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False
    print("Warning: gspread or oauth2client not installed. Skipping spreadsheet update.")

# ==========================================
# 設定エリア
# ==========================================
# 読み込む Google スプレッドシートのID
# (URLの https://docs.google.com/spreadsheets/d/★★★/edit の ★★★ の部分)
SPREADSHEET_ID = "1Muf5Hy6Zq1i8Rty1M26-5u13lalUBsuC-pVXNFXMoYM"
SHEET_GID = "0"  # シートID（通常、最初のシートは "0" です）

# CSVとしてダウンロードするためのURLを作っています
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}"

# ==========================================
# 出力先の設定
# ==========================================
# このファイル（generate_mobs.py）がある場所を基準にします
SCRIPT_DIR = Path(__file__).parent 

# データパックの場所（隣の MinecraftLikeRPG フォルダを探します）
# もしフォルダ名を変えたら、ここも変えてください！
DATAPACK_DIR = SCRIPT_DIR.parent / "MinecraftLikeRPG"

# 各ファイルの出力先フォルダ
# BANK_DIR:  ステータスや装備の設定ファイル置き場（Storage用）
# SPAWN_DIR: コマンドで呼び出すスポーン用ファイル置き場
# SPAWN_MAP_DIR: 内部処理用のファイル置き場
# DEBUG_SUMMON_DIR: デバッグ用召喚コマンド置き場
BANK_DIR = DATAPACK_DIR / "data" / "bank" / "function" / "mob"
SPAWN_DIR = DATAPACK_DIR / "data" / "mob" / "function" / "spawn"
SPAWN_MAP_DIR = DATAPACK_DIR / "data" / "mob" / "function" / "spawn_map"
DEBUG_SUMMON_DIR = DATAPACK_DIR / "data" / "debug" / "function" / "summon"

def fetch_spreadsheet_data():
    """
    【ステップ1】スプレッドシートからデータを取ってくる
    インターネット経由で Google のサーバーにアクセスし、CSVデータをダウンロードします。
    """
    print(f"[-] スプレッドシートからデータを取得中...")
    print(f"   URL: {CSV_URL}")
    
    try:
        with urllib.request.urlopen(CSV_URL) as response:
            data = response.read().decode('utf-8')
            return data
    except Exception as e:
        print(f"[!] エラー: スプレッドシートの取得に失敗しました")
        print(f"   {e}")
        print(f"\n[?] ヒント: スプレッドシートが「リンクを知っている全員が閲覧可能」に設定されているか確認してください")
        return None

def parse_csv_data(csv_data):
    """
    【ステップ2】データを読みやすい形に整理する
    ダウンロードした文字の羅列（CSV）を、プログラムで扱いやすいリスト形式に変換します。
    名前が空欄の行はスキップします。
    """
    reader = csv.DictReader(csv_data.splitlines())
    mobs = []
    
    rows = []
    last_valid_row = None
    
    rows = []
    last_valid_row = None
    
    for row in reader:
        name = row.get('NameJP', '').strip()
        
        # NameJPがある場合
        if name:
            rows.append(row)
            last_valid_row = row
            
        # NameJPがないが、前回のMOBが有効で、かつTURN/Interval情報がある場合は継続行とみなす
        elif last_valid_row and (row.get('TURN') or row.get('Interval') or row.get('SKILL')):
            # ID情報を継承
            row['NameJP'] = last_valid_row['NameJP']
            row['NameUS'] = last_valid_row['NameUS']
            row['ID'] = last_valid_row.get('ID')
            rows.append(row)
            
    return rows

def snake_case(text):
    """
    【お助け機能】名前をファイル名向けに変換する
    例: "SkeletonWarrior" → "skeleton_warrior"
    大文字交じりの名前を、全部小文字のファイル名（スネークケース）に直します。
    """
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()

def parse_equipment(equipment_raw):
    """
    equipment:{...} 文字列を解析して ArmorItems, HandItems のリストを返す
    """
    armor_items = ['{}', '{}', '{}', '{}'] # feet, legs, chest, head
    hand_items = ['{}', '{}'] # main, off
    
    if not equipment_raw:
        return armor_items, hand_items

    # 簡易パース: equipment:{...} があれば中身を取り出す
    eq_str = equipment_raw.replace('""', '"').strip()
    
    # NBTのキー修正 (count -> Count, id -> id)
    # ユーザーが /give コマンドなどの形式(count:1)で書いている場合、NBT(Count:1b)としては認識されないことがある
    # regexで数値の後ろにbがない場合のみ付与する: count:1 -> Count:1b
    # まず count: を Count: に
    eq_str = eq_str.replace('count:', 'Count:')
    
    # Count:1, Count:64 などを Count:1b, Count:64b に置換 (直後にbがない場合)
    eq_str = re.sub(r'Count:(\d+)(?!b)', r'Count:\1b', eq_str)
    
    if eq_str.startswith('equipment:{') and eq_str.endswith('}'):
        eq_str = eq_str[11:-1] # remove equipment:{ and }
    
    # key:{...} を探す
    # slot名と中身のマッピング
    slots = {
        'head': 3, 'chest': 2, 'legs': 1, 'feet': 0,
        'mainhand': 0, 'offhand': 1
    }
    
    for slot, idx in slots.items():
        start_marker = f"{slot}:" + "{"
        start_pos = eq_str.find(start_marker)
        if start_pos != -1:
            # { の位置
            brace_start = start_pos + len(slot) + 1
            brace_count = 1
            end_pos = -1
            
            for i in range(brace_start + 1, len(eq_str)):
                char = eq_str[i]
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            
            if end_pos != -1:
                item_data = eq_str[brace_start:end_pos]
                
                if slot in ['head', 'chest', 'legs', 'feet']:
                    armor_items[idx] = item_data
                elif slot == 'mainhand':
                    hand_items[0] = item_data
                elif slot == 'offhand':
                    hand_items[1] = item_data
                    
    return armor_items, hand_items

def get_nbt_str(mob_data, is_boss, mob_id, tags_str, armor_items, hand_items):
    """召喚用のNBT文字列を生成 (最小限)"""
    
    # NBTパーツ
    nbt_parts = []
    
    # Tagsは引数で渡されたものを使用（すでに生成済み）
    nbt_parts.append(f"Tags:[{tags_str}]")
    
    # CustomName, ArmorItems, HandItems は Storage経由で適用するため削除
    # ただし、CustomNameVisible や PersistenceRequired は維持
            
    nbt_parts.append("CustomNameVisible:true")
    nbt_parts.append("PersistenceRequired:true")
    
    # バニラの自然スポーンと競合しないように、LeftHandedなどの設定も必要ならここに追加
    
    return "{" + ",".join(nbt_parts) + "}"

def generate_spawn_wrapper_file(mob_data, unique_id, bank_path_str):
    """spawn ラッパーファイルを生成"""
    name_jp = mob_data.get('NameJP', 'Unknown')
    
    # 新しい方式: Bank(Storage Load) -> Generic Spawn
    content = f"""# {name_jp}を召喚（ラッパー）
# ID: {unique_id}
# 使用方法: /function mob:spawn/{unique_id}

# 1. データ登録 (Storageにセット)
function {bank_path_str}

# 2. 汎用召喚 (Storageの内容で召喚)
function mob:spawn_from_storage
"""
    path = SPAWN_DIR / f"{unique_id}.mcfunction"
    return {
        'path': path,
        'content': content,
        'name': f"{name_jp} (SpawnWrapper)"
    }


def generate_debug_summon_file(mob_data, unique_id, bank_path_str):
    """デバッグ用召喚ファイルを生成"""
    name_jp = mob_data.get('NameJP', 'Unknown')
    
    content = f"""# {name_jp}をデバッグ召喚
# 使用方法: /function debug:summon/{unique_id}

# 1. データ登録 (Storageにセット)
function {bank_path_str}

# 2. 汎用召喚 (Storageの内容で召喚)
function mob:spawn/from_storage
"""
    path = DEBUG_SUMMON_DIR / f"{unique_id}.mcfunction"
    return {
        'path': path,
        'content': content,
        'name': f"{name_jp} (DebugSummon)"
    }


def parse_triggers(mob_data):
    """
    トリガー列をパースしてスキルIDを抽出
    Returns: dict with trigger types as keys and skill IDs as values
    """
    triggers = {}
    
    # トリガー列のマッピング
    trigger_columns = {
        '初期': 'init',
        '死': 'death',
        'ダメージ': 'on_hurt',
        '攻撃': 'on_attack'
    }
    
    for col_name, trigger_type in trigger_columns.items():
        skill_id = mob_data.get(col_name, '').strip()
        if skill_id:
            triggers[trigger_type] = skill_id
    
    # initトリガーは常に必要（Tick関数生成のため）
    # Initタグの処理を行う .mcfunction (Tick) はここで生成されるため、
    # スキルやターン設定がなくても必ず生成する必要がある。
    if 'init' not in triggers:
        triggers['init'] = ""
            
    return triggers


def generate_skill_files(mob_data, unique_id, area, group, ai, triggers, subfolder_id=None):
    """
    トリガーに応じたスキル実行ファイルを生成
    subfolder_id: サブフォルダID（例: "main", "008.henchman"）
    Returns: list of file dicts to be written
    """
    files = []
    # サブフォルダがある場合はパスに含める
    if subfolder_id:
        base_path = BANK_DIR / area / group / ai / unique_id / subfolder_id
        func_base = f"bank:mob/{area}/{group}/{ai}/{unique_id}/{subfolder_id}"
    else:
        base_path = BANK_DIR / area / group / ai / unique_id
        func_base = f"bank:mob/{area}/{group}/{ai}/{unique_id}"
    name_jp = mob_data.get('NameJP', 'Unknown')

    for trigger_type, skill_json in triggers.items():
        # 標準のファイル生成 (init.mcfunction, death.mcfunction, etc.)
        filename = f"{trigger_type}.mcfunction"
        file_path = base_path / filename
        
        # JSONデータをそのまま使用
        content = f"# {name_jp} - {trigger_type} トリガー\n"
        if skill_json:
            content += f"# Skill: {skill_json}\n\n"
            content += f"# スキルデータをストレージに保存\n"
            content += f"data modify storage rpg_skill: data set value {skill_json}\n\n"
            content += f"# スキル実行\n"
            content += f"function skill:execute\n"
        else:
            content += "# このトリガーに特定のスキルはありません（ターン設定のみ）\n"
        # initの場合、Turn設定を追加（files.appendの前に行う）
        if trigger_type == 'init':
            turn_data_list = mob_data.get('TURN_DATA_LIST', [])
            if turn_data_list:
                first_interval = turn_data_list[0].get('interval') or '60'
                content += f"\n# ターン制システムのセットアップ\nscoreboard players set @s Turn 1\nscoreboard players set @s Interval {first_interval}\n"

        files.append({
            'path': file_path,
            'content': content,
            'name': f"{name_jp} ({trigger_type})"
        })

        # initの場合、Tick実行用ファイル(.mcfunction)も生成済み
        if trigger_type == 'init':
            tick_file_path = base_path / ".mcfunction"
            
            # Turn Dataがあればロジックを追加
            turn_logic = ""
            turn_data_list = mob_data.get('TURN_DATA_LIST', [])
            
            if turn_data_list:
                # 2. Tick Logic (Interval Decrement & Branch)
                turn_logic = f"""
# ターン制システム
scoreboard players remove @s Interval 1
execute if score @s Interval matches ..0 run function {func_base}/turn_distributor
"""
                # 3. Turn Distributor & Individual Turn Files
                dist_content = f"# {name_jp} のターン振り分け\n"
                
                for i, t_data in enumerate(turn_data_list):
                    turn_num = i + 1
                    dist_content += f"execute if score @s Turn matches {turn_num} run return run function {func_base}/turn/turn_{turn_num}\n"
                    
                    # Generate turn_{n}.mcfunction
                    turn_file_content = f"# ターン {turn_num} のアクション\n"
                    
                    # Probability Check
                    prob_str = t_data.get('prob', '').strip().replace('%', '')
                    prob_val = 100
                    if prob_str and prob_str.isdigit():
                         prob_val = int(prob_str)
                    
                    prefix = ""
                    if prob_val < 100:
                        turn_file_content += f"# 発動確率: {prob_val}%\n"
                        turn_file_content += f"function lib:calc/random100\n"
                        prefix = f"execute if score $random _ matches ..{prob_val - 1} run "

                    # Skill
                    skill_json = t_data.get('skill')
                    if skill_json and skill_json.strip():
                        turn_file_content += f"{prefix}data modify storage rpg_skill: data set value {skill_json}\n"
                        turn_file_content += f"{prefix}function skill:execute\n"
                    
                    # MP Cost
                    mp_cost = t_data.get('mp')
                    if mp_cost and mp_cost.strip():
                        turn_file_content += f"{prefix}scoreboard players remove @s MP {mp_cost}\n"
                    
                    # Setup Next Turn
                    next_idx = (i + 1) % len(turn_data_list)
                    next_turn_num = next_idx + 1
                    next_interval = turn_data_list[next_idx].get('interval') or '20'
                    
                    turn_file_content += f"\n# 次のターンのセットアップ\n"
                    turn_file_content += f"scoreboard players set @s Interval {next_interval}\n"
                    turn_file_content += f"scoreboard players set @s Turn {next_turn_num}\n"
                    
                    files.append({
                        'path': base_path / "turn" / f"turn_{turn_num}.mcfunction",
                        'content': turn_file_content,
                        'name': f"{name_jp} (Turn {turn_num})"
                    })

                # Loop Guard
                dist_content += f"execute unless score @s Turn matches 1..{len(turn_data_list)} run scoreboard players set @s Turn 1\n"
                
                files.append({
                    'path': base_path / "turn_distributor.mcfunction",
                    'content': dist_content,
                    'name': f"{name_jp} (Turn Distributor)"
                })

            tick_content = f"""# {name_jp} - Tick Function
# 初期化チェック
execute if entity @s[tag=Init] run function {func_base}/init
execute if entity @s[tag=Init] run tag @s remove Init

{turn_logic}
# ここにインターバル/ターン制スキルを追加可能
"""
            files.append({
                'path': tick_file_path,
                'content': tick_content,
                'name': f"{name_jp} (Tick/InitWrapper)"
            })

    return files


    return files


def generate_bank_file(mob_data, index, name_us_to_id):
    """
    【ステップ3】MOBの設定ファイルを作る（メイン）
    1体のMOBデータを受け取って、以下の2つのファイルの中身を作ります。
    
    1. Registerファイル: データ登録用 (bank/mob/xxx/register.mcfunction)
    2. Wrapperファイル: コマンド呼び出し用 (mob/spawn/xxx.mcfunction)
    
    name_us_to_id: NameUS → unique_id マッピング辞書（サブフォルダ対応用）
    """
    
    # 必須フィールド（名前など）がない場合は作らない
    name_jp = mob_data.get('NameJP', '').strip()
    if not name_jp:
        return None, None
    
    # 英語名（ファイル名用）
    name_us = mob_data.get('NameUS', name_jp).strip()
    base_entity_raw = mob_data.get('ID', 'zombie').strip()
    
    if base_entity_raw and not base_entity_raw.startswith('minecraft:'):
        base_entity = f"minecraft:{base_entity_raw}"
    else:
        base_entity = base_entity_raw if base_entity_raw else 'minecraft:zombie'
        
    custom_name_raw = mob_data.get('ベース', '').strip()
    equipment_raw = mob_data.get('見た目', '').strip()
    
    # IDの生成 (NameUSベース)
    simple_id = snake_case(name_us)
    
    # NameUSが初出なら新規ID、既出なら既存IDを使用
    if name_us not in name_us_to_id:
        name_us_to_id[name_us] = f"{index:03d}.{simple_id}"
    unique_id = name_us_to_id[name_us]
    
    # サブフォルダ処理
    subfolder = mob_data.get('サブフォルダ', '').strip()
    if subfolder:
        subfolder_snake = snake_case(subfolder)
        # "Main" の場合は連番を付けない（特別扱い）
        if subfolder.lower() == 'main':
            subfolder_id = subfolder_snake
        else:
            # Main以外は連番を付ける
            subfolder_id = f"{index:03d}.{subfolder_snake}"
    else:
        subfolder_id = None
    
    # カテゴリ情報（タグとしては残すが、フォルダ分けには使わない）
    area = mob_data.get('エリア', 'global').strip().lower()
    group = mob_data.get('グループ', 'ground').strip().lower()
    ai_raw = mob_data.get('AI', 'blow').strip().lower()
    if ai_raw == 'boss': ai = 'blow'
    else: ai = ai_raw
    
    spawn_tags_raw = mob_data.get('スポーンタグ', '').strip()
    is_boss = 'BOSS' in spawn_tags_raw or 'Boss' in spawn_tags_raw
    
    # 出力先パスの決定 (階層構造: area/group/ai/id[/subfolder])
    if subfolder_id:
        # サブフォルダあり: bank/mob/global/debug/shoot/007.test_summoner/008.henchman/register.mcfunction
        file_path = BANK_DIR / area / group / ai / unique_id / subfolder_id / "register.mcfunction"
        bank_path_str = f"bank:mob/{area}/{group}/{ai}/{unique_id}/{subfolder_id}/register"
        bank_dir_for_wrapper = BANK_DIR / area / group / ai / unique_id / subfolder_id
    else:
        # サブフォルダなし: bank/mob/global/ground/blow/001.goblin/register.mcfunction
        file_path = BANK_DIR / area / group / ai / unique_id / "register.mcfunction"
        bank_path_str = f"bank:mob/{area}/{group}/{ai}/{unique_id}/register"
        bank_dir_for_wrapper = BANK_DIR / area / group / ai / unique_id
    
    # -- タグの設定 --
    # 検索・制御用タグ
    tags = [f"mob.{unique_id}", "Init"] # IDタグ変更
    
    if is_boss: tags.append("mob.boss")
    
    # サブフォルダがある場合、そのサブフォルダIDもタグとして追加（Dispatcherで識別するため）
    if subfolder_id:
        tags.append(f"mob.{subfolder_id}")
    
    tags.append(area.capitalize())
    tags.append(group.capitalize())
    tags.append(ai.capitalize())
    
    if spawn_tags_raw:
        if 'Tags:[' in spawn_tags_raw:
            spawn_tags_content = spawn_tags_raw.split('Tags:[')[1].split(']')[0]
            extra_tags = [t.strip().strip('"').strip("'") for t in spawn_tags_content.split(',') if t.strip()]
            for tag in extra_tags:
                # クォートを除去済みのタグと比較
                if tag.lower() not in [area, group, ai, 'boss']: 
                    tags.append(tag)
        else:
            extra_tags = [t.strip() for t in spawn_tags_raw.split(',') if t.strip()]
            for tag in extra_tags:
                if tag.lower() not in [area, group, ai, 'boss']: tags.append(tag)
    
    # 友好フラグの処理
    is_friendly = mob_data.get('友好', 'FALSE').strip().upper() == 'TRUE'
    if is_friendly:
        tags.append("FRIENDLY")
    else:
        tags.append("ENEMY")
    
    # 以前は tags_str = ','.join(tags) でクォートなしだった
    # SNBTの互換性のため、すべてのタグをダブルクォートで囲むように変更する
    tags_str = ','.join([f'"{t}"' for t in tags])

    # -- Bankファイル(register)の中身を作る --
    
    # 見た目の処理
    appearance_parts = []
    custom_name_clean = '{"text":""}' # デフォルト値
    
    if custom_name_raw:
        custom_name_clean = custom_name_raw.replace('""', '"')
        
        # "CustomName:" というプレフィックスが入っている場合は削除する
        # 例: CustomName:{"text":"Name"} -> {"text":"Name"}
        if custom_name_clean.startswith("CustomName:"):
             custom_name_clean = custom_name_clean[11:].strip()
             
        # Lv表記 (例: Lv.30, Lv 5) を削除する (動的に付与するため)
        # JSON文字列の中にある {"text":"Lv.30"} や "text":" Lv.30" などをターゲットにする
        custom_name_clean = re.sub(r'Lv\.?\s*\d+', '', custom_name_clean)
        
        # 最後に念のため、BaseNameは常にJSON文字列として扱いたいので
        # もしリスト形式やオブジェクト形式でなくてもそのままにする（ユーザー入力を信頼）
        # ただし、誤ったクォート処理をしないように注意
        
        appearance_parts.append(custom_name_clean)
    
    if appearance_parts:
        appearance = '{' + ','.join(appearance_parts) + '}'
    else:
        appearance = '{}'

    # 装備 parsing
    armor_items, hand_items = parse_equipment(equipment_raw)
    armor_str = f"[{','.join(armor_items)}]"
    hand_str = f"[{','.join(hand_items)}]"
    
    # ステータス
    level = mob_data.get('推定lev', '1').strip()
    max_hp = mob_data.get('HP', '20').strip()
    attack = mob_data.get('str', '5').strip()
    defense = mob_data.get('def', '0').strip()
    speed = mob_data.get('agi', '5').strip()
    gold = mob_data.get('gold', '0').strip()
    
    # AIパラメータ
    move_speed_raw = float(mob_data.get('移動速度', '1.0').strip() or '1.0')
    move_speed = f"{move_speed_raw - 1.0:.4f}"
    follow_range_raw = float(mob_data.get('索敵範囲', '1.0').strip() or '1.0')
    follow_range = f"{follow_range_raw - 1.0:.4f}"
    kb_resistance = mob_data.get('ノックバック耐性', '0').strip()
    
    # Spawn Egg の種類を決定
    # 基本的には {base_entity}_spawn_egg だが、例外もあるので簡易処理
    # minecraft:zombie -> zombie_spawn_egg
    base_id_clean = base_entity.replace("minecraft:", "")
    spawn_egg_id = f"{base_id_clean}_spawn_egg"
    
    # 存在しない可能性が高いものや、特殊なものはデフォルト(zombie)または指定のものに
    # ここでは簡易的に「アーマースタンドやマーカーならゾンビ」にする
    if base_id_clean in ['armor_stand', 'marker', 'area_effect_cloud', 'item_display']:
        spawn_egg_id = "zombie_spawn_egg"

    # mcfunction の中身
    content = f"""# {name_jp} データ登録
# ID: {unique_id}
# {bank_path_str}

# 初期化
data modify storage rpg_mob: Instant set value {{}}

# Summon用データ
data modify storage rpg_mob: Instant.Base set value {{id:"{base_entity}",Tags:[{tags_str}]}}
data modify storage rpg_mob: Instant.Costume set value {{equipment:{{feet:{armor_items[0]},legs:{armor_items[1]},chest:{armor_items[2]},head:{armor_items[3]},mainhand:{hand_items[0]},offhand:{hand_items[1]}}}}}

# 見た目 (CustomName)
# CustomName は JSON String として BaseNameJSON に保存する (動的レベル表示のため) -> Baseに含まれるTagsやCustomNameは上記のInstant.Baseで設定済み
# ユーザーの例では CustomName:'...' となっていた。
data modify storage rpg_mob: Instant.Base.CustomName set value '{custom_name_clean}'

# 即時ステータス
data modify storage rpg_mob: Instant.EyePower set value {follow_range}d
data modify storage rpg_mob: Instant.MovementPower set value {move_speed}d
data modify storage rpg_mob: Instant.KBResistance set value {kb_resistance}d
data modify storage rpg_mob: Instant.KBPower set value 0d

# カスタムステータス (Delay)
data modify storage rpg_mob: Delay.Status.Level set value {level}
data modify storage rpg_mob: Delay.Status.HPMax set value {max_hp}f
data modify storage rpg_mob: Delay.Status.MPMax set value 0
data modify storage rpg_mob: Delay.Status.ATK set value {attack}
data modify storage rpg_mob: Delay.Status.DEF set value {defense}
data modify storage rpg_mob: Delay.Status.SPD set value {speed}
data modify storage rpg_mob: Delay.Status.GOLD set value {gold}

# Skill ai
data modify storage rpg_mob: Delay.AI set value {{}}
"""
    
    if ai_raw and ai_raw != 'blow' and ai_raw != 'boss':
         # AIカラムにJSONなどが入っている場合、それを Delay.AI に入れる
         # ユーザーの要望: AIの感じにskillを入力すればいい -> Delay.AIに設定
         if ai_raw.startswith('{'):
             content += f"\n# AI (Custom)\ndata modify storage rpg_mob: Delay.AI set value {ai_raw}\n"
         else:
             content += f"\n# AI (Type)\n# Type: {ai_raw}\n"
    
    if is_boss:
        content += "\n# ボスフラグ\ndata modify storage rpg_mob: Instant.Base.Tags append value \"Boss\"\n"
    
    bank_file = {
        'path': file_path,
        'content': content,
        'mob_id': unique_id,
        'subfolder_id': subfolder_id,  # サブフォルダID追加
        'name': name_jp,
        'bank_path': bank_path_str,  # Wrapper生成用に追加
        'area': area,  # Skill file生成用
        'group': group,
        'ai': ai
    }
    
    return bank_file


def generate_dispatch_files(all_mobs_data):
    """
    【ステップ4】ディスパッチファイル群を作る (GitHub構造準拠)
    - ディレクトリの中に .mcfunction を作成
    - 呼び出しは execute ... run function .../ で終わる
    - タグによる分岐:
        - Bank/Group/AI: Capitalized Tag (Global, Debug, etc.)
        - Mob Root: mob.unique_id
        - Subfolder: mob.subfolder_id
    """
    files = []
    
    # dispatch_tree["global"]["debug"]["shoot"]["007..."]["main"] = {__mob__: ...}
    dispatch_tree = {}
    
    for mob in all_mobs_data:
        if 'bank_path' not in mob:
            continue
            
        full_path = mob['bank_path'] 
        # bank:mob/global/debug/shoot/007.test_summoner/008.henchman/register
        # rel_path: global/debug/shoot/007.test_summoner/008.henchman
        rel_path = full_path.replace("bank:mob/", "").replace("/register", "")
        
        parts = rel_path.split("/")
        
        current_node = dispatch_tree
        for part in parts:
            if part not in current_node:
                current_node[part] = {}
            current_node = current_node[part]
        
        # 葉ノード (subfolder or mob root without subfolder)
        # ここは「そのフォルダ自体」がMobのコンテナであることを示す
        # しかし実装上は、generate_skill_files がそのフォルダ内に .mcfunction (Tick) を作っている
        current_node['__mob__'] = mob

    # 再帰的にファイルを生成
    root_lines, sub_files = generate_dispatch_code_recursive(dispatch_tree, "")
    
    files.extend(sub_files)
    
    # ルートファイル (data/bank/function/mob/.mcfunction)
    # これは function bank:mob/ で呼ばれる
    root_file_path = BANK_DIR.parent / "mob" / ".mcfunction"
    
    files.append({
        'path': root_file_path,
        'content': "\n".join(root_lines),
        'name': "Dispatch: Root (bank/function/mob/.mcfunction)"
    })
    
    return files


def generate_dispatcher_file(all_mobs_data):
    """
    【ステップ5】Dispatcherファイルを作る (Tag -> Path Mapping)
    - data/mob/function/spawn/match_id.mcfunction
    - execute if entity @s[tag=mob.id] run function ...
    """
    # 目的: .../data/mob/function/spawn/match_id.mcfunction
    dispatcher_path = BANK_DIR.parent.parent.parent / "mob" / "function" / "spawn" / "match_id.mcfunction"
    
    lines = [
        "# Tag-based Dispatcher",
        "# Generated by generate_mobs.py",
        "",
        "# マーカー(@s)のタグを見て、対応するRegister関数を呼び出す"
    ]
    
    for mob in all_mobs_data:
        mob_id = mob.get('mob_id')
        bank_path = mob.get('bank_path') # bank:mob/area/group/ai/id/register
        subfolder_id = mob.get('subfolder_id')
        
        if not mob_id or not bank_path:
            continue
            
        # 親ID (007.test_summoner)
        # サブフォルダがある場合、'main' であるときだけ親IDでも呼べるようにする
        if not subfolder_id or subfolder_id.lower() == 'main':
             lines.append(f"execute if entity @s[tag=mob.{mob_id}] run function {bank_path}")
        
        # サブフォルダID (008.henchman or main)
        if subfolder_id:
             lines.append(f"execute if entity @s[tag=mob.{subfolder_id}] run function {bank_path}")
             
    return {
        'path': dispatcher_path,
        'content': "\n".join(lines),
        'name': "System: Mob Dispatcher (match_id.mcfunction)"
    }


def generate_dispatch_code_recursive(node, relative_path=""):
    """
    再帰的にディスパッチコード(行リスト)とファイル定義を生成するヘルパー
    """
    lines = []
    generated_files = []
    
    sub_keys = [k for k in node.keys() if k != '__mob__']
    
    # 1. 子ディレクトリへの分岐
    for key in sub_keys:
        # 子ノードのパス
        child_rel = f"{relative_path}/{key}" if relative_path else key
        
        # 子functionへのパス (末尾スラッシュ必須)
        # bank:mob/global/debug/shoot/
        if relative_path == "":
             child_func_ref = f"bank:mob/{key}/"
        else:
             child_func_ref = f"bank:mob/{relative_path}/{key}/"
             
        # タグの推論
        # 基本: Capitalized (Global, Debug, Shoot)
        # 例外: mob.* (007.test_summoner, main, 008.henchman)
        
        # keyが数字を含むか、ドットを含む場合は Mob系タグとみなす (簡易判定)
        # または、子ノード自身が '__mob__' を持っていれば Mob系
        # しかし subfolder (main) は '__mob__' を持つが数字を含まないこともある
        
        # より確実な方法: node[key] に '__mob__' があるか？
        child_node = node[key]
        tag_condition = ""
        
        if '__mob__' in child_node:
            # そのフォルダ自体がMOBのLeafフォルダ、またはSubfolder
            mob_data = child_node['__mob__']
            
            # Subfolderかどうか判定
            # pathの末尾と key が一致するか？
            # mob['subfolder_id'] == key なら subfolder
            
            if mob_data.get('subfolder_id') == key:
                tag_condition = f"mob.{key}" # subfolder tag (mob.main, mob.008.henchman)
            elif mob_data.get('mob_id') == key:
                # Root Mob Path (007.test_summoner)
                tag_condition = f"mob.{key}"
            else:
                 # fallback
                 tag_condition = key.capitalize()
        else:
            # 中間ディレクトリ (Global, Debug, Shoot ...)
            tag_condition = key.capitalize()
            
        lines.append(f"execute if entity @s[tag={tag_condition}] run function {child_func_ref}")
        
        # 子ファイルの生成
        child_lines, child_files = generate_dispatch_code_recursive(node[key], child_rel)
        
        # 子ファイル定義を追加
        generated_files.extend(child_files)
        
        # ディレクトリ内 .mcfunction を作成
        # path: data/bank/function/mob/global/.mcfunction
        
        # 【修正】child_linesが空の場合（＝葉ノード＝Mob単体フォルダの場合）は
        # Dispatcherファイルを生成しない。
        # そこには generate_skill_files が生成した Tick/Init 用のファイルがあるため。
        # 上書きしてしまうと Tick が動かなくなる。
        if child_lines:
            f_path_rel = f"{child_rel}/.mcfunction"
            f_full = BANK_DIR / f_path_rel.replace("/", "\\") # Windows path separator safe
            
            generated_files.append({
                'path': f_full,
                'content': "\n".join(child_lines),
                'name': f"Dispatch: {child_rel}/.mcfunction"
            })
        
    # 2. 自分自身がLeafの場合 (Skill fileの生成した .mcfunction を呼ぶ必要はない)
    # なぜなら function bank:mob/.../ で呼ばれた時点で、そのフォルダの .mcfunction が実行されるから。
    # ここで生成しているのは「そのフォルダの .mcfunction」の中身そのもの。
    # もし自分自身がMob Leafなら、init/tickのロジックは generate_skill_files 側で生成される ".mcfunction" に書かれている。
    
    # ここでの衝突に注意:
    # generate_skill_files も ".mcfunction" を生成する (Tick/InitWrapper)。
    # generate_dispatch_files も ".mcfunction" を生成する (Dispatcher)。
    
    # Mob Leafフォルダ (例: .../008.henchman/) の場合:
    # generate_skill_files が既に .mcfunction (Init呼び出しなど) を生成している。
    # generate_dispatch_files がそれを上書きすると、Tickロジックが消える！
    
    # 解決策:
    # generate_dispatch_files は「サブディレクトリがある場合」のみ .mcfunction を生成すべき。
    # Leafノード (その下にフォルダがない) に対してはファイルを生成しない（generate_skill_filesに任せる）。
    
    if not sub_keys:
        # Leafノード: 生成しない (files リストに追加しない)
        pass 
        return [], generated_files # linesは空、filesは子供たちが作ったものだけ
        
    return lines, generated_files


def write_files(files):
    """生成されたファイルをディスクに書き込む"""
    
    if not files:
        print("⚠️  生成する MOB データがありません")
        return
    
    print(f"\n[-] {len(files)} 個のファイルを生成中...")
    
    for f_obj in files:
        path = f_obj['path']
        content = f_obj['content']
        
        # ディレクトリを作成
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # ファイルを書き込み
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # print(f"   [OK] {f_obj['name']} -> {path.name}") # 詳細ログは省略
    
    print(f"\n[OK] 完了！合計 {len(files)} ファイルを生成しました")

def main():
    """メイン処理"""
    print("=" * 60)
    print("Minecraft RPG - MOB Generator")
    print("=" * 60)
    
    # 既存のbank/function/mob/*を削除（古いファイルをクリーンアップ）
    if BANK_DIR.exists():
        import shutil
        print(f"\n[-] 既存のMOBデータを削除中: {BANK_DIR}")
        shutil.rmtree(BANK_DIR)
        print(f"   [OK] 削除完了")
    
    # スプレッドシートからデータを取得
    csv_data = fetch_spreadsheet_data()
    if not csv_data:
        return
    
    # CSV データを解析
    print(f"[-] データを解析中...")
    rows = parse_csv_data(csv_data)
    
    # 元のスプレッドシート上の行番号を保持 (Header=1行目ならData=2行目~)
    # parse_csv_dataがリストを返すので、イテレーション順序は維持されている
    for i, r in enumerate(rows):
        r['_original_index'] = i + 2 # ヘッダー(1行) + 0-index(1) = 2行目スタート
        
    print(f"   {len(rows)} 行のデータを検出")
    
    # IDごとにデータをグループ化
    mob_groups = {} # Key: NameJP, Value: List of rows
    ordered_names = [] # 出現順を保持
    
    for row in rows:
        name = row.get('NameJP')
        if name not in mob_groups:
            mob_groups[name] = []
            ordered_names.append(name)
        mob_groups[name].append(row)
        
    print(f"   {len(mob_groups)} 種類の MOB を検出")

    # ファイルを生成
    print(f"\n[-] ファイルを生成中...")
    all_files = []
    name_us_to_id = {}  # NameUS → unique_id マッピング（サブフォルダ対応）
    
    # IDリスト出力用 (RowIndex -> DisplayID)
    id_export_map = {}
    
    bank_info_list = []

    # グループごとに処理
    for idx, name in enumerate(ordered_names, 1):
        group_rows = mob_groups[name]
        primary_row = group_rows[0] # 1行目をメインデータとする
        
        # Outputフラグのチェック (Primary RowがFALSEならスキップ)
        output_flag = primary_row.get('出力', 'TRUE').strip().upper()
        if output_flag == 'FALSE':
            continue
        
        # 既存の generate_bank_file 等は 1つの row (mob dict) を受け取る仕様
        # これを拡張して、group_rows を受け取るようにするか、
        # あるいは必要な「スキルデータ」だけを抽出して渡すか
        
        # ここでは primary_row をベースに、 'TURN_DATA' という新しいフィールドを追加して渡すことにする
        # generate_mobs.py の他の関数は primary_row の情報（ステータスなど）を使う
        
        turn_data = []
        for r in group_rows:
            t_data = {
                'turn': r.get('TURN'),
                'interval': r.get('Interval'),
                'skill': r.get('SKILL'),
                'mp': r.get('-MP'),
                'prob': r.get('%') or r.get('％') or r.get('Prob') or '',
                'row_data': r # 必要なら
            }
            if t_data['turn'] or t_data['interval'] or t_data['skill']:
                turn_data.append(t_data)
        
        primary_row['TURN_DATA_LIST'] = turn_data
        
        # ID生成ロジック (既存流用)
        # name_en = primary_row.get('NameUS', 'Unknown')
        # if not name_en: name_en = 'Unknown'
        # mob_id_str = snake_case(name_en)
        # unique_id = f"{idx:03d}.{mob_id_str}"
        # primary_row['mob_id'] = unique_id # 辞書に注入
        
        # NOTE: generate_bank_file 内で mob_id を計算しているので、そこはそのまま任せるか、
        # あるいはここで計算して渡すか。
        # 既存: bank = generate_bank_file(mob, idx)
        
        bank = generate_bank_file(primary_row, idx, name_us_to_id)
        if bank:
            all_files.append(bank)
            bank_info_list.append(bank)
            
            # IDエクスポート用データを記録 (Primary Row)
            display_id = bank['mob_id']
            if bank.get('subfolder_id'):
                # サブフォルダがある場合、サブフォルダIDを表示
                # Mainの場合(subfolder_id="main")でも "007.test_summoner" (親ID) を表示するか？
                # ユーザー要望: "007.test_summoner" (Main), "008.henchman" (Henchman)
                # subfolder_idが数字で始まる("")008...")ならそちらを優先、
                # そうでなければ親IDを表示
                sf = bank['subfolder_id']
                if sf[0].isdigit():
                     display_id = sf
            
            id_export_map[primary_row['_original_index']] = display_id
            
            # Spawn wrapper は生成しない（debug:summon を使用）
            # wrapper = generate_spawn_wrapper_file(mob, bank['mob_id'], bank.get('bank_path', f"bank:mob/{bank['mob_id']}/register"))
            # all_files.append(wrapper)
            
            # Debug summon を生成
            # サブフォルダがある場合、
            # 1. Main なら 親ID (007.test_summoner) で生成
            # 2. その他 なら サブフォルダID (008.henchman) で生成
            
            debug_summon_id = bank['mob_id']
            if bank.get('subfolder_id'):
                sf = bank['subfolder_id']
                if sf.lower() == 'main':
                    # Main は親IDで生成 (007.test_summoner.mcfunction)
                    debug_summon_id = bank['mob_id']
                else:
                    # 他はサブフォルダIDで生成 (008.henchman.mcfunction)
                    debug_summon_id = sf
            
            debug_summon = generate_debug_summon_file(primary_row, debug_summon_id, bank.get('bank_path', f"bank:mob/{bank['mob_id']}/register"))
            all_files.append(debug_summon)
            
            # Skill files を生成（トリガーがある場合のみ）
            triggers = parse_triggers(primary_row)
            if triggers:
                skill_files = generate_skill_files(
                    primary_row, 
                    bank['mob_id'], 
                    bank['area'], 
                    bank['group'], 
                    bank['ai'], 
                    triggers,
                    bank.get('subfolder_id')  # サブフォルダID追加
                )
                all_files.extend(skill_files)
            
            print(f"   [OK] {bank['name']} ({bank['mob_id']})")

    
    # ファイルを書き込み
    # Dispatch files (復元)
    print("[-] Generating dispatch files...")
    dispatch_files = generate_dispatch_files(bank_info_list)
    all_files.extend(dispatch_files)
    
    # ID Matcher file (New)
    print("[-] Generating matcher file...")
    matcher_file = generate_dispatcher_file(bank_info_list)
    all_files.append(matcher_file)
    
    write_files(all_files)
    
    # IDリストファイル生成
    id_list_path = SCRIPT_DIR / "id_list_updates.txt"
    print(f"\n[-] IDリストを生成中: {id_list_path}")
    
    with open(id_list_path, 'w', encoding='utf-8') as f:
        # 全行分出力（ヘッダーを除く行数分）
        max_row = len(rows) + 1 # 2行目から開始
        for r_idx in range(2, max_row + 2): # python rangeはmax未満まで
             # マップにあればID、なければ空文字
             val = id_export_map.get(r_idx, "")
             f.write(f"{val}\n")
             
             f.write(f"{val}\n")
             
    print(f"   [OK] 生成完了。")

    # Google Sheets API で書き込み
    if HAS_GSPREAD:
        try:
            # 認証情報の確認
            creds_file = SCRIPT_DIR / "credentials.json" # デフォルト
            if not creds_file.exists():
                # ユーザー指定のファイル名を探す
                import glob
                json_files = glob.glob(str(SCRIPT_DIR / "*.json"))
                for jf in json_files:
                    if "mob-generator" in jf and "credentials" not in jf: # credentials.json以外でそれっぽいもの
                        creds_file = Path(jf)
                        break
                # もし credentials.json があればそれを優先
                if (SCRIPT_DIR / "credentials.json").exists():
                    creds_file = SCRIPT_DIR / "credentials.json"
            
            if creds_file.exists():
                print(f"\n[-] Google Sheets API で書き込み中... ({creds_file.name})")
                
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(str(creds_file), scope)
                client = gspread.authorize(creds)
                
                # シートを開く
                sheet = client.open_by_key(SPREADSHEET_ID).get_worksheet(int(SHEET_GID))
                
                # 書き込み用データの整形（リストのリスト）
                # M2セルから開始 (row_index 2 ~ max_row + 2)
                cell_list = []
                # 行数は rows の数 + 1 (Header) だけある
                # rows変数は parse_csv_data の結果 (Headerを含まないデータ行のみ)
                # rowsのインデックスは 0 から始まるが、スプレッドシートは 2行目からデータ開始
                
                # データの行数分ループ
                for r_idx in range(2, len(rows) + 2 + 1): # 余裕を持って少し多めに
                    val = id_export_map.get(r_idx, "")
                    cell_list.append([val])
                
                # 一括更新 (M列 = 13列目)
                # update range: M2:M<last_row>
                end_row = 2 + len(cell_list) - 1
                sheet.update(range_name=f'M2:M{end_row}', values=cell_list)
                
                print(f"   [OK] スプレッドシートのM列を更新しました！")
            else:
                print(f"\n[!] 認証ファイル(credentials.json)が見つからないため、API更新をスキップしました")
        except Exception as e:
            import traceback
            print(f"\n[!] Google Sheets API Error:")
            traceback.print_exc()
            print(f"    手動で id_list_updates.txt の内容をM列に貼り付けてください")
    else:
        print(f"\n[!] gspreadライブラリがないため、自動更新をスキップしました")
        print(f"    pip install gspread oauth2client を実行してください")

    print("\n" + "=" * 60)
    print(f"output (Bank): {BANK_DIR}")
    # print(f"output (Spawn): {SPAWN_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
