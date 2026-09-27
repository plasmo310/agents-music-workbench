"""試聴カタログ（data/library/index.html）の生成。

data/library/*/ の書き出し済みバッチと data/projects/*/delivery.json を集め、データを埋め込んだ1枚のHTMLにする。
サーバー不要で、ファイルをブラウザで直接開いて使う。
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import settings
from music import batch

OUTPUT = settings.LIBRARY / "index.html"
PLACEHOLDER = re.compile(r"/\*__DATA__\*/\s*null")


def _file(job_dir: Path, rel: str | None) -> dict | None:
    if not rel:
        return None
    path = job_dir / rel
    return {
        "src": f"../projects/{job_dir.name}/{rel}",
        "abs": str(path.resolve()),
        "exists": path.exists(),
    }


def list_projects() -> list[dict]:
    jobs = []
    for f in settings.PROJECTS.glob("*/delivery.json"):
        job_dir = f.parent
        d = json.loads(f.read_text(encoding="utf-8"))
        d["folder_abs"] = str(job_dir.resolve())
        d["overview"] = _file(job_dir, d.get("overview"))
        for c in d["cues"]:
            c["midi"] = _file(job_dir, c.get("midi"))
            for ver in c["versions"].values():
                ver["rpp"] = _file(job_dir, ver.get("rpp"))
                ver["wav"] = _file(job_dir, ver.get("wav"))
        jobs.append(d)
    return sorted(jobs, key=lambda j: j.get("created", ""), reverse=True)


def data() -> dict:
    batches = batch.list_batches()
    for b in batches:
        for c in b["cues"]:
            c["src"] = f"{b['id']}/{c['path']}"
            c["midi_src"] = f"{b['id']}/{c['midi']}" if c.get("midi") else None
    from reaper import profiles

    return {
        "generated": dt.datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
        "batches": batches,
        "projects": list_projects(),
        "profiles": profiles.available(),
    }


def build() -> Path:
    payload = json.dumps(data(), ensure_ascii=False).replace("</", "<\\/")
    html = (Path(__file__).with_name("catalog.html")).read_text(
        encoding="utf-8"
    )
    # HTML を整形しても差し込めるよう、/*__DATA__*/ と null の間の空白は問わない
    html, count = PLACEHOLDER.subn(lambda _: payload, html)
    if count != 1:
        raise RuntimeError("catalog.html にデータの差し込み位置がありません")
    settings.LIBRARY.mkdir(exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    return OUTPUT
