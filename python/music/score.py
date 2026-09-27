"""楽曲データ（スコア）の正式な形式。

作曲スクリプト（library/<batch>/compose.py）はこのモジュールの Cue / Note / Scale を使って
音符イベントを定義する。時間はすべて「拍（四分音符 = 1）」で表す。
テンポを持たないSEは bpm=None とし、作業用の120 BPMグリッド（1拍 = 0.5秒）で扱う。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

WORKING_BPM = 120
PPQ = 960

MODES = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10],
    'phrygian': [0, 1, 3, 5, 7, 8, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11],
    'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'pentatonic': [0, 2, 4, 7, 9],
    'minor_pentatonic': [0, 3, 5, 7, 10],
}

# プレビュー用シンセ（synth.py）が発音できる音色。REAPER版では音源プロファイルが役割ごとに音色を作り直す。
VOICES = {
    'pulse', 'pulse12', 'square', 'triangle', 'saw', 'brass', 'bass', 'fm', 'ep', 'piano',
    'bell', 'chipbell', 'glass', 'vibes', 'marimba', 'pluck', 'chippluck', 'guitar', 'clav',
    'wood', 'flute', 'chipflute', 'organ', 'pad', 'strings', 'softchip', 'chirp', 'boing',
    'bubble', 'metal', 'ring', 'kick', 'snare', 'hat', 'tom', 'clap', 'noise',
}

# パート名から役割を推定する。役割はミックスの既定値とREAPER音源プロファイルの音作りに使う。
ROLE_PATTERNS = [
    ('drum', r'kick|snare|hat|tom|clap|noise|perc|drum|cymbal|shaker'),
    ('bass', r'bass'),
    ('pad', r'harmony|pad|chord|string|comp'),
    ('arp', r'arp'),
]
ROLES = ('lead', 'bass', 'pad', 'arp', 'drum')

# 役割ごとの既定ミックス（dB）。Cue.mix でパート単位に上書きできる。
DEFAULT_MIX_DB = {'lead': 0.0, 'bass': -2.0, 'arp': -7.0, 'pad': -11.0, 'drum': -6.0}
DEFAULT_DRUM_MIX_DB = {'kick': -3.0, 'snare': -9.0, 'hat': -16.0, 'clap': -9.0, 'tom': -6.0, 'noise': -12.0}

ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_\-]*$')


class ScoreError(ValueError):
    pass


def role_of(part: str) -> str:
    low = part.lower()
    for role, pattern in ROLE_PATTERNS:
        if re.search(pattern, low):
            return role
    return 'lead'


def parse_meter(meter: str) -> tuple[int, int]:
    m = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', meter or '')
    if not m:
        raise ScoreError(f'拍子の形式が不正です: {meter!r}（例: "4/4", "6/8"）')
    num, den = int(m.group(1)), int(m.group(2))
    if num < 1 or den not in (1, 2, 4, 8, 16, 32):
        raise ScoreError(f'拍子の値が不正です: {meter!r}')
    return num, den


def beats_per_bar(meter: str) -> float:
    num, den = parse_meter(meter)
    return num * 4 / den


@dataclass
class Note:
    """1つの音符。start / dur は拍単位。glide は音符の長さ全体で滑る半音数（例: -12 で1オクターブ下降）。"""
    part: str
    start: float
    dur: float
    pitch: int
    vel: int = 100
    voice: str = 'pulse'
    pan: float = 0.0
    glide: float = 0.0

    def to_dict(self) -> dict:
        return dict(part=self.part, start=self.start, dur=self.dur, pitch=self.pitch, vel=self.vel,
                    voice=self.voice, pan=self.pan, glide=self.glide)


@dataclass
class Cue:
    """1つの曲・効果音。

    id        : バッチ内で一意（英小文字・数字・_ -）
    category  : BATCH['categories'] の id
    length    : 拍単位の長さ。ループ曲は必須（小節境界に揃える）。SEは省略すると最後の音の終わり＋余韻。
    bpm       : None ならテンポ未定義のSE（作業用120 BPM）
    mix       : パート名 -> dB。省略時は役割ごとの既定値
    roles     : パート名 -> 役割（lead/bass/pad/arp/drum）。省略時はパート名から推定
    """
    id: str
    title: str
    category: str
    notes: list[Note] = field(default_factory=list)
    bpm: float | None = None
    meter: str = '4/4'
    length: float | None = None
    loop: bool = False
    series: str = ''
    mood: str = ''
    style: str = ''
    description: str = ''
    tags: list[str] = field(default_factory=list)
    mix: dict[str, float] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)

    # ---- 時間の換算 -------------------------------------------------------
    @property
    def tempo(self) -> float:
        return float(self.bpm or WORKING_BPM)

    @property
    def beat_seconds(self) -> float:
        return 60.0 / self.tempo

    def seconds(self, beats: float) -> float:
        return beats * self.beat_seconds

    def beats(self, seconds: float) -> float:
        """秒 -> 拍。テンポ未定義のSEで秒単位の設計をしたい場合に使う。"""
        return seconds / self.beat_seconds

    @property
    def bar_beats(self) -> float:
        return beats_per_bar(self.meter)

    @property
    def length_beats(self) -> float:
        if self.length is not None:
            return float(self.length)
        end = max((n.start + n.dur for n in self.notes), default=1.0)
        return end + self.beats(0.05)

    @property
    def duration(self) -> float:
        return self.seconds(self.length_beats)

    # ---- パート情報 ---------------------------------------------------------
    @property
    def parts(self) -> list[str]:
        return list(dict.fromkeys(n.part for n in self.notes))

    def role(self, part: str) -> str:
        return self.roles.get(part) or role_of(part)

    def mix_db(self, part: str) -> float:
        if part in self.mix:
            return float(self.mix[part])
        role = self.role(part)
        if role == 'drum':
            low = part.lower()
            for key, db in DEFAULT_DRUM_MIX_DB.items():
                if key in low:
                    return db
        return DEFAULT_MIX_DB[role]

    # ---- 検証・正規化 -------------------------------------------------------
    def validate(self) -> list[str]:
        """不正な値は ScoreError。自動修正した内容を文字列のリストで返す。"""
        where = f'[{self.id}]'
        if not ID_PATTERN.match(self.id or ''):
            raise ScoreError(f'{where} id は英小文字・数字・_・- で指定してください')
        if not self.title:
            raise ScoreError(f'{where} title が空です')
        if not self.notes:
            raise ScoreError(f'{where} 音符がありません')
        parse_meter(self.meter)
        if self.bpm is not None and not (20 <= self.bpm <= 400):
            raise ScoreError(f'{where} bpm が範囲外です: {self.bpm}')
        if self.loop:
            if self.bpm is None:
                raise ScoreError(f'{where} ループ曲には bpm が必要です')
            if self.length is None:
                raise ScoreError(f'{where} ループ曲には length（拍）が必要です')
            bars = self.length / self.bar_beats
            if abs(bars - round(bars)) > 1e-6:
                raise ScoreError(f'{where} ループ長 {self.length} 拍が小節境界（{self.bar_beats} 拍単位）に揃っていません')
        for role in self.roles.values():
            if role not in ROLES:
                raise ScoreError(f'{where} 未知の役割 {role!r}（{", ".join(ROLES)}）')
        length = self.length_beats
        for i, n in enumerate(self.notes):
            at = f'{where} notes[{i}] ({n.part})'
            if not n.part or not isinstance(n.part, str):
                raise ScoreError(f'{at} part が空です')
            if not (0 <= int(n.pitch) <= 127):
                raise ScoreError(f'{at} pitch が0〜127の範囲外です: {n.pitch}')
            if n.start < 0:
                raise ScoreError(f'{at} start が負です: {n.start}')
            if n.dur <= 0:
                raise ScoreError(f'{at} dur は正の値にしてください: {n.dur}')
            if n.start >= length:
                raise ScoreError(f'{at} start {n.start} が曲の長さ {length} 拍を超えています')
            if not (1 <= int(n.vel) <= 127):
                raise ScoreError(f'{at} vel が1〜127の範囲外です: {n.vel}')
            if n.voice not in VOICES:
                raise ScoreError(f'{at} 未知の voice {n.voice!r}')
            if not (-1 <= n.pan <= 1):
                raise ScoreError(f'{at} pan は -1〜1 で指定してください: {n.pan}')
            if abs(n.glide) > 24:
                raise ScoreError(f'{at} glide は ±24 半音以内にしてください: {n.glide}')
            n.pitch, n.vel = int(n.pitch), int(n.vel)
        return self._trim_overlaps()

    def _trim_overlaps(self) -> list[str]:
        """同じパート・同じ音高で重なる音符は、MIDIで区別できないため前の音符を短くする。"""
        fixes = []
        groups: dict[tuple[str, int], list[Note]] = {}
        for n in self.notes:
            groups.setdefault((n.part, n.pitch), []).append(n)
        tick = 1 / PPQ
        for (part, pitch), notes in groups.items():
            notes.sort(key=lambda n: n.start)
            for a, b in zip(notes, notes[1:]):
                if a.start + a.dur > b.start:
                    if b.start - a.start < tick:
                        raise ScoreError(f'[{self.id}] {part} の音高 {pitch} が同時刻 {a.start} 拍に重複しています')
                    a.dur = b.start - a.start
                    fixes.append(f'{part} pitch={pitch} @ {a.start:g} 拍: 次の同音と重なるため {a.dur:g} 拍に短縮')
        return fixes

    def to_dict(self) -> dict:
        return dict(
            id=self.id, title=self.title, category=self.category, series=self.series, mood=self.mood,
            style=self.style, description=self.description, tags=list(self.tags),
            bpm=self.bpm, tempo=self.tempo, meter=self.meter, length_beats=self.length_beats,
            duration=self.duration, loop=self.loop,
            parts=[dict(name=p, role=self.role(p), mix_db=self.mix_db(p),
                        voices=list(dict.fromkeys(n.voice for n in self.notes if n.part == p)))
                   for p in self.parts],
            notes=[n.to_dict() for n in self.notes],
        )


def cue_from_dict(d: dict) -> Cue:
    parts = d.get('parts') or []
    return Cue(
        id=d['id'], title=d['title'], category=d['category'],
        notes=[Note(**n) for n in d['notes']], bpm=d.get('bpm'), meter=d.get('meter') or '4/4',
        length=d.get('length_beats'), loop=bool(d.get('loop')), series=d.get('series', ''),
        mood=d.get('mood', ''), style=d.get('style', ''), description=d.get('description', ''),
        tags=list(d.get('tags', [])),
        mix={p['name']: p['mix_db'] for p in parts}, roles={p['name']: p['role'] for p in parts},
    )


class Scale:
    """調と音階から音高を得る補助。degree は0始まりの音階度数（7以上・負値でオクターブをまたぐ）。

    >>> s = Scale(60, 'major')
    >>> s.note(0), s.note(4), s.note(7), s.note(-1)
    (60, 67, 72, 59)
    >>> s.chord(0)
    [60, 64, 67]
    """

    def __init__(self, root: int, mode: str = 'major'):
        if mode not in MODES:
            raise ScoreError(f'未知の音階 {mode!r}（{", ".join(MODES)}）')
        self.root = root
        self.mode = mode
        self.steps = MODES[mode]

    def note(self, degree: int, octave: int = 0) -> int:
        size = len(self.steps)
        return self.root + self.steps[degree % size] + 12 * (degree // size + octave)

    def chord(self, degree: int, size: int = 3, octave: int = 0, spread: int = 2) -> list[int]:
        """degree を根音に、音階上で spread 度ずつ積んだ和音（既定は三和音）。"""
        return [self.note(degree + spread * k, octave) for k in range(size)]
