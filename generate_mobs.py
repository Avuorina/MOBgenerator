#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOB Generator for Minecraft RPG Datapack
Google スプレッドシートから MOB データを読み込み、bank ファイルを生成します。
"""

import csv
import os
import urllib.request
from pathlib import Path

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
        if not row.get('ID') or not row.get('ID').strip():
            continue
            
        mobs.append(row)
    
    return mobs

def generate_bank_file(mob_data):
    """MOB データから bank ファイルを生成"""
    
    # 必須フィールドの取得
    mob_id = mob_data.get('ID', '').strip()
    if not mob_id:
        print(f"⚠️  警告: ID が空の MOB をスキップしました")
        return None
    
    # 各種パラメータの取得（デフォルト値付き）
    name = mob_data.get('名前', mob_id)
    level = mob_data.get('レベル', '1')
    entity_type = mob_data.get('エンティティ', 'minecraft:zombie')
    
    # ステータス
    max_hp = mob_data.get('最大HP', '20')
    attack = mob_data.get('物理攻撃力', '5')
    defense = mob_data.get('物理防御力', '0')
    speed = mob_data.get('素早さ', '5')
    luck = mob_data.get('運', '0')
    
    # タグ（カテゴリ）の取得
    category1 = mob_data.get('カテゴリ1', 'Global')
    category2 = mob_data.get('カテゴリ2', 'Ground')
    category3 = mob_data.get('カテゴリ3', 'Blow')
    
    # 名前の色
    name_color = mob_data.get('名前色', 'white')
    
    # ファイルパスの生成
    file_path = BANK_DIR / category1.lower() / category2.lower() / category3.lower() / f"{mob_id}.mcfunction"
    
    # ファイル内容の生成
    content = f"""# {name} 設定
# bank:mob/{category1.lower()}/{category2.lower()}/{category3.lower()}/{mob_id}

# [Spawn Egg Command]
# give @p zombie_spawn_egg[entity_data={{id:"minecraft:armor_stand",NoGravity:1b,Invisible:1b,Tags:["mob.egg_spawn"],equipment:{{head:{{id:"minecraft:stone",count:1,components:{{"minecraft:custom_data":{{"RPGMobId":"{mob_id}"}}}}}}}}}},item_name={{"text":"{name} Spawn Egg","color":"gold"}}] 1

# ベースエンティティ（即時ステータス）
data modify storage rpg_mob: ベース set value {{id:"{entity_type}",Tags:[MOB,mob.{mob_id},mob.new,{category1},{category2},{category3},{mob_id.replace('_', ' ').title().replace(' ', '')}]}}

# 見た目
data modify storage rpg_mob: 見た目 set value {{CustomName:[{{"color":"{name_color}","text":"{name}"}},{{"color":"gray","text":"Lv{level}"}}]}}

# ステータス
data modify storage rpg_mob: レベル set value {level}
data modify storage rpg_mob: 最大HP set value {max_hp}
data modify storage rpg_mob: 物理攻撃力 set value {attack}
data modify storage rpg_mob: 物理防御力 set value {defense}
data modify storage rpg_mob: 素早さ set value {speed}
data modify storage rpg_mob: 運 set value {luck}
"""
    
    return {
        'path': file_path,
        'content': content,
        'mob_id': mob_id,
        'name': name
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
