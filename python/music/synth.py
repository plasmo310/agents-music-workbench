"""試聴用プレビューの簡易シンセ（numpy）。

HTMLで聴き比べるためのWAVを作る。音色は近似で、REAPER版では音源プロファイルが改めて音作りをする。
ループ曲は曲末尾からはみ出た音と短いディレイを先頭へ回り込ませ、継ぎ目なく繰り返せるようにする。
"""
from __future__ import annotations

import hashlib
import math
import wave
import zlib
from pathlib import Path

import numpy as np

from music.score import Cue, Note

SR = 32000
LOOP_RMS, ONESHOT_RMS, PEAK_LIMIT = 0.11, 0.18, 0.83

# 音色ごとの出力差をおおまかに揃える係数
VOICE_LEVEL = {
    'pulse': .55, 'pulse12': .55, 'square': .45, 'saw': .42, 'brass': .42, 'triangle': .9, 'bass': .95,
    'softchip': .8, 'fm': .8, 'ep': .8, 'piano': 1.2, 'bell': .9, 'chipbell': .9, 'glass': .9,
    'vibes': .9, 'metal': .8, 'ring': .8, 'marimba': 1.0, 'pluck': 1.0, 'chippluck': 1.0,
    'guitar': 1.0, 'clav': .9, 'wood': 1.1, 'flute': .8, 'chipflute': .8, 'organ': .6,
    'pad': .6, 'strings': .6, 'chirp': .9, 'boing': .9, 'bubble': .9,
    'kick': 1.2, 'tom': 1.0, 'snare': .9, 'clap': .9, 'hat': .7, 'noise': .7,
}


def _phase(f: float, t: np.ndarray, d: float, glide: float) -> np.ndarray:
    if not glide:
        return 2 * np.pi * f * t
    k = glide / 12 / max(d, 1e-6)  # 1秒あたりのオクターブ変化
    return 2 * np.pi * f * np.expm1(k * math.log(2) * t) / (k * math.log(2))


