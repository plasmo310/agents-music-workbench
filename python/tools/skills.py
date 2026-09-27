"""スキルの配置。

正本は .agents/skills/（Codex が読む場所）。Claude Code は .claude/skills/ を読むため、
そこには説明文だけを持つ案内用の SKILL.md を置き、本体（.agents/skills/）を読ませる。
内容の重複を避けつつ、両方のエージェントでスキルが自動で選ばれるようにするため。
"""

from __future__ import annotations

import re
import shutil

import settings

STUB = """---
name: {name}
description: {description}
---

このスキルの本体は Codex と共用の `.agents/skills/{name}/SKILL.md` にあります。
そのファイルを読み、書かれている手順に従ってください（参照資料も同じフォルダにあります）。
"""


def names() -> list[str]:
    return sorted(
        p.name for p in settings.SKILLS.iterdir() if (p / "SKILL.md").is_file()
    )


def stub(name: str) -> str:
    text = (settings.SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    if not m:
        raise ValueError(f"{name}/SKILL.md に description がありません")
    return STUB.format(name=name, description=m.group(1).strip())


def sync() -> list[str]:
    out = []
    current = set(names())
    if settings.CLAUDE_SKILLS.is_dir():
        for old in settings.CLAUDE_SKILLS.iterdir():
            if old.is_dir() and old.name not in current:
                shutil.rmtree(old)
                out.append(f"削除: {settings.rel(old)}")
    for name in current:
        dest = settings.CLAUDE_SKILLS / name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(stub(name), encoding="utf-8")
        out.append(
            f"{settings.rel(settings.SKILLS / name)} → {settings.rel(dest)}（案内）"
        )
    return out


def differences() -> list[str]:
    """Claude Code 用の案内が正本と食い違っていれば、その一覧（テスト用）。"""
    diffs = []
    for name in names():
        dest = settings.CLAUDE_SKILLS / name / "SKILL.md"
        if not dest.exists() or dest.read_text(encoding="utf-8") != stub(name):
            diffs.append(settings.rel(dest))
    return diffs
