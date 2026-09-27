"""音源プロファイル（reaper/lua/profiles/*.lua）の一覧。

既定は REAPER 標準の ReaSynth（追加の音源なしで動く）。Magical 8bit Plug 2 / MASSIVE 用も同梱している。
使う音源の優先順位：コマンドの --profiles ＞ プロジェクト生成リストで選んだ音源 ＞ config.json の profiles ＞ 既定。
"""
from __future__ import annotations

import re

import settings


class ProfileError(ValueError):
    pass


def _field(name: str, key: str) -> str | None:
    text = (settings.PROFILES_DIR / f'{name}.lua').read_text(encoding='utf-8')
    m = re.search(rf"{key}\s*=\s*'([^']+)'", text)
    return m.group(1) if m else None


def names() -> list[str]:
    return sorted(p.stem for p in settings.PROFILES_DIR.glob('*.lua'))


def label(name: str) -> str:
    return _field(name, 'label') or name


def plugin(name: str) -> str | None:
    return _field(name, 'plugin')


def available() -> list[dict]:
    """既定の音源を先頭にした一覧（カタログの選択肢に使う）。"""
    default = settings.load()['profiles']
    order = sorted(names(), key=lambda n: (n not in default, default.index(n) if n in default else 0, n))
    return [dict(name=n, label=label(n), plugin=plugin(n), default=n in default) for n in order]


def check(selected: list[str]) -> list[str]:
    selected = list(dict.fromkeys(selected))
    unknown = [n for n in selected if n not in names()]
    if unknown:
        raise ProfileError(f'音源プロファイルがありません: {", ".join(unknown)}（使えるもの: {", ".join(names())}）')
    if not selected:
        raise ProfileError('音源プロファイルが指定されていません')
    return selected


def resolve(cli: list[str] | None, from_list: list[str] | None) -> tuple[list[str], str]:
    """(使う音源, どこで指定されたか)。"""
    if cli:
        return check(cli), 'コマンドの --profiles'
    if from_list:
        return check(from_list), 'プロジェクト生成リスト'
    return check(settings.load()['profiles']), 'config.json' if settings.CONFIG_FILE.exists() else '既定'
