"""音源プロファイル（reaper/lua/profiles/*.lua）の一覧。

既定は REAPER 標準の ReaSynth（追加の音源なしで動く）。Magical 8bit Plug 2 / MASSIVE 用も同梱している。
使う音源の優先順位：コマンドの --profiles ＞ プロジェクト生成リストで選んだ音源 ＞ config.json の profiles ＞ 既定。
"""

from __future__ import annotations

import re

import settings


class ProfileError(ValueError):
    """Raised when requested REAPER instrument profiles are unavailable or empty."""


def _field(name: str, key: str) -> str | None:
    text = (settings.PROFILES_DIR / f"{name}.lua").read_text(encoding="utf-8")
    m = re.search(rf"{key}\s*=\s*'([^']+)'", text)
    return m.group(1) if m else None


def names() -> list[str]:
    """List available REAPER instrument-profile IDs.

    Returns:
        list[str]: Alphabetically ordered Lua profile basenames.
    """
    return sorted(p.stem for p in settings.PROFILES_DIR.glob("*.lua"))


def label(name: str) -> str:
    """Return a profile's human-readable label.

    Args:
        name: Profile ID.

    Returns:
        str: Label from the Lua profile, or the ID when unspecified.
    """
    return _field(name, "label") or name


def plugin(name: str) -> str | None:
    """Return the plugin descriptor declared by a profile.

    Args:
        name: Profile ID.

    Returns:
        str | None: Plugin descriptor, if declared.
    """
    return _field(name, "plugin")


def available() -> list[dict]:
    """List profiles with labels and default-selection status.

    Returns:
        list[dict]: Catalog-ready profile records, with defaults first.
    """
    default = settings.load()["profiles"]
    order = sorted(
        names(),
        key=lambda n: (
            n not in default,
            default.index(n) if n in default else 0,
            n,
        ),
    )
    return [
        {
            "name": n,
            "label": label(n),
            "plugin": plugin(n),
            "default": n in default,
        }
        for n in order
    ]


def check(selected: list[str]) -> list[str]:
    """Validate and de-duplicate a profile selection.

    Args:
        selected: Requested profile IDs.

    Returns:
        list[str]: Unique valid profile IDs in first-seen order.

    Raises:
        ProfileError: If no profile is selected or a profile is unknown.
    """
    selected = list(dict.fromkeys(selected))
    unknown = [n for n in selected if n not in names()]
    if unknown:
        raise ProfileError(
            f"音源プロファイルがありません: {', '.join(unknown)}（使えるもの: {', '.join(names())}）"
        )
    if not selected:
        raise ProfileError("音源プロファイルが指定されていません")
    return selected


def resolve(
    cli: list[str] | None, from_list: list[str] | None
) -> tuple[list[str], str]:
    """Resolve profile selection according to documented precedence.

    Args:
        cli: Profiles supplied by the command line.
        from_list: Profiles stored in the saved project list.

    Returns:
        tuple[list[str], str]: Valid profiles and a human-readable source label.
    """
    if cli:
        return check(cli), "コマンドの --profiles"
    if from_list:
        return check(from_list), "プロジェクト生成リスト"
    return check(
        settings.load()["profiles"]
    ), "config.json" if settings.CONFIG_FILE.exists() else "既定"
