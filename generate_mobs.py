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
BANK_DIR = DATAPACK_DIR / "data" / "bank" / "function" / "mob"
SPAWN_DIR = DATAPACK_DIR / "data" / "mob" / "function" / "spawn"
SPAWN_MAP_DIR = DATAPACK_DIR / "data" / "mob" / "function" / "spawn_map"

def fetch_spreadsheet_data():
    """
    【ステップ1】スプレッドシートからデータを取ってくる
    インターネット経由で Google のサーバーにアクセスし、CSVデータをダウンロードします。
    """
    print(f"📥 スプレッドシートからデータを取得中...")
    print(f"   URL: {CSV_URL}")
    
    try:
        with urllib.request.urlopen(CSV_URL) as response:
            data = response.read().decode('utf-8')
            return data
    except Exception as e:
        print(f"❌ エラー: スプレッドシートの取得に失敗しました")
        print(f"   {e}")
        print(f"\n💡 ヒント: スプレッドシートが「リンクを知っている全員が閲覧可能」に設定されているか確認してください")
        return None

def parse_csv_data(csv_data):
    """
    【ステップ2】データを読みやすい形に整理する
    ダウンロードした文字の羅列（CSV）を、プログラムで扱いやすいリスト形式に変換します。
    名前が空欄の行はスキップします。
    """
    reader = csv.DictReader(csv_data.splitlines())
    mobs = []
    
    for row in reader:
        # 空行をスキップ（NameJPがない行は無視）
        if not row.get('NameJP') or not row.get('NameJP').strip():
            continue
            
        mobs.append(row)
    
    return mobs

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

def get_nbt_str(mob_data, is_boss, mob_id, tags_str):
    """召喚用のNBT文字列を生成"""
    
    # NBTパーツ
    nbt_parts = []
    
    # Tagsは引数で渡されたものを使用（すでに生成済み）
    nbt_parts.append(f"Tags:[{tags_str}]")
    
    # CustomName
    custom_name_raw = mob_data.get('ベース', '').strip()
    name_jp = mob_data.get('NameJP', '').strip()
    level = mob_data.get('推定lev', '1').strip()
    
    if custom_name_raw and 'CustomName' in custom_name_raw:
        custom_name = custom_name_raw.replace('""', '"')
        nbt_parts.append(custom_name)
    else:
        nbt_parts.append(f'CustomName:[{{"text":"{name_jp}"}},{{"text":" Lv{level}","color":"gray"}}]')
    
    # Equipment
    equipment_raw = mob_data.get('見た目', '').strip()
    if equipment_raw and 'mainhand' in equipment_raw:
        equipment_raw = equipment_raw.replace('""', '"').strip()
        import re
        match = re.search(r'mainhand:\{[^}]+\}', equipment_raw)
        if match:
            nbt_parts.append(f'equipment:{{{match.group(0)}}}')
            
    nbt_parts.append("CustomNameVisible:true")
    nbt_parts.append("PersistenceRequired:true")
    
    return "{" + ",".join(nbt_parts) + "}"