def voice_wave(n: Note, d: float, rng: np.random.Generator) -> np.ndarray:
    """1音分の波形（エンベロープ込み、振幅は音色基準）。d は秒。"""
    v = n.voice
    t = np.arange(max(2, round(d * SR))) / SR
    f = 440 * 2 ** ((n.pitch - 69) / 12)
    glide = n.glide or {'chirp': 7, 'boing': -9, 'bubble': -14}.get(v, 0)
    ph = _phase(f, t, d, glide)
    nyq = SR / 2
    if v in ('pulse', 'pulse12', 'square'):
        duty = {'pulse': .25, 'pulse12': .125, 'square': .5}[v]
        y = sum(np.sin(ph * k) * np.sin(np.pi * k * duty) / k for k in range(1, max(2, min(24, int(nyq / f)))))
    elif v in ('saw', 'brass'):
        y = sum(np.sin(ph * k) / k for k in range(1, max(2, min(16, int(nyq / f)))))
        if v == 'brass':
            y = y * np.minimum(1, t / .03)
    elif v in ('triangle', 'softchip', 'bass'):
        y = sum(((-1) ** ((k - 1) // 2)) * np.sin(ph * k) / k ** 2 for k in (1, 3, 5, 7))
    elif v == 'piano':
        y = sum(np.sin(ph * k * (1 + .00006 * k * k)) * np.exp(-t * (.9 + k * .35)) / (k ** 1.7) for k in range(1, 7))
    elif v in ('fm', 'ep'):
        y = np.sin(ph + (1.5 if v == 'fm' else 2.2) * np.sin(ph * 2) * np.exp(-t * 5)) * np.exp(-t * 2)
    elif v in ('bell', 'chipbell', 'glass', 'vibes', 'metal', 'ring'):
        ratios = [1, 2.756, 5.4] if v in ('metal', 'glass', 'ring') else [1, 2 if v == 'chipbell' else 3, 6.02]
        y = sum(np.sin(ph * r) * np.exp(-t * (3 + j * 4)) * g for j, (r, g) in enumerate(zip(ratios, [1, .3, .1])))
    elif v in ('guitar', 'pluck', 'chippluck', 'clav', 'marimba', 'wood', 'chirp', 'boing', 'bubble'):
        decay = {'wood': 28, 'clav': 9, 'marimba': 9}.get(v, 5)
        y = (np.sin(ph) + .4 * np.sin(ph * 2) * np.exp(-t * 10) + .22 * np.sin(ph * 3) * np.exp(-t * 17)) * np.exp(-t * decay)
    elif v in ('flute', 'chipflute'):
        y = np.sin(ph + .017 * np.sin(2 * np.pi * 4.6 * t)) + .1 * np.sin(ph * 2)
    elif v == 'organ':
        y = np.sin(ph) + .4 * np.sin(ph * 2) + .2 * np.sin(ph * 4)
    elif v in ('pad', 'strings'):
        y = (np.sin(ph) + .3 * np.sin(ph * 1.003) + .15 * np.sin(ph * 2)) * .8
    elif v in ('kick', 'tom'):
        base = 48 if v == 'kick' else f
        y = np.sin(2 * np.pi * (base * t + 3 * (1 - np.exp(-t * 38)))) * np.exp(-t * 25)
    else:  # snare / clap / hat / noise
        noise = rng.uniform(-1, 1, len(t))
        if v == 'hat':
            noise = np.r_[0, np.diff(noise)]
        tone = np.sin(ph) * .3 if v == 'snare' else 0
        y = (noise * .8 + tone) * np.exp(-t * {'hat': 75, 'clap': 33, 'snare': 26, 'noise': 12}[v])
    attack = .08 if v in ('pad', 'strings', 'softchip') else .0015 if d < .3 else .006
    release = min(.2 if v in ('pad', 'strings') else .065, d * .35)
    env = np.minimum(1, t / attack) * np.minimum(1, np.maximum(0, (d - t) / max(release, 1e-4)))
    return (y * env * VOICE_LEVEL[v]).astype(np.float32)


def render_cue(cue: Cue) -> np.ndarray:
    """Cue をステレオ float32 配列に合成して正規化する。"""
    n_samples = max(2, round(cue.duration * SR))
    buf = np.zeros((n_samples, 2), np.float32)
    rng = np.random.default_rng(zlib.crc32(cue.id.encode()))
    for n in cue.notes:
        gain = (n.vel / 127) ** 1.5 * 10 ** (cue.mix_db(n.part) / 20) * .2
        y = voice_wave(n, cue.seconds(n.dur), rng) * gain
        st = y[:, None] * np.array([math.sqrt((1 - n.pan) / 2), math.sqrt((1 + n.pan) / 2)], np.float32)
        start = round(cue.seconds(n.start) * SR)
        if cue.loop:
            np.add.at(buf, (start + np.arange(len(y))) % n_samples, st)
        else:
            end = min(n_samples, start + len(y))
            buf[start:end] += st[:end - start]
    if cue.loop:
        dry = buf.copy()
        for delay, g in [(.079, .07), (.137, .05), (.233, .035), (.367, .02)]:
            buf += np.roll(dry[:, ::-1], round(delay * SR), axis=0) * g
    buf -= buf.mean(axis=0)
    rms = float(np.sqrt(np.mean(buf ** 2)))
    peak = float(np.max(np.abs(buf)))
    buf *= min((LOOP_RMS if cue.loop else ONESHOT_RMS) / max(rms, 1e-8), PEAK_LIMIT / max(peak, 1e-8))
    if cue.loop:
        ramp = min(128, n_samples)
        buf[-ramp:] += np.linspace(0, 1, ramp, dtype=np.float32)[:, None] * (buf[0] - buf[-1])
    else:
        fade = max(2, min(n_samples, round(SR * .008)))
        buf[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    return buf


def write_wav(path: Path, buf: np.ndarray) -> dict:
    """16-bit PCM で書き出し、検査用の統計を返す。"""
    pcm = np.round(np.clip(buf, -1, 1) * 32767).astype('<i2')
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    x = pcm.astype(np.float64) / 32768
    return dict(
        peak_db=round(20 * math.log10(max(float(np.max(np.abs(x))), 1e-9)), 2),
        rms_db=round(20 * math.log10(max(float(np.sqrt(np.mean(x * x))), 1e-9)), 2),
        sha256=hashlib.sha256(pcm.tobytes()).hexdigest(),
    )


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """16/24/32-bit PCM と 32-bit float WAV を読み、(-1..1 の配列, サンプルレート) を返す。"""
    raw = Path(path).read_bytes()
    if raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
        raise ValueError(f'WAVではありません: {path}')
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(raw):
        cid, size = raw[pos:pos + 4], int.from_bytes(raw[pos + 4:pos + 8], 'little')
        body = raw[pos + 8:pos + 8 + size]
        if cid == b'fmt ':
            fmt = body
        elif cid == b'data':
            data = body
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError(f'WAVの構造が不正です: {path}')
    tag, channels, rate = int.from_bytes(fmt[0:2], 'little'), int.from_bytes(fmt[2:4], 'little'), int.from_bytes(fmt[4:8], 'little')
    bits = int.from_bytes(fmt[14:16], 'little')
    if tag == 0xFFFE:
        tag = int.from_bytes(fmt[24:26], 'little')
    if tag == 3 and bits == 32:
        x = np.frombuffer(data, '<f4').astype(np.float64)
    elif tag == 3 and bits == 64:
        x = np.frombuffer(data, '<f8').astype(np.float64)
    elif bits == 16:
        x = np.frombuffer(data, '<i2') / 32768
    elif bits == 24:
        b = np.frombuffer(data[:len(data) // 3 * 3], np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(v >= 1 << 23, v - (1 << 24), v) / float(1 << 23)
    elif bits == 32:
        x = np.frombuffer(data, '<i4') / 2147483648
    else:
        raise ValueError(f'未対応のWAV形式です（{bits}bit, tag={tag}）: {path}')
    return x[:len(x) // channels * channels].reshape(-1, channels), rate
