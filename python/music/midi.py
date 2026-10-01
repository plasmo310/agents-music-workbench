"""Standard MIDI File（Type 1 / 960 PPQ）の書き出しと検証用の読み込み。"""

from __future__ import annotations

import struct
from pathlib import Path

from music.score import PPQ, Cue, parse_meter


def _vlq(n: int) -> bytes:
    out = [n & 127]
    n >>= 7
    while n:
        out.insert(0, 128 | (n & 127))
        n >>= 7
    return bytes(out)


def _chunk(events: list[tuple[int, int, bytes]]) -> bytes:
    # 同時刻では note-off を note-on より先に置く（同音の連打が正しく切れるように）
    events.sort(key=lambda e: (e[0], e[1]))
    out, last = b"", 0
    for at, _, msg in events:
        out += _vlq(at - last) + msg
        last = at
    out += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(out)) + out


def tick(beats: float) -> int:
    """Convert score beats to MIDI ticks.

    Args:
        beats: Duration or position in score beats.

    Returns:
        int: Rounded tick position at the configured PPQ.
    """
    return round(beats * PPQ)


def note_ticks(start: float, dur: float) -> tuple[int, int]:
    """Return non-empty start and end ticks for one note.

    Args:
        start: Note start in score beats.
        dur: Note duration in score beats.

    Returns:
        tuple[int, int]: Start tick and end tick.
    """
    at = tick(start)
    return at, max(at + 1, tick(start + dur))


def _channels():
    """パートごとのMIDIチャンネル。GMドラムと解釈されないよう ch10 は使わない。"""
    return [c for c in range(16) if c != 9]


def bend_range(cue: Cue, part: str) -> int:
    """Select the pitch-bend range required by a part's glides.

    Args:
        cue: Cue containing the part notes.
        part: Part name to inspect.

    Returns:
        int: ``0``, ``12``, or ``24`` semitones.
    """
    top = max((abs(n.glide) for n in cue.notes if n.part == part), default=0)
    return 0 if not top else 12 if top <= 12 else 24


def write_midi(cue: Cue, path: Path) -> None:
    """Write a cue as a Type 1 MIDI file.

    Args:
        cue: Validated score cue to export.
        path: Destination MIDI file path.
    """
    num, den = parse_meter(cue.meter)
    tempo = round(60_000_000 / cue.tempo)
    conductor = [
        (0, 1, b"\xff\x51\x03" + tempo.to_bytes(3, "big")),
        (0, 1, b"\xff\x58\x04" + bytes([num, den.bit_length() - 1, 24, 8])),
    ]
    name = cue.title.encode("utf-8")
    conductor.append((0, 0, b"\xff\x03" + _vlq(len(name)) + name))
    tracks = [_chunk(conductor)]
    for j, part in enumerate(cue.parts):
        ch = _channels()[j % 15]
        label = part.encode("utf-8")
        events = [(0, 0, b"\xff\x03" + _vlq(len(label)) + label)]
        rng = bend_range(cue, part)
        if rng:
            # RPN 0 でピッチベンド幅を指定し、音源側と一致させる
            for cc, val in (
                (101, 0),
                (100, 0),
                (6, rng),
                (38, 0),
                (101, 127),
                (100, 127),
            ):
                events.append((0, 1, bytes([0xB0 | ch, cc, val])))
        for n in cue.notes:
            if n.part != part:
                continue
            at, end = note_ticks(n.start, n.dur)
            events.append((at, 2, bytes([0x90 | ch, n.pitch, n.vel])))
            events.append((end, 0, bytes([0x80 | ch, n.pitch, 0])))
            if n.glide:
                steps = max(2, min(64, (end - at) // 30))
                for s in range(steps + 1):
                    value = 8192 + round(n.glide / rng * 8191 * s / steps)
                    value = max(0, min(16383, value))
                    events.append(
                        (
                            at + (end - at) * s // steps,
                            1,
                            bytes([0xE0 | ch, value & 127, value >> 7]),
                        )
                    )
                events.append((end, 1, bytes([0xE0 | ch, 0, 64])))
        tracks.append(_chunk(events))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"MThd"
        + struct.pack(">IHHH", 6, 1, len(tracks), PPQ)
        + b"".join(tracks)
    )


def read_midi_notes(path: Path) -> list[tuple[str, int, int, int, int]]:
    """Read note events from a Type 1 MIDI file.

    Args:
        path: MIDI file to parse.

    Returns:
        list[tuple[str, int, int, int, int]]: Track, pitch, start tick, end tick,
            and velocity for each note.

    Raises:
        ValueError: If the MIDI structure is unsupported or malformed.
    """
    raw = Path(path).read_bytes()
    if raw[:4] != b"MThd":
        raise ValueError("MIDIヘッダーがありません")
    _, fmt, ntracks, ppq = struct.unpack(">IHHH", raw[4:14])
    if fmt != 1 or ppq != PPQ:
        raise ValueError(
            f"Type 1 / {PPQ} PPQ ではありません（type={fmt}, ppq={ppq}）"
        )
    pos, notes = 14, []
    for _ in range(ntracks):
        if raw[pos : pos + 4] != b"MTrk":
            raise ValueError("MTrk チャンクが見つかりません")
        size = int.from_bytes(raw[pos + 4 : pos + 8], "big")
        pos += 8
        end, at, status, name, active, ended = pos + size, 0, 0, "", {}, False

        def vlq() -> int:
            nonlocal pos
            v = 0
            while True:
                b = raw[pos]
                pos += 1
                v = (v << 7) | (b & 127)
                if b < 128:
                    return v

        while pos < end:
            at += vlq()
            if raw[pos] & 0x80:
                status = raw[pos]
                pos += 1
            if status == 0xFF:
                kind = raw[pos]
                pos += 1
                length = vlq()
                if kind == 0x03:
                    name = raw[pos : pos + length].decode("utf-8", "replace")
                if kind == 0x2F:
                    ended = True
                pos += length
            elif status in (0xF0, 0xF7):
                pos += vlq()
            else:
                kind = status & 0xF0
                size_ = 1 if kind in (0xC0, 0xD0) else 2
                data = raw[pos : pos + size_]
                pos += size_
                if kind in (0x80, 0x90):
                    key = (status & 15, data[0])
                    if kind == 0x90 and data[1] > 0:
                        active.setdefault(key, []).append((at, data[1]))
                    else:
                        if not active.get(key):
                            raise ValueError(
                                f"対応する note-on のない note-off（{name}）"
                            )
                        start, vel = active[key].pop(0)
                        notes.append((name, data[0], start, at, vel))
        if any(active.values()):
            raise ValueError(f"鳴りっぱなしのノートがあります（{name}）")
        if not ended or pos != end:
            raise ValueError(f"トラック終端が不正です（{name}）")
    if pos != len(raw):
        raise ValueError("ファイル末尾に余分なデータがあります")
    return sorted(notes)


def expected_notes(cue: Cue) -> list[tuple[str, int, int, int, int]]:
    """Build expected readback events for a cue's exported MIDI.

    Args:
        cue: Cue used to generate the MIDI file.

    Returns:
        list[tuple[str, int, int, int, int]]: Normalized expected note events.
    """
    return sorted(
        (n.part, n.pitch, *note_ticks(n.start, n.dur), n.vel)
        for n in cue.notes
    )
