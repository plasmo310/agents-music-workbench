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
    """Raised when REAPER automation cannot start, finish, or validate."""
    pass


def to_lua(value) -> str:
    """Serialize supported Python values as Lua literals.

    Args:
        value: Scalar, path, sequence, mapping, or ``None`` to serialize.

    Returns:
        str: Lua expression representing ``value``.

    Raises:
        TypeError: If the value type has no supported Lua representation.
    """
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(float(value)) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        return json.dumps(
            value, ensure_ascii=False
        )  # JSON文字列はLuaの文字列リテラルとしても有効
    if isinstance(value, Path):
        return to_lua(value.resolve().as_posix())
    if isinstance(value, (list, tuple)):
        return "{" + ",".join(to_lua(v) for v in value) + "}"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                f"[{to_lua(str(k))}]={to_lua(v)}" for k, v in value.items()
            )
            + "}"
        )
    raise TypeError(type(value))


def is_running() -> bool:
    """Check whether REAPER is running, conservatively treating probe failures as running.

    Returns:
        bool: Whether REAPER appears to be running or cannot be queried safely.
    """
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq reaper.exe", "/NH"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=15,
                check=False,
            ).stdout
            return "reaper.exe" in out.lower()
        return (
            subprocess.run(
                [
                    "pgrep",
                    "-x",
                    "REAPER" if sys.platform == "darwin" else "reaper",
                ],
                capture_output=True,
                timeout=15,
                check=False,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return True


def ensure_ready(
    exe: Path, logs: Path, log=print, timeout: float = 600
) -> None:
    """Start REAPER when needed and wait until it accepts automation scripts.

    Args:
        exe: REAPER executable path.
        logs: Directory for temporary readiness script and marker files.
        log: Callback used for user-visible progress messages.
        timeout: Maximum seconds to wait for readiness.

    Raises:
        PipelineError: If REAPER does not become ready before the timeout.
    """
    if is_running():
        return
    log(
        "  REAPER を起動します。起動時に案内ダイアログ（評価版の案内など）が出たら閉じてください"
    )
    subprocess.Popen(
        [str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    ready = logs / "reaper_ready.txt"
    ping = logs / "reaper_ready.lua"
    ready.unlink(missing_ok=True)
    ping.write_text(
        f'local f = io.open({to_lua(ready)}, "w"); f:write("ready"); f:close()\n',
        encoding="utf-8",
    )
    deadline, last_ping = time.time() + timeout, 0.0
    while time.time() < deadline:
        time.sleep(1)
        if ready.exists():
            time.sleep(2)  # 起動時のプロジェクト読み込みの完了を待つ余裕
            ready.unlink(missing_ok=True)
            log("  REAPER の起動を確認しました")
            return
        if time.time() - last_ping >= 5 and is_running():
            last_ping = time.time()
            subprocess.Popen(
                [str(exe), "-nonewinst", str(ping.resolve())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    raise PipelineError(
        f"REAPER の起動を {timeout:.0f} 秒以内に確認できませんでした。"
        "REAPER にダイアログが出ていないか確認し、閉じてから再実行してください"
    )


def write_lua_data(path: Path, value) -> Path:
    """Write a Lua file that returns serialized job data.

    Args:
        path: Output Lua file path.
        value: Supported Python value to serialize.

    Returns:
        Path: The written path.
    """
    path.write_text("return " + to_lua(value) + "\n", encoding="utf-8")
    return path


def run(
    exe: Path,
    script: str,
    job_dir: Path,
    stage: str,
    timeout: float,
    log=print,
    **args,
) -> list[str]:
    """Run a REAPER Lua stage and wait for its completion log.

    Args:
        exe: REAPER executable path.
        script: Lua script name or absolute path.
        job_dir: Generation job directory.
        stage: Unique stage label used for generated log names.
        timeout: Maximum seconds to wait for completion.
        log: Callback used for user-visible progress messages.
        **args: Additional values exposed to the Lua script as job variables.

    Returns:
        list[str]: Complete lines from the stage log.

    Raises:
        PipelineError: If REAPER reports an error or the stage times out.
    """
    logs = job_dir / "logs"
    logs.mkdir(exist_ok=True)
    log_file = logs / f"{stage}.log"
    try:
        log_file.unlink(missing_ok=True)
    except PermissionError:
        raise PipelineError(
            f"前回の {stage} の処理がREAPERでまだ動いています（{settings.rel(log_file)} が使用中）。"
            "REAPERにダイアログが出ていないか確認し、終わってから再実行してください"
        )
    job_vars = dict(
        lua_dir=settings.LUA_DIR.resolve().as_posix() + "/",
        log=log_file.resolve().as_posix(),
        stage=stage,
        **args,
    )
    boot = logs / f"{stage}.lua"
    script_path = (
        Path(script)
        if Path(script).is_absolute()
        else settings.LUA_DIR / script
    )
    boot.write_text(
        f"MUSIC_JOB = {to_lua(job_vars)}\n"
        f"local ok, err = pcall(dofile, {to_lua(script_path)})\n"
        'if not ok then local f = io.open(MUSIC_JOB.log, "a"); f:write("ERROR " .. tostring(err) .. "\\n"); f:close() end\n',
        encoding="utf-8",
    )
    ensure_ready(exe, logs, log)
    subprocess.Popen(
        [str(exe), "-nonewinst", str(boot.resolve())],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline, shown = time.time() + timeout, 0
    while time.time() < deadline:
        time.sleep(1)
        if not log_file.exists():
            continue
        lines = log_file.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        for line in lines[shown:]:
            if line.startswith(
                ("START", "RENDERED", "SKIP", "WARN", "MATCHED", "OVERVIEW")
            ):
                log(f"  [REAPER] {line}")
        shown = len(lines)
        if any(l.startswith("ERROR") for l in lines):
            text = "\n".join(
                lines[
                    next(
                        i for i, l in enumerate(lines) if l.startswith("ERROR")
                    ) :
                ]
            )
            raise PipelineError(
                f"REAPERでの処理に失敗しました（{settings.rel(log_file)}）:\n{text}"
            )
        if lines and lines[-1] == "DONE":
            return lines
    raise PipelineError(
        f"REAPERの処理が {timeout:.0f} 秒以内に終わりませんでした。REAPERにダイアログ（ライセンス認証・保存確認など）が"
        f"出ていないか確認してください（{settings.rel(log_file)}）"
    )
