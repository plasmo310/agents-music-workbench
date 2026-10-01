"""動作環境の確認。"""

from __future__ import annotations

import re
import sys

import settings
from reaper import profiles as profile_list


def run() -> int:
    """Check Python, audio dependencies, REAPER, and selected profiles.

    Returns:
        int: ``0`` when required checks pass; otherwise ``1``.
    """
    ok = True
    mark = lambda good: "✓" if good else "✗"
    cfg = settings.load()
    print(
        f"{mark(sys.version_info >= (3, 10))} Python {sys.version.split()[0]}（3.10以上）"
    )
    ok &= sys.version_info >= (3, 10)
    try:
        import numpy

        print(f"✓ numpy {numpy.__version__}")
    except ImportError:
        print("✗ numpy がありません（pip install -r requirements.txt）")
        ok = False
    print(
        f"{'✓' if settings.CONFIG_FILE.exists() else '-'} config.json {'あり' if settings.CONFIG_FILE.exists() else 'なし（既定値を使用。変更する場合は config.example.json をコピー）'}"
    )

    exe = settings.reaper_exe(cfg)
    print(
        f"{mark(exe is not None)} REAPER: {exe or '見つかりません（config.json の reaper_path を設定）'}"
    )
    ini_dir = settings.reaper_resource_dir()
    inis = (
        [p for p in ini_dir.glob("reaper-vstplugins*.ini")]
        if ini_dir.is_dir()
        else []
    )
    cache = "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in inis
    )
    if not inis:
        print(f"- REAPERのプラグイン一覧が見つかりません（{ini_dir}）")

    print(
        f"音源プロファイル（既定: {', '.join(cfg['profiles'])}。カタログで保存するときや --profiles で選べます）"
    )
    for name in profile_list.names():
        plugin = profile_list.plugin(name) or "?"
        display = re.sub(r"^\w+:\s*", "", plugin)
        found = display in cache if inis else None
        state = (
            "登録あり" if found else "登録なし" if found is False else "未確認"
        )
        print(
            f"  {'✓' if found else '✗' if found is False else '-'} {name:12s} {plugin}（REAPERのプラグイン一覧: {state}）"
        )
        if found is False and name in cfg["profiles"]:
            ok = False
    print(
        "※ 一覧への登録は実際のロード成功やライセンス認証の証明ではありません。project build のパイロット制作で確認します。"
    )
    return 0 if ok else 1
