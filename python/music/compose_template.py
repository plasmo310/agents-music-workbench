"""作曲バッチ。`python python/cli.py render <このフォルダ名>` でWAV・MIDI・一覧データを書き出す。

このファイルは雛形。BATCH の内容と cues() の中身を依頼に合わせて書き換える。
時間は拍（四分音符 = 1）。API は .agents/skills/compose-music/references/score-api.md を参照。
"""

from music import Cue, Note, Scale

BATCH = {
    "title": "新しい作曲バッチ",
    "description": "このバッチの狙い（用途・雰囲気・候補の作り分け方）を1〜2文で。",
    "request": "依頼文をそのまま記録する",
    "agent": "",  # 'Claude Code' / 'Codex' など
    "spec": "",  # ARR-SPEC などの設計メモの要約（任意）
    "categories": [
        {"id": "bgm", "label": "BGM", "note": "用途・差し替え先など"},
        {"id": "se", "label": "効果音", "note": ""},
    ],
    "series": [],  # 例: [{'id': 'retro', 'label': 'レトロ版'}]
}


def loop_bgm() -> Cue:
    key = Scale(60, "major")
    bpm, bars = 112, 8
    notes: list[Note] = []
    progression = [0, 5, 3, 4]  # I - vi - IV - V
    motif = [
        (0, 1, 2),
        (1, 0.5, 4),
        (1.5, 0.5, 5),
        (2, 2, 4),
    ]  # (拍, 長さ, 度数)
    for bar in range(bars):
        at = bar * 4
        degree = progression[bar % 4]
        for pitch in key.chord(degree, octave=-1):
            notes.append(Note("Harmony", at, 3.8, pitch, 70, "pad", pan=-0.2))
        notes.append(Note("Bass", at, 1.8, key.note(degree, -2), 100, "bass"))
        notes.append(
            Note("Bass", at + 2, 1.8, key.note(degree + 4, -2), 90, "bass")
        )
        for beat, length, step in motif:
            answer = 2 if bar % 2 else 0  # 2小節目は応答として音域をずらす
            notes.append(
                Note(
                    "Melody",
                    at + beat,
                    length * 0.9,
                    key.note(step + degree % 2 + answer),
                    100,
                    "pulse",
                    pan=0.1,
                )
            )
        notes.append(Note("Kick", at, 0.25, 36, 110, "kick"))
        notes.append(Note("Kick", at + 2, 0.25, 36, 90, "kick"))
        notes.append(Note("Snare", at + 1, 0.2, 50, 90, "snare"))
        notes.append(Note("Snare", at + 3, 0.2, 50, 90, "snare"))
    return Cue(
        id="bgm_01",
        title="雛形のループBGM",
        category="bgm",
        bpm=bpm,
        meter="4/4",
        length=bars * 4,
        loop=True,
        mood="明るい",
        style="pop",
        notes=notes,
    )


def one_shot_se() -> Cue:
    cue = Cue(
        id="se_01",
        title="雛形の上昇SE",
        category="se",
        mood="喜び",
        style="arpeggio",
    )
    for k, pitch in enumerate([72, 76, 79, 84]):
        cue.notes.append(
            Note(
                "Lead",
                cue.beats(k * 0.06),
                cue.beats(0.12),
                pitch,
                100,
                "square",
            )
        )
    return cue


def cues() -> list[Cue]:
    return [loop_bgm(), one_shot_se()]