def generate_spawn_map_file(mob_data, bank_path_str, mob_id):
    """spawn_map ファイルを生成"""
    name_jp = mob_data.get('NameJP', 'Unknown')
    
    # ベースエンティティ
    base_entity_raw = mob_data.get('ID', 'zombie').strip()
    if base_entity_raw and not base_entity_raw.startswith('minecraft:'):
        base_entity = f"minecraft:{base_entity_raw}"
    else:
        base_entity = base_entity_raw if base_entity_raw else 'minecraft:zombie'
        
    # NBT再生成（Tagsなどはgenerate_bank_fileと同じロジックが必要だが、DRYのために分離すべき）
    # ここでは簡易的にbank_file生成時に必要な情報を渡してもらうか、再計算する。
    # 再計算コストは低いので再計算する。
    
    # タグ生成ロジック再利用（関数化すべきだが、一旦コピペで対応。リファクタ対象）
    area = mob_data.get('エリア', 'global').strip().lower()
    group = mob_data.get('グループ', 'ground').strip().lower()
    ai_raw = mob_data.get('AI', 'blow').strip().lower()
    if ai_raw == 'boss':
        ai = 'blow'
    else:
        ai = ai_raw
        
    spawn_tags_raw = mob_data.get('スポーンタグ', '').strip()
    is_boss = 'BOSS' in spawn_tags_raw or 'Boss' in spawn_tags_raw
    
    tags = ["MOB", f"mob.{mob_id}", "mob.new"]
    if is_boss: tags.append("mob.boss")
    tags.append(area.capitalize())
    tags.append(group.capitalize())
    tags.append(ai.capitalize())
    
    if spawn_tags_raw:
        # 簡易パース
        extra_tags = [t.strip() for t in spawn_tags_raw.replace('Tags:[','').replace(']','').split(',') if t.strip()]
        for tag in extra_tags:
            tag_lower = tag.lower()
            if tag_lower not in [area, group, ai, 'boss']:
                tags.append(tag)
    
    tags_str = ','.join(tags)
    nbt_str = get_nbt_str(mob_data, is_boss, mob_id, tags_str)
    
    # セットアップ関数
    setup_path = "mob:setup/apply_from_storage"
    
    content = f"""# {name_jp}の実体召喚処理
# spawn_map: {mob_id}

# 設定をロード（Storage: rpg_mob）
function {bank_path_str}

summon {base_entity} ~ ~ ~ {nbt_str}

# 新規MOBにステータスを設定
execute as @e[tag=mob.{mob_id},tag=!mob.initialized,limit=1] run function {setup_path}
"""
    
    path = SPAWN_MAP_DIR / f"{mob_id}.mcfunction"
    return {
        'path': path,
        'content': content,
        'name': f"{name_jp} (SpawnMap)"
    }

def generate_spawn_wrapper_file(mob_data, mob_id):
    """spawn ラッパーファイルを生成"""
    name_jp = mob_data.get('NameJP', 'Unknown')
    
    content = f"""# {name_jp}を召喚（ラッパー）
# 使用方法: /function mob:spawn/{mob_id}

function mob:spawn_map/{mob_id}
"""
    path = SPAWN_DIR / f"{mob_id}.mcfunction"
    return {
        'path': path,
        'content': content,
        'name': f"{name_jp} (SpawnWrapper)"
    }


