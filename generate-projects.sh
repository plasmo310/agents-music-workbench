#!/usr/bin/env bash
# 最新のプロジェクト生成リスト（data/project-lists/）から REAPER プロジェクトを作る（macOS / Linux 用）。
# 引数はそのまま渡る（例: ./generate-projects.sh --profiles reasynth magical8bit）。
# numpy の入った Python を自動で探す。見つからない場合は環境変数 MUSIC_PYTHON に python のパスを設定する。
set -u
cd "$(dirname "$0")"

PY=""
for candidate in "${MUSIC_PYTHON:-}" python3 python; do
  if [ -n "$candidate" ] && "$candidate" -c "import numpy" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "numpy の入った Python が見つかりません。"
  echo "  pip install -r requirements.txt を実行するか、環境変数 MUSIC_PYTHON に python のパスを設定してください。"
  exit 1
fi

"$PY" python/cli.py project all "$@"
code=$?
echo
if [ "$code" -eq 0 ]; then
  echo "完了しました。試聴カタログ data/library/index.html の「生成済みプロジェクト」タブで確認できます。"
else
  echo "生成できませんでした（終了コード $code）。上のメッセージと data/projects/<ジョブ>/logs/ を確認してください。"
fi
exit "$code"
