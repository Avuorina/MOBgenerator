#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOB Generator for Minecraft RPG Datapack
Google スプレッドシートから MOB データを読み込み、bank ファイルを生成します。
"""

import csv
import urllib.request
from pathlib import Path
import json

# Google スプレッドシートの設定
SPREADSHEET_ID = "1Muf5Hy6Zq1i8Rty1M26-5u13lalUBsuC-pVXNFXMoYM"
SHEET_GID = "0"  # 最初のシート
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}"

# 出力先のパス（このスクリプトの親ディレクトリから相対パス）
SCRIPT_DIR = Path(__file__).parent
DATAPACK_DIR = SCRIPT_DIR.parent / "minecraft_rpg"
BANK_DIR = DATAPACK_DIR / "data" / "bank" / "function" / "mob"

def fetch_spreadsheet_data():
    """Google スプレッドシートから CSV データを取得"""
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
    """CSV データを解析して MOB データのリストを返す"""
    reader = csv.DictReader(csv_data.splitlines())
    mobs = []
    
    for row in reader:
        # 空行をスキップ
        if not row.get('NameJP') or not row.get('NameJP').strip():
            continue
            
        mobs.append(row)
    
    return mobs

def snake_case(text):
    """文字列を snake_case に変換（キャメルケース対応）"""
    import re
    # キャメルケースをスネークケースに変換
    # 例: SkeletonWarrior → skeleton_warrior, DarkKnight → dark_knight
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()

def generate_bank_file(mob_data):
    """MOB データから bank ファイルを生成"""
    
    # 必須フィールドの取得
    name_jp = mob_data.get('NameJP', '').strip()
    if not name_jp:
        print(f"⚠️  警告: NameJP が空の MOB をスキップしました")
        return None
    
    # 各種パラメータの取得
    # スプレッドシートの正しい列構造:
    # NameJP: 日本語名
    # /summon: (空白)
    # ID: エンティティタイプ (zombie, skeleton, wither_skeleton)
    # ベース: CustomName の JSON
    # 見た目: equipment の JSON (mainhand など)
    # エリア: (空白)
    # グループ: global
    # AI: ground
    # サブフォルダ: blow, shoot, boss など
    # スポーンタグ: Tags:[]
    name_us = mob_data.get('NameUS', name_jp).strip()
    base_entity_raw = mob_data.get('ID', 'zombie').strip()  # ID列 = エンティティタイプ
    
    # minecraft: プレフィックスを追加（ない場合）
    if base_entity_raw and not base_entity_raw.startswith('minecraft:'):
        base_entity = f"minecraft:{base_entity_raw}"
    else:
        base_entity = base_entity_raw if base_entity_raw else 'minecraft:zombie'
    
    custom_name_raw = mob_data.get('ベース', '').strip()  # ベース列 = CustomName
    equipment_raw = mob_data.get('見た目', '').strip()  # 見た目列 = equipment
    
    # MOB IDはNameUSから生成
    mob_id = snake_case(name_us)
    
    
    # カテゴリ情報の取得（正しい列マッピング）
    # エリア列 = global
    # グループ列 = ground
    # AI列 = blow/shoot/boss
    area = mob_data.get('エリア', 'global').strip().lower()  # エリア列 = global
    group = mob_data.get('グループ', 'ground').strip().lower()  # グループ列 = ground
    ai_raw = mob_data.get('AI', 'blow').strip().lower()  # AI列 = blow/shoot/boss
    
    # ボスの判定とディレクトリ構造の決定
    if ai_raw == 'boss':
        # ボスの場合: global/ground/blow/boss/
        ai = 'blow'
        subfolder = 'boss'
    else:
        # 通常MOB: global/ground/blow/ または global/ground/shoot/
        ai = ai_raw
        subfolder = ''
    
    # タグ情報（スプレッドシートから取得）
    spawn_tags_raw = mob_data.get('スポーンタグ', '').strip()
    
    # ステータス
    level = mob_data.get('推定lev', '1').strip()
    max_hp = mob_data.get('HP', '20').strip()
    attack = mob_data.get('str', '5').strip()
    defense = mob_data.get('def', '0').strip()
    speed = mob_data.get('agi', '5').strip()
    luck = mob_data.get('luck', '0').strip()
    
    # ボスフラグの判定
    is_boss = 'BOSS' in spawn_tags_raw or 'Boss' in spawn_tags_raw
    
    # ファイルパスの生成
    if subfolder:
        file_path = BANK_DIR / area / group / ai / subfolder / f"{mob_id}.mcfunction"
        bank_path = f"bank:mob/{area}/{group}/{ai}/{subfolder}/{mob_id}"
    else:
        file_path = BANK_DIR / area / group / ai / f"{mob_id}.mcfunction"
        bank_path = f"bank:mob/{area}/{group}/{ai}/{mob_id}"
    
    # タグの生成 (TUSB 形式)
    # 基本タグ: MOB, mob.{id}, mob.new
    tags = ["MOB", f"mob.{mob_id}", "mob.new"]
    
    # ボスタグ
    if is_boss:
        tags.append("mob.boss")
    
    # カテゴリタグ（大文字）: Global, Ground, Blow など
    tags.append(area.capitalize())   # Global
    tags.append(group.capitalize())  # Ground
    tags.append(ai.capitalize())     # Blow/Shoot
    
    # スポーンタグから追加タグを抽出（MOB名など）
    if spawn_tags_raw:
        if 'Tags:[' in spawn_tags_raw:
            spawn_tags_content = spawn_tags_raw.split('Tags:[')[1].split(']')[0]
            extra_tags = [t.strip() for t in spawn_tags_content.split(',') if t.strip()]
            # カテゴリタグ（Global, Ground, Blow など）は除外して、MOB名のみ追加
            for tag in extra_tags:
                # 小文字にしてカテゴリタグと比較
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


    
    # 見た目の処理
    appearance_parts = []
    
    # CustomName の処理
    if custom_name_raw:
        # スプレッドシートの二重引用符をエスケープ解除
        custom_name_clean = custom_name_raw.replace('""', '"')
        appearance_parts.append(custom_name_clean)
    
    # 装備の処理
    if equipment_raw:
        equipment_clean = equipment_raw.replace('""', '"').strip()
        
        # 既に {...} で囲まれている場合は中身だけ取得
        if equipment_clean.startswith('{') and equipment_clean.endswith('}'):
            equipment_clean = equipment_clean[1:-1]
        
        appearance_parts.append(equipment_clean)
    
    # 見た目を結合
    if appearance_parts:
        appearance = '{' + ','.join(appearance_parts) + '}'
    else:
        appearance = '{}'
    
    # ファイル内容の生成
    content = f"""# {name_jp} 設定
