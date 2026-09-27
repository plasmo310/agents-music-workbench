"""コマンドライン入口。`python python/cli.py <コマンド> -h` で各コマンドの説明を表示する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

import settings


def cmd_new_batch(args):
    from music import batch

    path = batch.new_batch(args.name, example=args.example)
    print(f"作成しました: {settings.rel(path)}")
    print(
        f"{'' if args.example else '編集後に'}実行: python python/cli.py render {path.parent.name}"
    )


def cmd_render(args):
    from music import batch

    print(f"書き出し中: {args.batch}")
    report = batch.render(args.batch, force=args.force)
    for w in report["warnings"]:
        print(f"  注意: {w}")
    for cue_id, fixes in report["auto_fixes"].items():
        for f in fixes:
            print(f"  自動修正 {cue_id}: {f}")
    if not args.no_catalog:
        from catalog import build as catalog

        print(f"カタログ更新: {settings.rel(catalog.build())}")
    if not report["ok"]:
        print("検査で問題が見つかりました:", file=sys.stderr)
        for f in report["failures"]:
            print(f"  ✗ {f}", file=sys.stderr)
        return 1
    print(
        f"完了: {report['count']} 件（{settings.rel(settings.LIBRARY / args.batch / 'verification.json')}）"
    )


def cmd_catalog(args):
    from catalog import build as catalog

    print(f"カタログ更新: {settings.rel(catalog.build())}")


def cmd_project_list(args):
    from catalog import project_list

    sel = project_list.load(args.file)
    print(f"ファイル: {sel['source']}（保存 {sel.get('saved_at') or '不明'}）")
    for item in sel["items"]:
        print(f"  {item['key']}  {item['title']}  [{item['category']}]")
    print(f"計 {len(sel['items'])} 件")
    from reaper import profiles

    names, origin = profiles.resolve(None, sel["profiles"])
    print(f"音源: {', '.join(profiles.label(n) for n in names)}（{origin}）")


def cmd_project(args):
    from reaper import pipeline

    cfg = settings.load()
    if args.action in ("prepare", "all"):
        job = pipeline.prepare(args.list, args.profiles, name=args.name)
        print(f"準備完了: {settings.rel(job)}")
        if args.action == "prepare":
            print(f"次に実行: python python/cli.py project build {job.name}")
            return
        args.job = job.name
    job_dir = pipeline.job_dir(args.job)
    return pipeline.build(job_dir, cfg, stage=args.stage, force=args.force)


def cmd_doctor(args):
    from tools import doctor

    return doctor.run()


def cmd_sync_skills(args):
    from tools import skills

    for line in skills.sync():
        print(line)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python python/cli.py",
        description="AIエージェントによる作曲→試聴→REAPERプロジェクト生成",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser(
        "new-batch",
        help="作曲バッチの雛形（data/library/<日付-名前>/compose.py）を作る",
    )
    s.add_argument("name", help="英数字・_・- の名前。先頭に日付が付く")
    s.add_argument(
        "--example",
        action="store_true",
        help="雛形の代わりに見本（examples/demo_batch）をコピーする",
    )
    s.set_defaults(func=cmd_new_batch)

    s = sub.add_parser(
        "render",
        help="compose.py からWAV・MIDI・一覧データを書き出し、カタログを更新する",
    )
    s.add_argument("batch")
    s.add_argument(
        "--force", action="store_true", help="書き出し済みのバッチを作り直す"
    )
    s.add_argument(
        "--no-catalog", action="store_true", help="カタログを更新しない"
    )
    s.set_defaults(func=cmd_render)

    s = sub.add_parser(
        "catalog", help="試聴カタログ data/library/index.html を作り直す"
    )
    s.set_defaults(func=cmd_catalog)

    s = sub.add_parser(
        "project-list", help="最新のプロジェクト生成リストを表示する"
    )
    s.add_argument("--file", help="リストのJSONを明示する")
    s.set_defaults(func=cmd_project_list)

    s = sub.add_parser("project", help="REAPERプロジェクトを生成する")
    s.add_argument(
        "action",
        choices=["prepare", "build", "all"],
        help="prepare=リストからMIDI等を準備 / build=REAPERで制作 / all=両方",
    )
    s.add_argument(
        "job",
        nargs="?",
        help="build 対象のジョブ（data/projects/ 内のフォルダ名。省略時は最新）",
    )
    s.add_argument(
        "--list", help="プロジェクト生成リストのJSON（省略時は最新）"
    )
    s.add_argument(
        "--profiles",
        nargs="+",
        help="音源プロファイル（例: reasynth magical8bit massive）。省略時はリストで選んだ音源 → config.json → reasynth",
    )
    s.add_argument("--name", help="ジョブ名に付ける短い名前")
    s.add_argument(
        "--stage",
        choices=["pilot", "all"],
        default="all",
        help="pilot=先頭1曲だけ制作して止める / all=全工程（既定）",
    )
    s.add_argument(
        "--force", action="store_true", help="制作済みの曲も作り直す"
    )
    s.set_defaults(func=cmd_project)

    s = sub.add_parser(
        "doctor", help="Python・REAPER・音源プラグインの環境を確認する"
    )
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser(
        "sync-skills",
        help=".agents/skills（正本）から Claude Code 用の案内 .claude/skills を作り直す",
    )
    s.set_defaults(func=cmd_sync_skills)

    args = p.parse_args(argv)
    try:
        return args.func(args) or 0
    except Exception as e:  # 利用者向けに要点だけ表示する
        if getattr(args, "command", "") and type(e).__name__ in (
            "BatchError",
            "ScoreError",
            "ProjectListError",
            "PipelineError",
            "ProfileError",
        ):
            print(f"エラー: {e}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
