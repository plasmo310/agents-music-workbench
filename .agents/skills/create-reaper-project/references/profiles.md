# 音源プロファイル

`python/reaper/lua/profiles/<名前>.lua`。既定は `reasynth`。試聴カタログの保存時の選択、`--profiles <名前>`、`config.json` の `profiles` で指定する（優先順：`--profiles` ＞ リスト ＞ config.json ＞ 既定）。

## 同梱

| 名前 | 音源 | 備考 |
|---|---|---|
| `magical8bit` | Magical 8bit Plug 2（YMCK、無料、任意） | パルス・三角波・ノイズ。滑音があるパートはベンド幅を自動設定 |
| `massive` | Native Instruments MASSIVE（任意） | MASSIVE X ではない。ベンド幅はホストから設定できない |
| `reasynth` | ReaSynth（REAPER標準、既定） | 追加音源なしで動く。ノイズ源がないため打楽器は近似 |

## 書き方

```lua
return {
  label = '表示名',
  plugin = 'VST3i: 製品名 (メーカー)',   -- REAPERのFX一覧に出る名前。TrackFX_AddByName に渡す
  gate_trim = 0.025,                      -- 音源のリリースと重ならないようゲートを短くする秒数
  gate_trim_drum = 0.01,
  track_gain = function(t) return 0.4 end, -- トラック音量の基準（パートの mix dB が掛かる）
  configure = function(p, t)
    -- t.part / t.role（lead bass pad arp drum）/ t.voice / t.voices / t.loop / t.bend_range / t.cue
    p.set('パラメーター名', 0.5)          -- 正規化値 0〜1
    p.option('パラメーター名', '表示文字列') -- 選択肢（値域を走査して一致する値を探す）
    p.number('パラメーター名', 0.002)     -- 表示される数値に最も近い値（単調増加するパラメーター）
    p.note('記録に残したい補足')
  end,
  bend = function(p, range) end,          -- 任意：ピッチベンド幅（半音）を設定
}
```

- 設定したパラメーターは `sound_settings.tsv` に記録され、保存→再読み込み後に表示値が一致するか検査される。
- パラメーター名・選択肢はプラグインのバージョンで変わる。新しい音源を追加するときは、REAPER で実際に挿入し、`reaper.TrackFX_GetParamName` / `TrackFX_GetFormattedParamValue` で名前と値を確認してから書く。推測で書かない。
- 役割ごとに音作りを変える（全パート同じプリセットにしない）。会話用BGMは持続音と中域を抑え、SEは立ち上がりと終止を優先する。
