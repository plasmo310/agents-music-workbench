# スコアAPI（python/music/score.py）

compose.py からは `from music import Cue, Note, Scale` で使う（CLI が `python/` を import パスに加える）。

## 時間の単位

- すべて **拍（四分音符 = 1）**。4/4 の1小節 = 4拍、3/4 = 3拍、6/8 = 3拍。
- テンポのないSEは `bpm=None`（作業用120 BPM、1拍 = 0.5秒）。秒で考えたいときは `cue.beats(秒)` で拍に換算する。

## BATCH

```python
BATCH = {
    'title': 'lec-game-001 まとめBGM 改訂',      # タブに表示
    'description': '狙いを1〜2文で',
    'request': '依頼文そのまま',                   # カタログの「依頼内容」に表示
    'agent': 'Claude Code',                        # または 'Codex' など
    'spec': 'ARR-SPEC などの設計メモ（任意）',
    'categories': [                                # 各 Cue.category はここの id
        {'id': 'summary', 'label': 'まとめ用BGM', 'note': '差し替え先: bgm/summer_triangle.mp3'},
    ],
    'series': [                                    # 任意。Cue.series に使う id
        {'id': 'retro', 'label': 'レトロ版'}, {'id': 'free', 'label': 'ジャンル自由'},
    ],
}
```

## Cue（1曲・1音）

| 引数 | 説明 |
|---|---|
| `id` | バッチ内で一意。英小文字・数字・`_`・`-`（例 `summary_retro_03`） |
| `title` / `category` | 曲名 / BATCH の categories の id |
| `notes` | `Note` のリスト |
| `bpm` / `meter` | テンポ（None = テンポなしSE）/ 拍子 `'4/4'` `'3/4'` `'6/8'` `'5/4'` など |
| `length` | 拍単位の長さ。**ループ曲は必須で小節の倍数**。SEは省略可（最後の音の終わり＋0.05秒） |
| `loop` | ループ曲なら True |
| `series` `mood` `style` `description` `tags` | カタログの表示・絞り込み用 |
| `mix` | `{'Harmony': -12}` のようにパートごとの音量（dB）。省略時は役割ごとの既定値 |
| `roles` | `{'Lead2': 'arp'}` のようにパートの役割を明示（lead/bass/pad/arp/drum）。省略時はパート名から推定 |

## Note（1音）

`Note(part, start, dur, pitch, vel=100, voice='pulse', pan=0.0, glide=0.0)`

- `part`：パート名。**役割の違う音は別パートにする**（メロディー／伴奏／ベース／各打楽器）。REAPER版では1パート＝1トラック。
  - 役割の推定：`kick snare hat tom clap noise perc drum` → drum、`bass` → bass、`harmony pad chord string comp` → pad、`arp` → arp、それ以外 → lead
- `pitch`：MIDIノート番号（60 = C4）。`vel`：1〜127。`pan`：-1（左）〜1（右）。
- `glide`：音の長さ全体で滑る半音数（例 `-12` = 1オクターブ下降）。MIDIではピッチベンド（幅±12または±24）になる。
- 同じパート・同じ音高で重なる音は、前の音が自動で短縮される（MIDIで区別できないため）。

## voice（プレビューの音色）

`pulse`(25%) `pulse12`(12.5%) `square` `triangle` `saw` `brass` `bass` `fm` `ep` `piano`
`bell` `chipbell` `glass` `vibes` `marimba` `pluck` `chippluck` `guitar` `clav` `wood`
`flute` `chipflute` `organ` `pad` `strings` `softchip` `chirp` `boing` `bubble` `metal` `ring`
打楽器：`kick` `snare` `hat` `tom` `clap` `noise`

プレビューは簡易シンセによる近似。REAPER版では音源プロファイルが役割と voice から音色を作り直す。

## Scale（音階の補助）

```python
key = Scale(62, 'major')        # 根音D4。major minor dorian phrygian lydian mixolydian harmonic_minor pentatonic minor_pentatonic
key.note(0)                     # 主音 62
key.note(4, octave=1)           # 5度上をオクターブ上で
key.chord(3, octave=-1)         # IV の三和音（1オクターブ下）
key.chord(0, size=4)            # 四和音
```

## 例

`examples/demo_batch/compose.py`（`python python/cli.py new-batch demo --example` でコピーされる）を参照。
