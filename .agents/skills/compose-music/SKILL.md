---
name: compose-music
description: BGM・ジングル・効果音などの候補曲を作曲し、試聴用WAV・パート別MIDI・試聴カタログ（data/library/index.html）に書き出す。「〇〇用のBGMを10曲作って」「SEの候補がほしい」「さっきの曲をもう少し明るく」のような作曲・改訂の依頼で使う。
---

# 作曲して試聴カタログに並べる

このリポジトリでは、作曲は **音符データ（Pythonのスコア）を書くこと** で行う。
`data/library/<バッチID>/compose.py` に曲を定義し、CLI で WAV・MIDI・一覧データを書き出すと、試聴カタログ `data/library/index.html` にバッチ単位のタブが自動で追加される。
利用者はカタログで試聴して★を付け、REAPERプロジェクト化（create-reaper-project スキル）へ進む。

## 手順

1. **依頼を整理する**：用途（会話BGM・まとめ・ジングル・見出しSE など）、尺・ループの要否、候補数、雰囲気、シリーズ分け（例：レトロ版／自由版）、差し替え先。足りない情報は、推測で進めてよい範囲は仮定を明示し、候補数や用途が曖昧なときだけ確認する。
2. **設計する**：
   - [music-composition-skills](https://github.com/jtydhr88/music-composition-skills) が使える場合は、そのワークフロー（ARR-SPEC：調・テンポ・セクション・コード進行・編成・エネルギー曲線）で候補ごとの設計を作る。スキルの一覧は環境のスキル一覧で確認する。
   - 使えない場合は [references/composition-guide.md](references/composition-guide.md) の指針で設計する。
   - 設計の要約は `BATCH['spec']` に残す（カタログの「依頼内容・設計メモ」に表示される）。
3. **バッチを作る**：`python python/cli.py new-batch <名前>` → `data/library/<日付-名前>/compose.py` ができる。
4. **compose.py を書く**：API は [references/score-api.md](references/score-api.md)。`BATCH` に依頼文（`request`）・使用エージェント名（`agent`、例 "Claude Code" / "Codex"）・カテゴリを記録し、`cues()` で `Cue` のリストを返す。
5. **書き出す**：`python python/cli.py render <バッチID>`。WAV/MIDI/manifest/verification を出力し、カタログも更新される。
   - エラーや `注意`（移調・テンポ違いだけの重複など）が出たら compose.py を直して `--force` で書き出し直す。
6. **報告する**：候補の一覧（ID・曲名・狙い）と `data/library/index.html` を案内し、「気に入った曲に★を付けて『プロジェクト生成リストを保存』→『最新のリストでREAPERプロジェクトを生成して』と伝えてください」と伝える。

## 改訂の依頼

- 既存バッチは上書きしない。改訂は新しいバッチ（例：`<日付>-summary-v2`）として作り、`BATCH['description']` に元のバッチIDと変更点を書く。元の compose.py を読み、関数を流用してよい。
- 同じバッチを作り直すのは、利用者がまだ試聴していない直後の修正に限る（`render --force`）。

## 守ること

- 乱数でメロディーを作らない。フレーズ（問いと答え・終止）を意図して書く。乱数を使うなら音色の揺らぎ程度に留め、シードを固定する。
- 候補を単なる移調・テンポ違いで水増ししない。候補ごとに拍子・リズム・編成・旋律の輪郭を変える。
- ループ曲は小節境界で `length` を設定し、フレーズが継ぎ目で自然につながるようにする（最終小節から1小節目へ戻る進行）。
- 既存の曲やメロディーを模倣しない。参照曲名を依頼されても、雰囲気・編成・テンポ感の参考に留める。
- `render` の検査（無音・クリップ・PCM重複・ループ端・MIDI往復）が通っても、音楽的な品質の保証にはならない。聴いていないことは「未試聴」と明記する。
- `data/library/` 以外（`_reference/` など）の既存成果物を変更しない。
