"""パスと設定。すべてのパスはリポジトリのルート（ROOT）を基準にする。

    ROOT/                   ← このファイル（python/settings.py）の1つ上のフォルダ
      config.json           個人設定（任意。config.example.json をコピー）
      data/                 作業データ（Git の管理対象外）
        library/            作曲バッチと試聴カタログ
        project-lists/      プロジェクト生成リスト
        projects/           REAPERプロジェクト
      .agents/skills/       スキルの正本（.claude/skills/ は案内のみ）
      python/               このコード
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_DIR = ROOT / 'python'
DATA = ROOT / 'data'
LIBRARY = DATA / 'library'
PROJECT_LISTS = DATA / 'project-lists'
PROJECTS = DATA / 'projects'
SKILLS = ROOT / '.agents' / 'skills'
CLAUDE_SKILLS = ROOT / '.claude' / 'skills'
LUA_DIR = PYTHON_DIR / 'reaper' / 'lua'
PROFILES_DIR = LUA_DIR / 'profiles'
CONFIG_FILE = ROOT / 'config.json'

DEFAULTS = {
    'reaper_path': '',
    'profiles': ['reasynth'],   # 追加の音源なしで動く REAPER 標準の ReaSynth
    'downloads_dir': '',
    'reaper_timeout_sec': 1800,
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.is_file():
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding='utf-8-sig')))
    return cfg


def downloads_dir(cfg: dict) -> Path:
    if cfg.get('downloads_dir'):
        return Path(os.path.expandvars(os.path.expanduser(cfg['downloads_dir'])))
    return Path.home() / 'Downloads'


def reaper_candidates() -> list[Path]:
    if sys.platform == 'win32':
        bases = [os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')]
        return [Path(b) / name / 'reaper.exe' for b in bases for name in ('REAPER (x64)', 'REAPER')]
    if sys.platform == 'darwin':
        return [Path('/Applications/REAPER.app/Contents/MacOS/REAPER'), Path('/Applications/REAPER64.app/Contents/MacOS/REAPER')]
    return [Path.home() / 'opt/REAPER/reaper', Path('/opt/REAPER/reaper'), Path('/usr/local/bin/reaper')]


def reaper_exe(cfg: dict) -> Path | None:
    if cfg.get('reaper_path'):
        p = Path(os.path.expandvars(os.path.expanduser(cfg['reaper_path'])))
        return p if p.is_file() else None
    return next((p for p in reaper_candidates() if p.is_file()), None)


def reaper_resource_dir() -> Path:
    if sys.platform == 'win32':
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming')) / 'REAPER'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/REAPER'
    return Path.home() / '.config/REAPER'


def rel(path: Path) -> str:
    """リポジトリ基準の表示用パス。"""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)
