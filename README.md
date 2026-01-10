# Minecraft Java 1.21.1 Mod + データパック作業用リポジトリ

Minecraft Java 1.21.1 向けに、データパックと mod を並行して作るための作業ディレクトリです。

## 構成

- `datapack/` - データパック本体（pack.mcmeta, data/）
- `mod/` - mod 本体（Gradle プロジェクト）
- `shared/` - 共通の設計メモやアセット案
- `tools/` - 補助スクリプトや検証ツール

## 対象バージョン

- Minecraft Java: 1.21.1
- Java: JDK 21

## ローダーについて

現在よく使われる選択肢は以下です。

- Fabric（軽量・更新が早い・API が小さめ）
- NeoForge（Forge の後継、エコシステムが大きい）

迷ったら 1.21.x では Fabric が無難です。Forge/NeoForge 専用の mod を使う予定があるなら NeoForge を選ぶのが良いです。

## 次のステップ

1. ローダーを決める（Fabric / NeoForge）
2. `mod/` をテンプレートで初期化する
3. 必要に応じて `datapack/` にデータパックの雛形を作る

## WSL からデータパックを同期する（rsync）

WSL から Windows 側の `.minecraft` に同期するためのスクリプトを用意しています。

### 準備

1. `.env.example` をコピーして `.env` を作成
2. 環境ごとの上書きが必要なら `.env.local` を作成（Git 管理外）
3. `WIN_USER`, `MC_DIR`, `WORLD_NAME`, `DATAPACK_NAME` を設定

### 実行

```bash
tools/sync-datapack.sh
```

dotenvx を使う場合は、次のように実行できます。

```bash
dotenvx run -- tools/sync-datapack.sh
```
