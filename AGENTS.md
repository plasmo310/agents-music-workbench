# エージェント向けガイド

このリポジトリは、AIエージェント（Codex / Claude Code）に作曲させ、試聴カタログで選んだ曲を REAPER プロジェクトにするための仕組みです。

## 流れ

1. **作曲**（スキル `compose-music`）：`data/library/<バッチID>/compose.py` に音符データを書き、`python python/cli.py render <バッチID>` で WAV・MIDI・一覧データを書き出す。試聴カタログ `data/library/index.html` にバッチのタブが追加される。
2. **選曲**（利用者）：カタログで試聴して★を付け、「プロジェクト生成リストを保存」を押す → `data/project-lists/latest.json`（またはダウンロードフォルダの `project-list-latest.json`）。
3. **プロジェクト生成**（スキル `create-reaper-project`）：`python python/cli.py project all` で、最新のリストの曲を音源別の REAPER プロジェクトにする → `data/projects/<ジョブID>/`。

依頼に応じて、該当するスキル（本体は `.agents/skills/`）を読んでから作業すること。

## コマンド

```
python python/cli.py new-batch <名前> [--example]   作曲バッチの雛形
python python/cli.py render <バッチID> [--force]      書き出し＋カタログ更新
python python/cli.py catalog                          カタログだけ作り直す
python python/cli.py project-list [--file PATH]       最新のプロジェクト生成リストを表示
python python/cli.py project all [--profiles ...]     リスト → REAPERプロジェクト（prepare + build）
python python/cli.py project build [<ジョブID>] [--stage pilot] [--force]   制作の再開・続行
python python/cli.py doctor                           環境確認
python python/cli.py sync-skills                      .agents/skills から Claude Code 用の案内 .claude/skills を作り直す
python -m unittest discover -s tests                  テスト
```

Python 3.10 以上と numpy が必要。`python` で numpy が読めない環境では、numpy の入った Python を使う。

## ディレクトリ

| 場所 | 内容 | Git |
|---|---|---|
| `python/cli.py` | 入口。パスはすべて `python/settings.py` の `ROOT`（リポジトリのルート）基準 | 管理 |
| `python/music/` | スコア形式（Cue/Note/Scale）・プレビューシンセ・MIDI・バッチ書き出し | 管理 |
| `python/catalog/` | 試聴カタログHTML・プロジェクト生成リスト | 管理 |
| `python/reaper/` | REAPER連携（`lua/` はREAPER内で動くスクリプト、`lua/profiles/` は音源プロファイル） | 管理 |
| `.agents/skills/` | スキルの本体。編集したら `sync-skills` を実行（`.claude/skills/` は案内のみ） | 管理 |
| `examples/` | 作曲バッチの見本 | 管理 |
| `data/library/` | 作曲バッチと試聴カタログ（生成物） | 対象外 |
| `data/project-lists/` | プロジェクト生成リスト（カタログから保存） | 対象外 |
| `data/projects/` | REAPER プロジェクト一式（生成物） | 対象外 |
| `_reference/` | 以前の試作。生成物は `data/library/`・`data/projects/` に取り込み済み（`import_to_library.py`）。参照のみ | 対象外 |

## 守ること

- 既存のバッチ・ジョブ・`_reference/` を上書き・削除しない。改訂は新しいバッチ／ジョブとして作る（`render --force` は利用者が未試聴の直後の修正に限る）。
- プロジェクト生成は、利用者が保存したリストの曲だけを対象にする。リストがない・曲が見つからないときは、別の曲や全曲で代用しない。
- REAPER では新しいタブだけを操作する。利用者が開いているプロジェクトを閉じたり変更したりしない。ダイアログが出て止まったら、勝手に操作せず利用者に確認する。
- 音源プロファイルのパラメーター名・値を推測で書かない。REAPER 上で確認する。
- 自動検査は音楽的な品質を保証しない。聴いていなければ「未試聴」と報告する。
