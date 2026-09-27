"""REAPER にスクリプトを実行させ、ログで完了を待つ。

`reaper -nonewinst <script.lua>` で起動中のREAPERにスクリプトを渡す（起動していなければ新しく起動する）。
スクリプトは新しいプロジェクトタブだけを操作し、完了時にログへ DONE / ERROR を書く。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import settings


class PipelineError(RuntimeError):
    pass


def to_lua(value) -> str:
    if value is None:
        return 'nil'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return repr(float(value)) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # JSON文字列はLuaの文字列リテラルとしても有効
    if isinstance(value, Path):
        return to_lua(value.resolve().as_posix())
    if isinstance(value, (list, tuple)):
        return '{' + ','.join(to_lua(v) for v in value) + '}'
    if isinstance(value, dict):
        return '{' + ','.join(f'[{to_lua(str(k))}]={to_lua(v)}' for k, v in value.items()) + '}'
    raise TypeError(type(value))


def is_running() -> bool:
    """REAPER が起動しているか。確認できない環境では起動中とみなす。"""
    try:
        if sys.platform == 'win32':
            out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq reaper.exe', '/NH'], capture_output=True, text=True,
                                 errors='replace', timeout=15).stdout
            return 'reaper.exe' in out.lower()
        return subprocess.run(['pgrep', '-x', 'REAPER' if sys.platform == 'darwin' else 'reaper'],
                              capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True


def write_lua_data(path: Path, value) -> Path:
    path.write_text('return ' + to_lua(value) + '\n', encoding='utf-8')
    return path


def run(exe: Path, script: str, job_dir: Path, stage: str, timeout: float, log=print, **args) -> list[str]:
    """lua/<script> を実行し、ログの行を返す。ERROR やタイムアウトは PipelineError。"""
    logs = job_dir / 'logs'
    logs.mkdir(exist_ok=True)
    log_file = logs / f'{stage}.log'
    try:
        log_file.unlink(missing_ok=True)
    except PermissionError:
        raise PipelineError(f'前回の {stage} の処理がREAPERでまだ動いています（{settings.rel(log_file)} が使用中）。'
                            'REAPERにダイアログが出ていないか確認し、終わってから再実行してください')
    job_vars = dict(lua_dir=settings.LUA_DIR.resolve().as_posix() + '/', log=log_file.resolve().as_posix(), stage=stage, **args)
    boot = logs / f'{stage}.lua'
    script_path = Path(script) if Path(script).is_absolute() else settings.LUA_DIR / script
    boot.write_text(
        f'MUSIC_JOB = {to_lua(job_vars)}\n'
        f'local ok, err = pcall(dofile, {to_lua(script_path)})\n'
        'if not ok then local f = io.open(MUSIC_JOB.log, "a"); f:write("ERROR " .. tostring(err) .. "\\n"); f:close() end\n',
        encoding='utf-8')
    if is_running():
        subprocess.Popen([str(exe), '-nonewinst', str(boot.resolve())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # 起動していなければ新しく起動してスクリプトを渡す（-nonewinst は起動中のREAPERにしか届かない）
        log('  REAPER を起動します（起動時にダイアログが出たら閉じてください）')
        subprocess.Popen([str(exe), str(boot.resolve())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    deadline, shown = time.time() + timeout, 0
    while time.time() < deadline:
        time.sleep(1)
        if not log_file.exists():
            continue
        lines = log_file.read_text(encoding='utf-8', errors='replace').splitlines()
        for line in lines[shown:]:
            if line.startswith(('START', 'RENDERED', 'SKIP', 'WARN', 'MATCHED', 'OVERVIEW')):
                log(f'  [REAPER] {line}')
        shown = len(lines)
        if any(l.startswith('ERROR') for l in lines):
            text = '\n'.join(lines[next(i for i, l in enumerate(lines) if l.startswith('ERROR')):])
            raise PipelineError(f'REAPERでの処理に失敗しました（{settings.rel(log_file)}）:\n{text}')
        if lines and lines[-1] == 'DONE':
            return lines
    raise PipelineError(f'REAPERの処理が {timeout:.0f} 秒以内に終わりませんでした。REAPERにダイアログ（ライセンス認証・保存確認など）が'
                        f'出ていないか確認してください（{settings.rel(log_file)}）')
