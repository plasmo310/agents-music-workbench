"""見本の作曲バッチ：解説動画向けの短い素材3点。

試すには:
    python python/cli.py new-batch demo          # data/library/<日付>-demo/compose.py ができる
    （このファイルの内容で compose.py を置き換える）
    python python/cli.py render <日付>-demo
"""

from music import Cue, Note, Scale

BATCH = {
    "title": "見本：解説動画の素材",
    "description": "会話の後ろで流すBGMを拍子と編成を変えて2曲、ひらめきのSEを1点。",
    "request": "解説動画用に、会話を邪魔しない明るいBGMを2曲と、ひらめいた瞬間のSEを1つ作って",
    "agent": "見本",
    "spec": "BGM1: 4/4・104 BPM・I-vi-IV-V、パルスのリードと三角波ベース、4小節の問いと答え。\n"
    "BGM2: 3/4・96 BPM・ワルツ、ベルの分散和音、ドラムなし。\n"
    "SE: 上昇する3音＋滑音で終わる約0.5秒。",
    "categories": [
        {
            "id": "talk",
            "label": "会話BGM",
            "note": "ループ。台詞の帯域を空けるためリードは中音域に置く",
        },
        {"id": "idea", "label": "ひらめきSE", "note": "ワンショット"},
    ],
}


def workshop() -> Cue:
    key = Scale(62, "major")  # D major
    bars, notes = 8, []
    progression = [0, 5, 3, 4]
    call = [(0, 0.75, 4), (1, 0.5, 2), (1.5, 0.5, 4), (2, 1.5, 5)]  # 問い
    answer = [
        (0, 0.75, 4),
        (1, 0.5, 3),
        (1.5, 0.5, 2),
        (2, 1.5, 0),
    ]  # 答え（主音へ）
    for bar in range(bars):
        at = bar * 4
        degree = progression[bar % 4]
        for pitch in key.chord(degree, octave=-1):
            notes.append(Note("Harmony", at, 3.9, pitch, 64, "pad"))
        root = key.note(degree, -2)
        for beat, length, step in [
            (0, 0.9, 0),
            (1.5, 0.4, 0),
            (2, 0.9, 4),
            (3, 0.9, 0),
        ]:
            notes.append(
                Note(
                    "Bass",
                    at + beat,
                    length,
                    key.note(degree + step, -2) if step else root,
                    100,
                    "bass",
                )
            )
        phrase = call if bar % 2 == 0 else answer
        if bar % 4 == 3:
            phrase = [(0, 3.5, 0)]  # 4小節目は伸ばして区切る
        for beat, length, step in phrase:
            notes.append(
                Note(
                    "Melody",
                    at + beat,
                    length,
                    key.note(step),
                    96,
                    "pulse",
                    pan=0.1,
                )
            )
        for k in range(8):
            notes.append(
                Note(
                    "Arp",
                    at + k * 0.5,
                    0.3,
                    key.chord(degree, octave=1)[k % 3],
                    60,
                    "chippluck",
                    pan=-0.3,
                )
            )
        notes.append(Note("Kick", at, 0.25, 36, 110, "kick"))
        notes.append(Note("Kick", at + 2.5, 0.25, 36, 80, "kick"))
        notes.append(Note("Snare", at + 1, 0.2, 50, 90, "snare"))
        notes.append(Note("Snare", at + 3, 0.2, 50, 90, "snare"))
        for k in range(4):
            notes.append(
                Note("Hat", at + k + 0.5, 0.08, 80, 70, "hat", pan=0.3)
            )
    return Cue(
        id="talk_01",
        title="朝の作業場",
        category="talk",
        bpm=104,
        meter="4/4",
        length=bars * 4,
        loop=True,
        mood="明るい",
        style="chip pop",
        tags=["4/4", "ドラムあり"],
        notes=notes,
    )


def waltz() -> Cue:
    key = Scale(65, "major")  # F major
    bars, notes = 8, []
    progression = [0, 3, 4, 0, 5, 1, 4, 0]
    melody = [
        [(0, 2, 2), (2, 1, 4)],
        [(0, 3, 5)],
        [(0, 1, 4), (1, 1, 3), (2, 1, 1)],
        [(0, 3, 2)],
        [(0, 2, 0), (2, 1, 2)],
        [(0, 3, 3)],
        [(0, 1, 1), (1, 1, 2), (2, 1, 1)],
        [(0, 3, 0)],
    ]
    for bar in range(bars):
        at = bar * 3
        degree = progression[bar]
        notes.append(Note("Bass", at, 2.8, key.note(degree, -2), 96, "bass"))
        chord = key.chord(degree)
        for k, idx in enumerate([0, 1, 2, 1, 2, 1]):
            notes.append(
                Note(
                    "Arp",
                    at + k * 0.5,
                    0.45,
                    chord[idx],
                    62,
                    "bell",
                    pan=(-1) ** k * 0.25,
                )
            )
        for beat, length, step in melody[bar]:
            notes.append(
                Note(
                    "Melody",
                    at + beat,
                    length * 0.95,
                    key.note(step, 1),
                    90,
                    "flute",
                )
            )
    return Cue(
        id="talk_02",
        title="午後の三拍子",
        category="talk",
        bpm=96,
        meter="3/4",
        length=bars * 3,
        loop=True,
        mood="穏やか",
        style="waltz",
        tags=["3/4", "ドラムなし"],
        notes=notes,
    )


def spark() -> Cue:
    cue = Cue(
        id="idea_01",
        title="ピコーン",
        category="idea",
        mood="ひらめき",
        style="rising",
    )
    for k, pitch in enumerate([79, 84, 88]):
        cue.notes.append(
            Note(
                "Lead",
                cue.beats(k * 0.07),
                cue.beats(0.1),
                pitch,
                100,
                "square",
            )
        )
    cue.notes.append(
        Note(
            "Lead", cue.beats(0.21), cue.beats(0.3), 91, 110, "square", glide=5
        )
    )
    cue.notes.append(
        Note("Sparkle", cue.beats(0.21), cue.beats(0.35), 103, 70, "chipbell")
    )
    return cue


def cues() -> list[Cue]:
    return [workshop(), waltz(), spark()]
