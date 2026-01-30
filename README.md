# Minecraft RPG - MOB Generator

Google スプレッドシートから MOB データを読み込み、Minecraft RPG Datapack の bank ファイルを自動生成する Python スクリプトです。

## 📋 機能

- Google スプレッドシートから CSV 形式で MOB データを取得
- Storage ベースの bank ファイル（`.mcfunction`）を自動生成
- Spawn Egg コマンドの自動生成
- カテゴリごとのディレクトリ構造を自動作成

## 🚀 使い方

### 1. スプレッドシートの準備

Google スプレッドシートを「リンクを知っている全員が閲覧可能」に設定してください。

#### 必要な列

| 列名 | 説明 | 例 |
|------|------|-----|
| `ID` | MOB の識別子（必須） | `goblin` |
| `名前` | 表示名 | `ゴブリン` |
| `レベル` | MOB のレベル | `5` |
| `エンティティ` | ベースエンティティ | `minecraft:zombie` |
| `最大HP` | 最大HP | `50` |
| `物理攻撃力` | 攻撃力 | `10` |
| `物理防御力` | 防御力 | `5` |
| `素早さ` | 素早さ | `7` |
| `運` | 運 | `3` |
| `カテゴリ1` | 大分類 | `Global` |
| `カテゴリ2` | 中分類 | `Ground` |
| `カテゴリ3` | 小分類 | `Blow` |
| `名前色` | 名前の色 | `green` |

### 2. スクリプトの設定

`generate_mobs.py` の冒頭にある以下の設定を編集してください：

```python
SPREADSHEET_ID = "あなたのスプレッドシートID"
SHEET_GID = "0"  # シートのGID
```

### 3. 実行

```bash
python generate_mobs.py
```

## 📁 出力先

生成されたファイルは以下のパスに保存されます：

```
../minecraft_rpg/data/bank/function/mob/[カテゴリ1]/[カテゴリ2]/[カテゴリ3]/[ID].mcfunction
```

## 📦 生成されるファイルの例

```mcfunction
# ゴブリン 設定
# bank:mob/global/ground/blow/goblin

# [Spawn Egg Command]
# give @p zombie_spawn_egg[...] 1

# ベースエンティティ
data modify storage rpg_mob: ベース set value {id:"minecraft:zombie",Tags:[MOB,mob.goblin,mob.new,Global,Ground,Blow,Goblin]}

# 見た目
data modify storage rpg_mob: 見た目 set value {CustomName:[{"color":"green","text":"ゴブリン"},{"color":"gray","text":"Lv5"}]}

# ステータス
data modify storage rpg_mob: レベル set value 5
data modify storage rpg_mob: 最大HP set value 50
data modify storage rpg_mob: 物理攻撃力 set value 10
data modify storage rpg_mob: 物理防御力 set value 5
data modify storage rpg_mob: 素早さ set value 7
data modify storage rpg_mob: 運 set value 3
```

## 🔗 関連プロジェクト

- [minecraft_rpg](https://github.com/YOUR_USERNAME/minecraft_rpg) - メインの Minecraft RPG Datapack

## 📝 ライセンス

MIT License

## 🤝 貢献

プルリクエストを歓迎します！

---

**MinecraftならではのRPG** 🎮