def generate_bank_file(mob_data):
    """
    【ステップ3】MOBの設定ファイルを作る（メイン）
    1体のMOBデータを受け取って、以下の3つのファイルの中身を作ります。
    
    1. Bankファイル: ステータス、装備、タグなどの設定データ（Storageに保存される）
    2. SpawnMapファイル: 実際に召喚コマンドを実行するファイル
    3. Wrapperファイル: 人間がコマンド入力しやすいようにするための短いファイル
    """
    
    # 必須フィールド（名前など）がない場合は作らない
    name_jp = mob_data.get('NameJP', '').strip()
    if not name_jp:
        return None, None, None # bank, spawn_map, wrapper
    
    # -- データの読み取り開始 --
    
    # 英語名（ファイル名用）
    name_us = mob_data.get('NameUS', name_jp).strip()
    # ベースになるエンティティ（ゾンビなど）
    base_entity_raw = mob_data.get('ID', 'zombie').strip()  # ID列 = エンティティタイプ
    
    # 'minecraft:' がついてなければつける
    if base_entity_raw and not base_entity_raw.startswith('minecraft:'):
        base_entity = f"minecraft:{base_entity_raw}"
    else:
        base_entity = base_entity_raw if base_entity_raw else 'minecraft:zombie'
        
    custom_name_raw = mob_data.get('ベース', '').strip()  # ベース列 = CustomName
    equipment_raw = mob_data.get('見た目', '').strip()  # 見た目列 = equipment
    
    # ファイル名用のIDを作成
    mob_id = snake_case(name_us)
    
    
    # カテゴリ情報の取得（フォルダ分け用）
    area = mob_data.get('エリア', 'global').strip().lower()  # エリア列 = global
    group = mob_data.get('グループ', 'ground').strip().lower()  # グループ列 = ground
    ai_raw = mob_data.get('AI', 'blow').strip().lower()  # AI列 = blow/shoot/boss
    
    # ボスなら boss フォルダに入れる
    if ai_raw == 'boss':
        ai = 'blow'   # AIタイプとしての基本は blow
        subfolder = 'boss'
    else:
        ai = ai_raw
        subfolder = ''
    
    # スポーンタグ（追加情報）
    spawn_tags_raw = mob_data.get('スポーンタグ', '').strip()
    
    # ステータスの読み取り
    level = mob_data.get('推定lev', '1').strip()
    max_hp = mob_data.get('HP', '20').strip()
    attack = mob_data.get('str', '5').strip()
    defense = mob_data.get('def', '0').strip()
    speed = mob_data.get('agi', '5').strip()
    luck = mob_data.get('luck', '0').strip()
    
    # AIパラメータ
    move_speed = mob_data.get('移動速度', '0.23').strip()
    follow_range = mob_data.get('索敵範囲', '35').strip()
    kb_resistance = mob_data.get('ノックバック耐性', '0').strip()
    base_atk = mob_data.get('攻撃力', '3').strip()
    
    # ボスかどうか判定
    is_boss = 'BOSS' in spawn_tags_raw or 'Boss' in spawn_tags_raw
    
    # 出力先パスの決定（カテゴリによってフォルダが変わります）
    if subfolder:
        file_path = BANK_DIR / area / group / ai / subfolder / f"{mob_id}.mcfunction"
        bank_path_str = f"bank:mob/{area}/{group}/{ai}/{subfolder}/{mob_id}"
    else:
        file_path = BANK_DIR / area / group / ai / f"{mob_id}.mcfunction"
        bank_path_str = f"bank:mob/{area}/{group}/{ai}/{mob_id}"
    
    # -- タグの設定 --
    # TUSB形式のタグ（検索用、制御用）を自動でつけます
    tags = ["MOB", f"mob.{mob_id}", "mob.new"]
    
    if is_boss:
        tags.append("mob.boss")
    
    # カテゴリタグ（Global, Ground など）
    tags.append(area.capitalize())   # Global
    tags.append(group.capitalize())  # Ground
    tags.append(ai.capitalize())     # Blow/Shoot
    
    # 追加タグ
    if spawn_tags_raw:
        if 'Tags:[' in spawn_tags_raw:
            spawn_tags_content = spawn_tags_raw.split('Tags:[')[1].split(']')[0]
            extra_tags = [t.strip() for t in spawn_tags_content.split(',') if t.strip()]
            for tag in extra_tags:
                tag_lower = tag.lower()
                if tag_lower not in [area, group, ai, 'boss']:
                    tags.append(tag)
        else:
            # Tags:[] がない場合はカンマ区切りと仮定
            extra_tags = [t.strip() for t in spawn_tags_raw.split(',') if t.strip()]
            for tag in extra_tags:
                tag_lower = tag.lower()
                if tag_lower not in [area, group, ai, 'boss']:
                    tags.append(tag)
    
    tags_str = ','.join(tags)

    # -- Bankファイルの中身を作る --
    
    # 見た目の処理
    appearance_parts = []
    
    # 名前
    if custom_name_raw:
        custom_name_clean = custom_name_raw.replace('""', '"')
        appearance_parts.append(custom_name_clean)
    
    # 装備
    if equipment_raw:
        equipment_clean = equipment_raw.replace('""', '"').strip()
        if equipment_clean.startswith('{') and equipment_clean.endswith('}'):
            equipment_clean = equipment_clean[1:-1]
        appearance_parts.append(equipment_clean)
    
    if appearance_parts:
        appearance = '{' + ','.join(appearance_parts) + '}'
    else:
        appearance = '{}'
    
    # mcfunction の中身を書き込み
    content = f"""# {name_jp} 設定
# {bank_path_str}

# [Spawn Egg Command]
# スポーンエッグを入手するためのコマンド（ArmorStand経由でスポーンさせます）
# give @p zombie_spawn_egg[entity_data={{id:"minecraft:armor_stand",NoGravity:1b,Invisible:1b,Tags:["mob.egg_spawn"],equipment:{{head:{{id:"minecraft:stone",count:1,components:{{"minecraft:custom_data":{{"RPGMobId":"{mob_id}"}}}}}}}}}},item_name={{"text":"{name_jp} Spawn Egg","color":"gold"}}] 1

# ベースエンティティ（即時ステータス）
# ここで設定したタグやIDが最初に適用されます
data modify storage rpg_mob: ベース set value {{id:"{base_entity}",Tags:[{tags_str}]}}

# 見た目
# 名前や装備品を設定します
data modify storage rpg_mob: 見た目 set value {appearance}

# ステータス
# RPG用のステータスを設定します
data modify storage rpg_mob: レベル set value {level}
data modify storage rpg_mob: 最大HP set value {max_hp}
data modify storage rpg_mob: 物理攻撃力 set value {attack}
data modify storage rpg_mob: 物理防御力 set value {defense}
data modify storage rpg_mob: 素早さ set value {speed}
data modify storage rpg_mob: 運 set value {luck}

# AIパラメータ
# 移動速度、索敵範囲、ノックバック耐性など
data modify storage rpg_mob: ai_speed set value {move_speed}
data modify storage rpg_mob: ai_follow_range set value {follow_range}
data modify storage rpg_mob: ai_knockback_resistance set value {kb_resistance}
# data modify storage rpg_mob: ai_attack_damage set value {base_atk} (基本攻撃力: 必要なら使用)
"""
    
    if is_boss:
        content += "\n# ボスフラグ\ndata modify storage rpg_mob: ボス set value true\n"
    
    bank_file = {
        'path': file_path,
        'content': content,
        'mob_id': mob_id,
        'name': name_jp
    }
    
    # spawn_map と wrapper の生成
    spawn_map_file = generate_spawn_map_file(mob_data, bank_path_str, mob_id)
    wrapper_file = generate_spawn_wrapper_file(mob_data, mob_id)
    
    return bank_file, spawn_map_file, wrapper_file


