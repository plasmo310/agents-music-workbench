"""試聴カタログで保存した「プロジェクト生成リスト」を探して読み込む。

探す場所（最も新しく保存されたものを採用）:
  1. data/project-lists/*.json（カタログの保存ボタンで直接書き込まれる）
  2. ダウンロードフォルダの project-list-*.json（直接書き込めないブラウザではダウンロードになる）
"""

from __future__ import annotations

import json
from pathlib import Path

import settings

FORMAT = "music-project-list/1"


class ProjectListError(RuntimeError):
    pass


def candidates(cfg: dict | None = None) -> list[Path]:
    cfg = cfg or settings.load()
    found = list(settings.PROJECT_LISTS.glob("*.json"))
    downloads = settings.downloads_dir(cfg)
    if downloads.is_dir():
        found += [
            p for p in downloads.glob("project-list-*.json") if p.is_file()
        ]
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def latest(cfg: dict | None = None) -> Path:
    found = candidates(cfg)
    if not found:
        raise ProjectListError(
            "プロジェクト生成リストが見つかりません。試聴カタログ（data/library/index.html）で★を付け、"
            "「全タブの★を保存」または「このタブの★を保存」を押してください。"
        )
    return found[0]


def _items(data) -> list[dict]:
    if isinstance(data, dict):
        data = data.get("items", [])
    out = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, str) and "/" in item:
            batch, cue = item.split("/", 1)
            out.append({"batch": batch, "id": cue})
        elif isinstance(item, dict) and item.get("batch") and item.get("id"):
            out.append({"batch": item["batch"], "id": item["id"]})
        elif isinstance(item, dict) and "/" in str(item.get("key", "")):
            batch, cue = item["key"].split("/", 1)
            out.append({"batch": batch, "id": cue})
        else:
            raise ProjectListError(f"リストの項目を解釈できません: {item!r}")
    return out


def load(path: str | Path | None = None) -> dict:
    source = Path(path) if path else latest()
    if not source.is_file():
        raise ProjectListError(f"ファイルがありません: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise ProjectListError(f"JSONとして読めません: {source}（{e}）")
    manifests: dict[str, dict[str, dict]] = {}
    items, seen, missing = [], set(), []
    for item in _items(data):
        key = f"{item['batch']}/{item['id']}"
        if key in seen:
            continue
        seen.add(key)
        if item["batch"] not in manifests:
            mf = settings.LIBRARY / item["batch"] / "manifest.json"
            manifests[item["batch"]] = (
                {
                    r["id"]: r
                    for r in json.loads(mf.read_text(encoding="utf-8"))
                }
                if mf.exists()
                else {}
            )
        row = manifests[item["batch"]].get(item["id"])
        if not row:
            missing.append(key)
            continue
        if row.get("has_score") is False:
            raise ProjectListError(
                f"{key} は音声のみの素材で音符データがないため、REAPERプロジェクトにできません"
            )
        items.append(
            {
                "key": key,
                "batch": item["batch"],
                "id": item["id"],
                "title": row["title"],
                "category": row["category"],
                "loop": row["loop"],
            }
        )
    if missing:
        raise ProjectListError(
            "library に存在しない曲がリストに含まれています（別の曲で代用しません）: "
            + ", ".join(missing)
        )
    if not items:
        raise ProjectListError(f"リストが空です: {source}")
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if profiles is not None and not (
        isinstance(profiles, list)
        and all(isinstance(p, str) for p in profiles)
    ):
        raise ProjectListError(
            f"profiles は音源プロファイル名のリストにしてください: {profiles!r}"
        )
    return {
        "source": str(source),
        "saved_at": data.get("saved_at") if isinstance(data, dict) else None,
        "items": items,
        "profiles": profiles or None,
    }
