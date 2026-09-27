"""作曲バッチ（data/library/<batch_id>/compose.py）をWAV・MIDI・一覧データに書き出す。"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import settings

from music import midi, synth
from music.score import Cue, ScoreError

BATCH_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")
GENERATED = (
    "audio",
    "midi",
    "events.json",
    "manifest.json",
    "verification.json",
)


class BatchError(RuntimeError):
    pass


def batch_dir(batch_id: str) -> Path:
    if not BATCH_ID.match(batch_id):
        raise BatchError(
            f"バッチIDは英数字・_・- で指定してください: {batch_id!r}"
        )
    return settings.LIBRARY / batch_id


def new_batch(
    name: str, today: dt.date | None = None, example: bool = False
) -> Path:
    """テンプレート（example=True なら見本）から compose.py を作る。IDの先頭に日付を付ける。"""
    today = today or dt.datetime.now().astimezone().date()
    batch_id = name if re.match(r"^\d{8}-", name) else f"{today:%Y%m%d}-{name}"
    folder = batch_dir(batch_id)
    target = folder / "compose.py"
    if target.exists():
        raise BatchError(f"既に存在します: {settings.rel(target)}")
    folder.mkdir(parents=True, exist_ok=True)
    source = (
        settings.ROOT / "examples" / "demo_batch" / "compose.py"
        if example
        else settings.PYTHON_DIR / "music" / "compose_template.py"
    )
    shutil.copyfile(source, target)
    return target


def load_compose(folder: Path):
    path = folder / "compose.py"
    if not path.is_file():
        raise BatchError(f"compose.py がありません: {settings.rel(path)}")
    if str(settings.PYTHON_DIR) not in sys.path:
        sys.path.insert(0, str(settings.PYTHON_DIR))
    spec = importlib.util.spec_from_file_location(
        f"compose_{folder.name.replace('-', '_')}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    meta = getattr(module, "BATCH", None)
    make = getattr(module, "cues", None)
    if not isinstance(meta, dict) or not callable(make):
        raise BatchError(
            "compose.py には BATCH（dict）と cues() 関数が必要です"
        )
    cues = list(make())
    if not cues or not all(isinstance(c, Cue) for c in cues):
        raise BatchError("cues() は Cue のリストを返してください")
    return meta, cues


def _fingerprint(cue: Cue) -> tuple:
    """移調・テンポ違いだけの重複を見つけるための指紋（相対音高とリズム）。"""
    notes = sorted(cue.notes, key=lambda n: (n.start, n.part, n.pitch))
    base = notes[0].pitch
    return tuple(
        (
            round(n.start / cue.length_beats, 4),
            round(n.dur / cue.length_beats, 4),
            n.pitch - base,
        )
        for n in notes
    )


def render(batch_id: str, force: bool = False, log=print) -> dict:
    folder = batch_dir(batch_id)
    meta, cues = load_compose(folder)
    if (folder / "manifest.json").exists() and not force:
        raise BatchError(
            f"{batch_id} は書き出し済みです。作り直す場合は --force を付けてください（既存のWAV/MIDIは削除されます）"
        )

    ids = [c.id for c in cues]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise BatchError(f"id が重複しています: {', '.join(dupes)}")
    categories = meta.get("categories") or [
        {"id": c, "label": c} for c in dict.fromkeys(c.category for c in cues)
    ]
    known = {c["id"] for c in categories}
    fixes = {}
    for cue in cues:
        if cue.category not in known:
            raise ScoreError(
                f'[{cue.id}] category {cue.category!r} が BATCH["categories"] にありません'
            )
        fixed = cue.validate()
        if fixed:
            fixes[cue.id] = fixed

    for name in GENERATED:
        target = folder / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    batch_file = folder / "batch.json"
    created = (
        json.loads(batch_file.read_text(encoding="utf-8")).get("created")
        if batch_file.exists()
        else None
    )
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    info = {
        "id": batch_id,
        "title": meta.get("title") or batch_id,
        "description": meta.get("description", ""),
        "request": meta.get("request", ""),
        "agent": meta.get("agent", ""),
        "spec": meta.get("spec", ""),
        "categories": categories,
        "series": meta.get("series") or [],
        "created": created or now,
        "rendered": now,
        "count": len(cues),
    }

    rows, events, checks, failures = [], [], [], []
    hashes: dict[str, str] = {}
    prints: dict[tuple, str] = {}
    warnings = []
    for index, cue in enumerate(cues, 1):
        buf = synth.render_cue(cue)
        wav = Path("audio") / cue.category / f"{cue.id}.wav"
        stats = synth.write_wav(folder / wav, buf)
        mid = Path("midi") / f"{cue.id}.mid"
        midi.write_midi(cue, folder / mid)

        problems = []
        x, _ = synth.read_wav(folder / wav)
        rms = float(np.sqrt(np.mean(x * x)))
        if not np.isfinite(x).all() or rms < 0.001:
            problems.append("無音または不正なサンプル")
        if float(np.max(np.abs(x))) >= 0.99:
            problems.append("クリッピング")
        if cue.loop and float(np.max(np.abs(x[0] - x[-1]))) > 1e-3:
            problems.append("ループ端が不連続")
        if not cue.loop and float(np.max(np.abs(x[-1]))) > 1e-3:
            problems.append("SE終端が無音になっていない")
        if stats["sha256"] in hashes:
            problems.append(f"{hashes[stats['sha256']]} とPCMが同一")
        hashes[stats["sha256"]] = cue.id
        try:
            if midi.read_midi_notes(folder / mid) != midi.expected_notes(cue):
                problems.append("MIDIの音符が元データと一致しない")
        except ValueError as e:
            problems.append(f"MIDI構造: {e}")
        fp = _fingerprint(cue)
        if fp in prints:
            warnings.append(
                f"{cue.id} は {prints[fp]} と移調・テンポ違いだけの可能性があります"
            )
        prints.setdefault(fp, cue.id)
        for p in problems:
            failures.append(f"{cue.id}: {p}")

        data = cue.to_dict()
        events.append(data)
        row = {k: v for k, v in data.items() if k != "notes"}
        row.update(
            index=index,
            batch=batch_id,
            key=f"{batch_id}/{cue.id}",
            path=wav.as_posix(),
            midi=mid.as_posix(),
            note_count=len(cue.notes),
            **stats,
        )
        rows.append(row)
        log(
            f"  {cue.id}: {cue.duration:.2f}秒 / {len(cue.notes)}音 / {len(cue.parts)}パート"
            + (f"  ⚠ {', '.join(problems)}" if problems else "")
        )

    checks = [
        f"{len(cues)} 件のWAV（{synth.SR} Hz / 16-bit / ステレオ）とType 1 MIDIを書き出し",
        "無音・クリッピング・PCM重複・ループ端・SE終端・MIDI往復一致を検査",
    ]
    report = {
        "batch": batch_id,
        "ok": not failures,
        "count": len(cues),
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "auto_fixes": fixes,
        "listening": "エージェントによる聴取評価は未実施",
    }
    dump = lambda p, d: (folder / p).write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    dump("batch.json", info)
    dump("manifest.json", rows)
    (folder / "events.json").write_text(
        json.dumps({"batch": batch_id, "cues": events}, ensure_ascii=False),
        encoding="utf-8",
    )
    dump("verification.json", report)
    return report


def import_audio(
    batch_id: str, meta: dict, entries: list[dict], log=print
) -> dict:
    """既存の音声（と音符データ）を、書き出し済みバッチと同じ形式で library に登録する。

    entries: [{'cue': Cue, 'audio': Path}]。音符データがない音声は cue.notes を空にする（has_score=False、
    カタログでは試聴のみでプロジェクト生成リストには入れられない）。音声は再合成せずにコピーする。
    """
    folder = batch_dir(batch_id)
    if (folder / "manifest.json").exists():
        raise BatchError(f"{batch_id} は登録済みです")
    folder.mkdir(parents=True, exist_ok=True)
    rows, events, failures, fixes = [], [], [], {}
    for index, entry in enumerate(entries, 1):
        cue, src = entry["cue"], Path(entry["audio"])
        has_score = bool(cue.notes)
        if has_score:
            fixed = cue.validate()
            if fixed:
                fixes[cue.id] = fixed
        wav = Path("audio") / cue.category / f"{cue.id}{src.suffix.lower()}"
        (folder / wav).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, folder / wav)
        x, rate = synth.read_wav(folder / wav)
        stats = {
            "peak_db": round(
                20 * np.log10(max(float(np.max(np.abs(x))), 1e-9)), 2
            ),
            "rms_db": round(
                20 * np.log10(max(float(np.sqrt(np.mean(x * x))), 1e-9)), 2
            ),
            "sha256": hashlib.sha256((folder / wav).read_bytes()).hexdigest(),
        }
        data = (
            cue.to_dict()
            if has_score
            else {
                "id": cue.id,
                "title": cue.title,
                "category": cue.category,
                "series": cue.series,
                "mood": cue.mood,
                "style": cue.style,
                "description": cue.description,
                "tags": list(cue.tags),
                "bpm": cue.bpm,
                "tempo": cue.tempo,
                "meter": cue.meter,
                "loop": cue.loop,
                "parts": [],
                "notes": [],
            }
        )
        data["duration"] = len(x) / rate  # 実際の音声の長さ
        mid = None
        if has_score:
            mid = Path("midi") / f"{cue.id}.mid"
            midi.write_midi(cue, folder / mid)
            if midi.read_midi_notes(folder / mid) != midi.expected_notes(cue):
                failures.append(f"{cue.id}: MIDIの音符が元データと一致しない")
            events.append(data)
        row = {k: v for k, v in data.items() if k != "notes"}
        row.update(
            index=index,
            batch=batch_id,
            key=f"{batch_id}/{cue.id}",
            path=wav.as_posix(),
            midi=mid.as_posix() if mid else None,
            has_score=has_score,
            note_count=len(cue.notes),
            **stats,
        )
        rows.append(row)
    info = {
        "id": batch_id,
        "title": meta["title"],
        "description": meta.get("description", ""),
        "request": meta.get("request", ""),
        "agent": meta.get("agent", ""),
        "spec": meta.get("spec", ""),
        "categories": meta["categories"],
        "series": meta.get("series") or [],
        "created": meta["created"],
        "rendered": dt.datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
        "count": len(rows),
        "imported_from": meta.get("imported_from", ""),
    }
    report = {
        "batch": batch_id,
        "ok": not failures,
        "count": len(rows),
        "failures": failures,
        "warnings": [],
        "auto_fixes": fixes,
        "checks": [
            "既存の音声をコピー（再合成なし）",
            "音符データのある曲はMIDIを書き出し、元データとの一致を検査",
        ],
        "audio_only": [r["id"] for r in rows if not r["has_score"]],
        "listening": "エージェントによる聴取評価は未実施",
    }
    dump = lambda p, d: (folder / p).write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    dump("batch.json", info)
    dump("manifest.json", rows)
    (folder / "events.json").write_text(
        json.dumps({"batch": batch_id, "cues": events}, ensure_ascii=False),
        encoding="utf-8",
    )
    dump("verification.json", report)
    log(f"  {batch_id}: {len(rows)} 件（音符データあり {len(events)} 件）")
    return report


def list_batches() -> list[dict]:
    out = []
    for f in sorted(settings.LIBRARY.glob("*/batch.json")):
        info = json.loads(f.read_text(encoding="utf-8"))
        manifest = f.parent / "manifest.json"
        if manifest.exists():
            info["cues"] = json.loads(manifest.read_text(encoding="utf-8"))
            out.append(info)
    return sorted(out, key=lambda b: b.get("created", ""), reverse=True)


def load_events(batch_id: str) -> dict[str, dict]:
    path = batch_dir(batch_id) / "events.json"
    if not path.exists():
        raise BatchError(
            f"バッチ {batch_id} の events.json がありません（render 済みか確認してください）"
        )
    return {
        c["id"]: c
        for c in json.loads(path.read_text(encoding="utf-8"))["cues"]
    }