def write_files(files):
    """生成されたファイルをディスクに書き込む"""
    
    if not files:
        print("⚠️  生成する MOB データがありません")
        return
    
    print(f"\n📝 {len(files)} 個のファイルを生成中...")
    
    for f_obj in files:
        path = f_obj['path']
        content = f_obj['content']
        
        # ディレクトリを作成
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # ファイルを書き込み
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # print(f"   ✅ {f_obj['name']} -> {path.name}") # 詳細ログは省略
    
    print(f"\n✨ 完了！合計 {len(files)} ファイルを生成しました")

def main():
    """メイン処理"""
    print("=" * 60)
    print("🎮 Minecraft RPG - MOB Generator")
    print("=" * 60)
    
    # スプレッドシートからデータを取得
    csv_data = fetch_spreadsheet_data()
    if not csv_data:
        return
    
    # CSV データを解析
    print(f"📋 データを解析中...")
    mobs = parse_csv_data(csv_data)
    print(f"   {len(mobs)} 個の MOB データを検出")
    
    # ファイルを生成
    print(f"\n🔨 ファイルを生成中...")
    all_files = []
    
    for mob in mobs:
        bank, spawn_map, wrapper = generate_bank_file(mob)
        if bank:
            all_files.append(bank)
            all_files.append(spawn_map)
            all_files.append(wrapper)
            print(f"   ✅ {bank['name']} ({bank['mob_id']})")
    
    # ファイルを書き込み
    write_files(all_files)
    
    print("\n" + "=" * 60)
    print(f"📦 出力先 (Bank): {BANK_DIR}")
    print(f"📦 出力先 (Spawn): {SPAWN_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