# {bank_path}

# [Spawn Egg Command]
# give @p zombie_spawn_egg[entity_data={{id:"minecraft:armor_stand",NoGravity:1b,Invisible:1b,Tags:["mob.egg_spawn"],equipment:{{head:{{id:"minecraft:stone",count:1,components:{{"minecraft:custom_data":{{"RPGMobId":"{mob_id}"}}}}}}}}}},item_name={{"text":"{name_jp} Spawn Egg","color":"gold"}}] 1

# ベースエンティティ（即時ステータス）
data modify storage rpg_mob: ベース set value {{id:"{base_entity}",Tags:[{tags_str}]}}

# 見た目
data modify storage rpg_mob: 見た目 set value {appearance}

# ステータス
data modify storage rpg_mob: レベル set value {level}
data modify storage rpg_mob: 最大HP set value {max_hp}
data modify storage rpg_mob: 物理攻撃力 set value {attack}
data modify storage rpg_mob: 物理防御力 set value {defense}
data modify storage rpg_mob: 素早さ set value {speed}
data modify storage rpg_mob: 運 set value {luck}
"""
    
    # ボスフラグの追加
    if is_boss:
        content += "\n# ボスフラグ\ndata modify storage rpg_mob: ボス set value true\n"
    
    return {
        'path': file_path,
        'content': content,
        'mob_id': mob_id,
        'name': name_jp
    }

def write_bank_files(bank_files):
    """生成された bank ファイルをディスクに書き込む"""
    
    if not bank_files:
        print("⚠️  生成する MOB データがありません")
        return
    
    print(f"\n📝 {len(bank_files)} 個の bank ファイルを生成中...")
    
    for bank_file in bank_files:
        path = bank_file['path']
        content = bank_file['content']
        
        # ディレクトリを作成
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # ファイルを書き込み
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"   ✅ {bank_file['name']} ({bank_file['mob_id']})")
    
    print(f"\n✨ 完了！{len(bank_files)} 個の MOB を生成しました")

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
    
    # bank ファイルを生成
    print(f"\n🔨 bank ファイルを生成中...")
    bank_files = []
    for mob in mobs:
        bank_file = generate_bank_file(mob)
        if bank_file:
            bank_files.append(bank_file)
    
    # ファイルを書き込み
    write_bank_files(bank_files)
    
    print("\n" + "=" * 60)
    print(f"📦 出力先: {BANK_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
