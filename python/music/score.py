"""楽曲データ（スコア）の正式な形式。

作曲スクリプト（library/<batch>/compose.py）はこのモジュールの Cue / Note / Scale を使って
音符イベントを定義する。時間はすべて「拍（四分音符 = 1）」で表す。
テンポを持たないSEは bpm=None とし、作業用の120 BPMグリッド（1拍 = 0.5秒）で扱う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import pairwise

WORKING_BPM = 120
PPQ = 960

MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
}

# プレビュー用シンセ（synth.py）が発音できる音色。REAPER版では音源プロファイルが役割ごとに音色を作り直す。
VOICES = {
    "pulse",
    "pulse12",
    "square",
    "triangle",
    "saw",
    "brass",
    "bass",
    "fm",
    "ep",
    "piano",
    "bell",
    "chipbell",
    "glass",
    "vibes",
    "marimba",
    "pluck",
    "chippluck",
    "guitar",
    "clav",
    "wood",
    "flute",
    "chipflute",
    "organ",
    "pad",
    "strings",
    "softchip",
    "chirp",
    "boing",
    "bubble",
    "metal",
    "ring",
    "kick",
    "snare",
    "hat",
    "tom",
    "clap",
    "noise",
}

# パート名から役割を推定する。役割はミックスの既定値とREAPER音源プロファイルの音作りに使う。
ROLE_PATTERNS = [
    ("drum", r"kick|snare|hat|tom|clap|noise|perc|drum|cymbal|shaker"),
    ("bass", r"bass"),
    ("pad", r"harmony|pad|chord|string|comp"),
    ("arp", r"arp"),
]
ROLES = ("lead", "bass", "pad", "arp", "drum")

# 役割ごとの既定ミックス（dB）。Cue.mix でパート単位に上書きできる。
DEFAULT_MIX_DB = {
    "lead": 0.0,
    "bass": -2.0,
    "arp": -7.0,
    "pad": -11.0,
    "drum": -6.0,
}
DEFAULT_DRUM_MIX_DB = {
    "kick": -3.0,
    "snare": -9.0,
    "hat": -16.0,
    "clap": -9.0,
    "tom": -6.0,
    "noise": -12.0,
}

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")


class ScoreError(ValueError):
    """Raised when score data violates the supported music-data contract."""


def role_of(part: str) -> str:
    """Infer an arrangement role from a part name.

    Args:
        part: User-defined part name.

    Returns:
        str: One of the supported roles, defaulting to ``lead``.
    """
    low = part.lower()
    for role, pattern in ROLE_PATTERNS:
        if re.search(pattern, low):
            return role
    return "lead"


def parse_meter(meter: str) -> tuple[int, int]:
    """Parse and validate a time-signature string.

    Args:
        meter: Signature such as ``"4/4"`` or ``"6/8"``.

    Returns:
        tuple[int, int]: Numerator and denominator.

    Raises:
        ScoreError: If the signature is not supported.
    """
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", meter or "")
    if not m:
        raise ScoreError(
            f'拍子の形式が不正です: {meter!r}（例: "4/4", "6/8"）'
        )
    num, den = int(m.group(1)), int(m.group(2))
    if num < 1 or den not in (1, 2, 4, 8, 16, 32):
        raise ScoreError(f"拍子の値が不正です: {meter!r}")
    return num, den


def beats_per_bar(meter: str) -> float:
    """Calculate quarter-note beats in one bar.

    Args:
        meter: Valid time-signature string.

    Returns:
        float: Length of one bar in the score's beat unit.
    """
    num, den = parse_meter(meter)
    return num * 4 / den


@dataclass
class Note:
    """Represent one note event in beat-based score time.

    Args:
        part: Part that owns the note.
        start: Start time in quarter-note beats.
        dur: Duration in quarter-note beats.
        pitch: MIDI pitch from 0 through 127.
        vel: MIDI velocity from 1 through 127.
        voice: Preview-synth voice name.
        pan: Stereo position from -1.0 (left) through 1.0 (right).
        glide: Pitch bend in semitones over the note duration.
    """

    part: str
    start: float
    dur: float
    pitch: int
    vel: int = 100
    voice: str = "pulse"
    pan: float = 0.0
    glide: float = 0.0

    def to_dict(self) -> dict:
        """Serialize the note for JSON event data.

        Returns:
            dict: JSON-compatible note fields.
        """
        return {
            "part": self.part,
            "start": self.start,
            "dur": self.dur,
            "pitch": self.pitch,
            "vel": self.vel,
            "voice": self.voice,
            "pan": self.pan,
            "glide": self.glide,
        }


@dataclass
class Cue:
    """Represent one music cue or sound effect.

    Args:
        id: Unique lowercase identifier within a batch.
        title: Display title.
        category: ID from ``BATCH['categories']``.
        notes: Note events in beat-based time.
        bpm: Tempo, or ``None`` for a one-shot effect.
        meter: Time signature string.
        length: Explicit length in beats; required for loops.
        loop: Whether the cue must loop at the length boundary.
        series: Optional catalog series name.
        mood: Optional mood label.
        style: Optional musical style label.
        description: Optional catalog description.
        tags: Optional searchable catalog tags.
        mix: Per-part mix level in decibels.
        roles: Per-part arrangement-role overrides.
    """

    id: str
    title: str
    category: str
    notes: list[Note] = field(default_factory=list)
    bpm: float | None = None
    meter: str = "4/4"
    length: float | None = None
    loop: bool = False
    series: str = ""
    mood: str = ""
    style: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    mix: dict[str, float] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)

    # ---- 時間の換算 -------------------------------------------------------
    @property
    def tempo(self) -> float:
        """Return the cue tempo, using the working tempo for one-shot effects.

        Returns:
            float: Beats per minute used for time conversion.
        """
        return float(self.bpm or WORKING_BPM)

    @property
    def beat_seconds(self) -> float:
        """Return the duration of one score beat.

        Returns:
            float: Seconds per quarter-note beat.
        """
        return 60.0 / self.tempo

    def seconds(self, beats: float) -> float:
        """Convert score beats to seconds at this cue's tempo.

        Args:
            beats: Duration in quarter-note beats.

        Returns:
            float: Equivalent duration in seconds.
        """
        return beats * self.beat_seconds

    def beats(self, seconds: float) -> float:
        """Convert seconds to score beats at this cue's tempo.

        Args:
            seconds: Duration in seconds.

        Returns:
            float: Equivalent duration in quarter-note beats.
        """
        return seconds / self.beat_seconds

    @property
    def bar_beats(self) -> float:
        """Return the score-beat length of one bar.

        Returns:
            float: Quarter-note beats per bar for the configured meter.
        """
        return beats_per_bar(self.meter)

    @property
    def length_beats(self) -> float:
        """Return the explicit or derived cue length in score beats.

        Returns:
            float: Configured loop length, or note end plus a short tail.
        """
        if self.length is not None:
            return float(self.length)
        end = max((n.start + n.dur for n in self.notes), default=1.0)
        return end + self.beats(0.05)

    @property
    def duration(self) -> float:
        """Return the cue duration in seconds.

        Returns:
            float: Converted ``length_beats`` at the effective tempo.
        """
        return self.seconds(self.length_beats)

    # ---- パート情報 ---------------------------------------------------------
    @property
    def parts(self) -> list[str]:
        """Return part names in first-note order.

        Returns:
            list[str]: Unique names of parts represented by the cue notes.
        """
        return list(dict.fromkeys(n.part for n in self.notes))

    def role(self, part: str) -> str:
        """Return the configured or inferred role for a part.

        Args:
            part: Part name to resolve.

        Returns:
            str: Configured role, or a role inferred from the part name.
        """
        return self.roles.get(part) or role_of(part)

    def mix_db(self, part: str) -> float:
        """Return the configured or default mix level for a part.

        Args:
            part: Part name to resolve.

        Returns:
            float: Mix gain in decibels.
        """
        if part in self.mix:
            return float(self.mix[part])
        role = self.role(part)
        if role == "drum":
            low = part.lower()
            for key, db in DEFAULT_DRUM_MIX_DB.items():
                if key in low:
                    return db
        return DEFAULT_MIX_DB[role]

    # ---- 検証・正規化 -------------------------------------------------------
    def validate(self) -> list[str]:
        """Validate the cue and normalize overlapping same-pitch notes.

        Returns:
            list[str]: Descriptions of automatic overlap corrections.

        Raises:
            ScoreError: If metadata or note values are invalid.
        """
        where = f"[{self.id}]"
        if not ID_PATTERN.match(self.id or ""):
            raise ScoreError(
                f"{where} id は英小文字・数字・_・- で指定してください"
            )
        if not self.title:
            raise ScoreError(f"{where} title が空です")
        if not self.notes:
            raise ScoreError(f"{where} 音符がありません")
        parse_meter(self.meter)
        if self.bpm is not None and not (20 <= self.bpm <= 400):
            raise ScoreError(f"{where} bpm が範囲外です: {self.bpm}")
        if self.loop:
            if self.bpm is None:
                raise ScoreError(f"{where} ループ曲には bpm が必要です")
            if self.length is None:
                raise ScoreError(
                    f"{where} ループ曲には length（拍）が必要です"
                )
            bars = self.length / self.bar_beats
            if abs(bars - round(bars)) > 1e-6:
                raise ScoreError(
                    f"{where} ループ長 {self.length} 拍が小節境界（{self.bar_beats} 拍単位）に揃っていません"
                )
        for role in self.roles.values():
            if role not in ROLES:
                raise ScoreError(
                    f"{where} 未知の役割 {role!r}（{', '.join(ROLES)}）"
                )
        length = self.length_beats
        for i, n in enumerate(self.notes):
            at = f"{where} notes[{i}] ({n.part})"
            if not n.part or not isinstance(n.part, str):
                raise ScoreError(f"{at} part が空です")
            if not (0 <= int(n.pitch) <= 127):
                raise ScoreError(f"{at} pitch が0〜127の範囲外です: {n.pitch}")
            if n.start < 0:
                raise ScoreError(f"{at} start が負です: {n.start}")
            if n.dur <= 0:
                raise ScoreError(f"{at} dur は正の値にしてください: {n.dur}")
            if n.start >= length:
                raise ScoreError(
                    f"{at} start {n.start} が曲の長さ {length} 拍を超えています"
                )
            if not (1 <= int(n.vel) <= 127):
                raise ScoreError(f"{at} vel が1〜127の範囲外です: {n.vel}")
            if n.voice not in VOICES:
                raise ScoreError(f"{at} 未知の voice {n.voice!r}")
            if not (-1 <= n.pan <= 1):
                raise ScoreError(
                    f"{at} pan は -1〜1 で指定してください: {n.pan}"
                )
            if abs(n.glide) > 24:
                raise ScoreError(
                    f"{at} glide は ±24 半音以内にしてください: {n.glide}"
                )
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
            for a, b in pairwise(notes):
                if a.start + a.dur > b.start:
                    if b.start - a.start < tick:
                        raise ScoreError(
                            f"[{self.id}] {part} の音高 {pitch} が同時刻 {a.start} 拍に重複しています"
                        )
                    a.dur = b.start - a.start
                    fixes.append(
                        f"{part} pitch={pitch} @ {a.start:g} 拍: 次の同音と重なるため {a.dur:g} 拍に短縮"
                    )
        return fixes

    def to_dict(self) -> dict:
        """Serialize the cue and its notes for generated event data.

        Returns:
            dict: JSON-compatible cue data including derived timing and parts.
        """
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "series": self.series,
            "mood": self.mood,
            "style": self.style,
            "description": self.description,
            "tags": list(self.tags),
            "bpm": self.bpm,
            "tempo": self.tempo,
            "meter": self.meter,
            "length_beats": self.length_beats,
            "duration": self.duration,
            "loop": self.loop,
            "parts": [
                {
                    "name": p,
                    "role": self.role(p),
                    "mix_db": self.mix_db(p),
                    "voices": list(
                        dict.fromkeys(
                            n.voice for n in self.notes if n.part == p
                        )
                    ),
                }
                for p in self.parts
            ],
            "notes": [n.to_dict() for n in self.notes],
        }


def cue_from_dict(d: dict) -> Cue:
    """Recreate a cue from serialized event data.

    Args:
        d: JSON-compatible cue dictionary.

    Returns:
        Cue: Reconstructed cue with notes, part roles, and mix settings.
    """
    parts = d.get("parts") or []
    return Cue(
        id=d["id"],
        title=d["title"],
        category=d["category"],
        notes=[Note(**n) for n in d["notes"]],
        bpm=d.get("bpm"),
        meter=d.get("meter") or "4/4",
        length=d.get("length_beats"),
        loop=bool(d.get("loop")),
        series=d.get("series", ""),
        mood=d.get("mood", ""),
        style=d.get("style", ""),
        description=d.get("description", ""),
        tags=list(d.get("tags", [])),
        mix={p["name"]: p["mix_db"] for p in parts},
        roles={p["name"]: p["role"] for p in parts},
    )


class Scale:
    """Map scale degrees to MIDI pitches for a root and mode.

    Args:
        root: MIDI pitch used as the scale root.
        mode: Name of a supported scale mode.

    >>> s = Scale(60, 'major')
    >>> s.note(0), s.note(4), s.note(7), s.note(-1)
    (60, 67, 72, 59)
    >>> s.chord(0)
    [60, 64, 67]
    """

    def __init__(self, root: int, mode: str = "major"):
        if mode not in MODES:
            raise ScoreError(f"未知の音階 {mode!r}（{', '.join(MODES)}）")
        self.root = root
        self.mode = mode
        self.steps = MODES[mode]

    def note(self, degree: int, octave: int = 0) -> int:
        """Return the MIDI pitch at a scale degree.

        Args:
            degree: Zero-based scale degree; values may cross octaves.
            octave: Additional octave offset.

        Returns:
            int: MIDI pitch for the requested scale position.
        """
        size = len(self.steps)
        return (
            self.root
            + self.steps[degree % size]
            + 12 * (degree // size + octave)
        )

    def chord(
        self, degree: int, size: int = 3, octave: int = 0, spread: int = 2
    ) -> list[int]:
        """Build a chord by stacking scale intervals.

        Args:
            degree: Root scale degree.
            size: Number of pitches to include.
            octave: Additional octave offset.
            spread: Scale-degree distance between chord tones.

        Returns:
            list[int]: MIDI pitches from the chord root upward.
        """
        return [self.note(degree + spread * k, octave) for k in range(size)]
