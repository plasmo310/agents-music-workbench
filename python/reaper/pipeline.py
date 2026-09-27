"""プロジェクト生成リスト → REAPERプロジェクト一式、の工程をまとめる。

data/projects/<job_id>/
  job.json / job.lua          工程の入力（選択された曲の音符データ・音源プロファイル）
  project_list.json           使用したプロジェクト生成リストの控え
  <曲>/score.mid              共通のパート別MIDI
  <曲>/<音源>/<曲>_<音源>.rpp  音色設定済みの編集用プロジェクト
  <曲>/<音源>/preview_matched.wav  音量を揃えた試聴用WAV（preview.wav は調整前）
  <曲>/<音源>/sound_settings.tsv   設定したパラメーターの記録
  <job_id>_overview.rpp       全曲をサブプロジェクトとして並べたまとめプロジェクト
  delivery.json / README.md   成果物の一覧と検証結果
  logs/                       REAPER側のログ
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import shutil
from pathlib import Path

import numpy as np

import settings
from catalog import project_list
from music import batch, midi, synth
from music.score import cue_from_dict, parse_meter

from .runner import PipelineError, run, write_lua_data

TAIL = 0.35
GAP = 2.0


def job_dir(job_id: str | None) -> Path:
    if job_id:
        path = settings.PROJECTS / job_id
        if not (path / 'job.json').exists():
            raise PipelineError(f'ジョブが見つかりません: {job_id}')
        return path
    jobs = sorted(settings.PROJECTS.glob('*/job.json'), key=lambda p: p.parent.name)
    if not jobs:
        raise PipelineError('ジョブがありません。先に project prepare を実行してください')
    return jobs[-1].parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _profile_label(name: str) -> str:
    text = (settings.PROFILES_DIR / f'{name}.lua').read_text(encoding='utf-8')
    m = re.search(r"label\s*=\s*'([^']+)'", text)
    return m.group(1) if m else name


def prepare(list_path: str | None, profiles: list[str], name: str | None = None, log=print) -> Path:
    sel = project_list.load(list_path)
    log(f'リスト: {sel["source"]}（{len(sel["items"])} 曲）')
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    slug = re.sub(r'[^A-Za-z0-9_\-]+', '-', name).strip('-') if name else ''
    job_id = f'{stamp}-{slug}' if slug else stamp
    folder = settings.PROJECTS / job_id
    folder.mkdir(parents=True, exist_ok=False)

    events: dict[str, dict] = {}
    ids = [i['id'] for i in sel['items']]
    cues_json, cues_lua = [], []
    for item in sel['items']:
        if item['batch'] not in events:
            events[item['batch']] = batch.load_events(item['batch'])
        data = events[item['batch']][item['id']]
        cue = cue_from_dict(data)
        cue.validate()
        cue_name = item['id'] if ids.count(item['id']) == 1 else f'{item["batch"]}__{item["id"]}'
        cue_dir = folder / cue_name
        midi.write_midi(cue, cue_dir / 'score.mid')
        num, den = parse_meter(cue.meter)
        common = dict(key=item['key'], batch=item['batch'], id=item['id'], title=cue.title, category=cue.category,
                      loop=cue.loop, bpm=cue.bpm, tempo=cue.tempo, meter=cue.meter,
                      length_beats=cue.length_beats, duration=cue.duration, name=cue_name)
        cues_json.append(common)
        cues_lua.append(dict(
            common, meter_num=num, meter_den=den,
            parts=[dict(name=p, role=cue.role(p), mix_db=cue.mix_db(p),
                        voices=list(dict.fromkeys(n.voice for n in cue.notes if n.part == p)),
                        bend_range=midi.bend_range(cue, p)) for p in cue.parts],
            notes=[n.to_dict() for n in cue.notes],
        ))
        log(f'  {item["key"]} → {cue_name}/score.mid')
    shutil.copyfile(sel['source'], folder / 'project_list.json')
    job = dict(id=job_id, name=name or '', created=dt.datetime.now().isoformat(timespec='seconds'),
               project_list=dict(source=sel['source'], saved_at=sel.get('saved_at')),
               profiles=profiles, cues=cues_json)
    (folder / 'job.json').write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
    write_lua_data(folder / 'job.lua', dict(id=job_id, profiles=profiles, cues=cues_lua))
    return folder


def _paths(folder: Path, cue: dict, profile: str) -> dict:
    out = folder / cue['name'] / profile
    return dict(dir=out, rpp=out / f'{cue["name"]}_{profile}.rpp', raw=out / 'preview.wav',
                matched=out / 'preview_matched.wav', settings=out / 'sound_settings.tsv')


def _audio_check(path: Path, expected_sec: float) -> dict:
    x, rate = synth.read_wav(path)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
    sec = len(x) / rate
    problems = []
    if rms < 1e-5:
        problems.append('無音')
    if peak >= .999:
        problems.append('クリッピング')
    if abs(sec - expected_sec) > .05:
        problems.append(f'長さが想定外（{sec:.3f}秒 / 想定 {expected_sec:.3f}秒）')
    db = lambda v: round(20 * math.log10(max(v, 1e-9)), 2)
    return dict(file=path.name, seconds=round(sec, 3), rate=rate, peak_db=db(peak), rms_db=db(rms), problems=problems)


def _expected_seconds(cue: dict) -> float:
    return cue['duration'] if cue['loop'] else cue['duration'] + TAIL


def build(folder: Path, cfg: dict, stage: str = 'all', force: bool = False, log=print) -> int:
    exe = settings.reaper_exe(cfg)
    if not exe:
        raise PipelineError('REAPER が見つかりません。config.json の reaper_path を設定してください（python python/cli.py doctor で確認）')
    job = _load(folder / 'job.json')
    timeout = float(cfg.get('reaper_timeout_sec', 1800))
    common = dict(job=(folder / 'job.lua').resolve().as_posix(), job_root=folder.resolve().as_posix(), force=force)
    log(f'ジョブ: {settings.rel(folder)}（{len(job["cues"])} 曲 × {", ".join(job["profiles"])}）')

    # 1. 先頭1曲で、両音源の保存・再読み込み・レンダーが成立するか確認する
    log('1/5 パイロット制作（先頭の1曲）')
    run(exe, 'build.lua', folder, 'pilot', timeout, log, **common)
    first = job['cues'][0]
    for profile in job['profiles']:
        check = _audio_check(_paths(folder, first, profile)['raw'], _expected_seconds(first))
        if check['problems']:
            raise PipelineError(f'パイロットのレンダー結果に問題があります（{first["key"]} / {profile}）: {", ".join(check["problems"])}')
    if stage == 'pilot':
        log(f'パイロット完了。音色を確認後、続きは: python python/cli.py project build {folder.name}')
        return 0

    # 2. 残りの曲
    warnings = []
    if len(job['cues']) > 1:
        log('2/5 残りの曲を制作')
        lines = run(exe, 'build.lua', folder, 'remaining', timeout, log, **common)
        warnings += [l[5:] for l in lines if l.startswith('WARN')]
    for stage_log in ('pilot',):
        path = folder / 'logs' / f'{stage_log}.log'
        warnings += [l[5:] for l in path.read_text(encoding='utf-8').splitlines() if l.startswith('WARN')]

    # 3. 音量合わせ
    log('3/5 音源版の音量合わせ')
    items = []
    for cue in job['cues']:
        for profile in job['profiles']:
            p = _paths(folder, cue, profile)
            x, _ = synth.read_wav(p['raw'])
            peak, rms = float(np.max(np.abs(x))), float(np.sqrt(np.mean(x * x)))
            if rms < 1e-6:
                raise PipelineError(f'無音のレンダー結果です: {settings.rel(p["raw"])}')
            gain = min((.095 if cue['loop'] else .13) / rms, 10 ** (-2 / 20) / peak)
            items.append(dict(key=cue['key'], profile=profile, rpp=p['rpp'].resolve().as_posix(),
                              folder=p['dir'].resolve().as_posix(), gain=gain))
    data = write_lua_data(folder / 'logs' / 'level_data.lua', items)
    run(exe, 'level_match.lua', folder, 'level_match', timeout, log, data=data.resolve().as_posix())

    # 4. 全曲まとめ（サブプロジェクト）
    log('4/5 全曲まとめプロジェクト（サブプロジェクト）')
    overview = folder / f'{job["id"]}_overview.rpp'
    entries, at = [], 0.0
    for cue in job['cues']:
        length = _expected_seconds(cue)
        entries.append(dict(key=cue['key'], title=cue['title'], start=at, length=length,
                            versions={pr: _paths(folder, cue, pr)['rpp'].resolve().as_posix() for pr in job['profiles']}))
        at += length + GAP
    notes = ('全曲まとめ（サブプロジェクト）\n'
             'トラック = 音源。同じ曲の各音源版は同じ時刻に並んでいるので、ソロで切り替えて聴き比べられます。\n'
             'アイテムをダブルクリックすると、その曲の編集用プロジェクトが開きます。保存すると、ここにも反映されます。')
    data = write_lua_data(folder / 'logs' / 'overview_data.lua', dict(
        rpp=overview.resolve().as_posix(), notes=notes, entries=entries,
        profiles=[dict(name=p, label=_profile_label(p)) for p in job['profiles']]))
    run(exe, 'overview.lua', folder, 'overview', timeout, log, data=data.resolve().as_posix())

    # 5. 検証と納品情報
    log('5/5 検証・納品情報の作成')
    report = deliver(folder, job, overview, warnings)
    from catalog import build as catalog
    log(f'カタログ更新: {settings.rel(catalog.build())}')
    if not report['ok']:
        for f in report['failures']:
            log(f'  ✗ {f}')
        return 1
    log(f'完了: {settings.rel(overview)}')
    return 0


def deliver(folder: Path, job: dict, overview: Path, warnings: list[str]) -> dict:
    failures, cues = [], []
    events: dict[str, dict] = {}
    for cue in job['cues']:
        if cue['batch'] not in events:
            events[cue['batch']] = batch.load_events(cue['batch'])
        score = cue_from_dict(events[cue['batch']][cue['id']])
        score.validate()
        mid = folder / cue['name'] / 'score.mid'
        try:
            if midi.read_midi_notes(mid) != midi.expected_notes(score):
                failures.append(f'{cue["key"]}: 共通MIDIが元の音符データと一致しません')
        except ValueError as e:
            failures.append(f'{cue["key"]}: 共通MIDIの構造 {e}')
        versions = {}
        for profile in job['profiles']:
            p = _paths(folder, cue, profile)
            if not p['rpp'].exists() or not p['matched'].exists():
                failures.append(f'{cue["key"]} / {profile}: RPPまたは試聴WAVがありません')
                continue
            audio = _audio_check(p['matched'], _expected_seconds(cue))
            failures += [f'{cue["key"]} / {profile}: {x}' for x in audio['problems']]
            rel = lambda x: x.relative_to(folder).as_posix()
            versions[profile] = dict(rpp=rel(p['rpp']), wav=rel(p['matched']), raw_wav=rel(p['raw']),
                                     settings=rel(p['settings']), audio=audio)
        cues.append(dict(cue, midi=f'{cue["name"]}/score.mid', versions=versions))
    if not overview.exists():
        failures.append('全曲まとめプロジェクトがありません')
    profiles = [dict(name=p, label=_profile_label(p)) for p in job['profiles']]
    verification = dict(
        ok=not failures, failures=failures, warnings=warnings,
        checks=['各RPPを保存→再読み込みし、音源ロード・音色パラメーター・MIDIノート数を照合（logs/pilot.log, remaining.log）',
                '音量合わせ後に再度開き直してレンダー（logs/level_match.log）',
                '試聴WAVの無音・クリッピング・長さを検査',
                '共通MIDIと元の音符データの一致（960 PPQ）',
                '全曲まとめのサブプロジェクト参照を再読み込みで確認（logs/overview.log）'],
        listening='エージェントによる聴取評価は未実施')
    delivery = dict(id=job['id'], name=job.get('name') or '', created=job['created'], profiles=profiles,
                    overview=overview.relative_to(folder).as_posix() if overview.exists() else None,
                    cues=cues, verification=verification)
    (folder / 'delivery.json').write_text(json.dumps(delivery, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'README.md').write_text(_readme(delivery), encoding='utf-8')
    return verification


def _readme(d: dict) -> str:
    labels = ' / '.join(p['label'] for p in d['profiles'])
    lines = [f'# REAPERプロジェクト {d["id"]}', '',
             f'{len(d["cues"])} 曲 × {labels}。試聴は試聴カタログ（data/library/index.html）の「生成済みプロジェクト」タブから。', '',
             '## 開き方', '',
             f'- 全曲をまとめて見る: `{d["overview"]}`（各曲がサブプロジェクトとして並ぶ。トラック=音源、ダブルクリックで各曲を編集）',
             '- 1曲ずつ編集する: `<曲>/<音源>/<曲>_<音源>.rpp`', '',
             '## ファイル', '',
             '- `score.mid`：共通のパート別MIDI（Type 1 / 960 PPQ）。音色設定は含まない',
             '- `<音源>/*.rpp`：音色設定済みの編集用プロジェクト。MIDIは埋め込み済み',
             '- `<音源>/preview_matched.wav`：音量を揃えた試聴用（48 kHz / 24-bit）。`preview.wav` は調整前',
             '- `<音源>/sound_settings.tsv`：設定したパラメーターの記録', '',
             '## 注意', '',
             '- ループ曲は3周並べ、中央の1周が再生・書き出し範囲。3周は独立したMIDIアイテムです',
             '- SEには0.35秒の余韻枠があります',
             '- 元のプレビューWAVとは音色が異なります（音源による再アレンジ）',
             f'- 必要な音源: {labels}', '',
             '## 曲', '']
    for c in d['cues']:
        lines.append(f'- {c["title"]}（`{c["key"]}`）→ `{c["name"]}/`')
    v = d['verification']
    lines += ['', '## 検証', '', *(f'- {c}' for c in v['checks']), f'- {v["listening"]}']
    if v['failures']:
        lines += ['', '### 問題', '', *(f'- {f}' for f in v['failures'])]
    if v['warnings']:
        lines += ['', '### 注意事項', '', *(f'- {w}' for w in v['warnings'])]
    return '\n'.join(lines) + '\n'
