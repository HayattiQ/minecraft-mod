# Jarvis CLI 仕様書（Python Core / Mod 連携 / テスト設計）

## 1. 目的

Minecraft Mod（Java/Fabric）から利用する Jarvis のコア機能を、`Python` 製 CLI として定義する。  
本仕様は、以下を固定することを目的とする。

- Mod と CLI のインターフェース（JSON 契約）
- `action` ベースの実行分岐契約（`execute` / `confirm` / `reject`）
- エラー時の挙動と返却形式
- テスト結果の受け取り方法
- エージェントの作業確認フロー

## 2. 前提方針

- Mod 本体は `Java` で実装する
- Jarvis コア（認識受付・応答生成・意図判定）は `Python CLI` で実装する
- Mod と CLI は `stdin/stdout` の JSON で連携する
- CLI 内部の推論基盤はローカル優先とし、必要に応じて外部 API を利用可能とする

## 3. 実行アーキテクチャ

1. Mod が `ProcessBuilder` で Jarvis CLI プロセスを起動する
2. Mod は 1 リクエスト単位で JSON を `stdin` に送る
3. CLI は 1 レスポンス JSON を `stdout` に返す
4. Mod は応答を UI 表示またはコマンド提案/実行に反映する
5. タイムアウト・異常終了時は Mod 側で縮退処理（提案のみ、または会話終了）を行う

## 4. CLI インターフェース定義

### 4.1 Request JSON

```json
{
  "version": "1.0",
  "trace_id": "c0a80123-0001",
  "input": {
    "type": "text",
    "text": "朝にして"
  },
  "player_context": {
    "player_name": "Steve",
    "is_multiplayer": false,
    "is_op": true,
    "world": "overworld"
  }
}
```

必須フィールド:

- `version`
- `trace_id`
- `input.type`（`text` / `audio_ref`）
- `player_context`

### 4.2 Response JSON

```json
{
  "version": "1.0",
  "trace_id": "c0a80123-0001",
  "ok": true,
  "type": "reply",
  "message": "了解。朝にします。",
  "intent": "minecraft_command",
  "command": "/time set day",
  "action": "execute",
  "confidence": 0.95,
  "requires_confirm": false,
  "reason_code": "NONE",
  "error_code": null,
  "latency_ms": 182
}
```

必須フィールド:

- `version`
- `trace_id`
- `ok`
- `type`（`reply` / `error`）
- `message`
- `action`（`execute` / `confirm` / `reject`）
- `confidence`（`0.0`〜`1.0`）
- `reason_code`
- `error_code`（正常時 `null`）
- `latency_ms`

`action` の意味:

- `execute`: Mod 側で即時実行対象として扱う
- `confirm`: Mod 側で確認 UI を表示して承認待ちにする
- `reject`: 実行せず返答表示のみ行う

### 4.3 エラーコード

- `LIMIT_EXCEEDED`
- `TIMEOUT`
- `PERMISSION_DENIED`
- `INVALID_REQUEST`
- `ENGINE_UNAVAILABLE`
- `INTERNAL_ERROR`

エラー時も `stdout` は必ず JSON 1 件を返し、`ok=false` とする。  
プロセスが異常終了した場合は Mod 側で `ENGINE_UNAVAILABLE` として扱う。

## 5. Mod 連携ルール

- Mod は CLI を長寿命プロセスで維持しても、リクエスト都度起動でもよい（MVP は都度起動）
- 1 リクエストのタイムアウトは `3000ms`（MVP 既定）
- タイムアウト時はユーザーに失敗通知し、状態を `AWAKE` 維持または `IDLE` 復帰のいずれかを設定で選択する
- `trace_id` は Mod が発行し、ログ・UI・テスト結果で同一値を使う
- ゲーム継続を最優先とし、失敗時は「未実行 + エラー表示」を基本挙動とする

## 6. テスト設計

### 6.1 テストレイヤー

- `unit`: Python 内部ロジック（意図判定、権限判定、上限判定）
- `contract`: Request/Response JSON スキーマ適合
- `e2e-cli`: `stdin -> stdout` の統合確認（正常系・異常系・タイムアウト）
- `mod-bridge`: Java ProcessBuilder からの起動/通信確認

### 6.2 実行コマンド（標準化）

- `make test-unit`
- `make test-contract`
- `make test-e2e`
- `make test-mod-bridge`
- `make test-all`

### 6.3 結果出力形式

- JUnit XML: `artifacts/test-results/junit-*.xml`
- JSON サマリ: `artifacts/test-results/summary.json`
- 実行ログ: `artifacts/logs/jarvis-test-*.log`

`summary.json` の必須項目:

- `run_id`
- `commit_sha`
- `passed`
- `failed`
- `duration_ms`
- `error_codes`（集計）
- `manual_tests`（手動テスト件数）
- `ai_tests`（自動テスト件数）

### 6.4 人間テスト / AI テストの分離

- AI が担当する範囲:
  - `unit` / `contract` / `e2e-cli` / `mod-bridge` の自動実行
  - 失敗ログの分類と再実行
- 人間が担当する範囲:
  - 実マイク入力による wake word 確認
  - 実際の UI 操作体験（チャット/インベントリ競合時の体感）
  - LLM 応答品質の評価と Skill 改善判断
- リリース判定時は「AI 自動テスト全通 + 人間手動スモーク完了」を必須とする

### 6.5 最低通過条件（ゲート）

- `test-all` が成功すること
- `contract` テスト失敗時は実装変更をマージ不可
- `e2e-cli` の主要シナリオ（`execute` / `confirm` / `reject` / 異常系）全通

## 7. エージェント作業確認フロー

1. 変更対象の仕様 ID を明記して実装する
2. 実装後に `make test-all` を実行する
3. `summary.json` と失敗時ログを確認し、原因を分類する
4. 修正後に再実行し、全通を確認する
5. PR/コミット報告で以下を必ず提示する
   - 実行コマンド
   - pass/fail 件数
   - 主要 `error_code` 件数
   - 影響範囲（どの仕様 ID に対応したか）

## 8. 受け入れ基準

- Mod から CLI を呼び出して JSON 応答を取得できる
- エラー時も JSON 形式で `error_code` を受け取れる
- `test-all` の結果が機械可読で保存される
- 同一 `trace_id` でリクエスト・レスポンス・ログ・テスト結果を追跡できる
