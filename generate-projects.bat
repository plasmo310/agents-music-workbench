@echo off
rem 最新のプロジェクト生成リスト（data\project-lists\）から REAPER プロジェクトを作る。
rem ダブルクリックで実行できる。引数はそのまま渡る（例: generate-projects.bat --profiles reasynth magical8bit）。
rem numpy の入った Python を自動で探す。見つからない場合は環境変数 MUSIC_PYTHON に python.exe のパスを設定する。
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PY="
if defined MUSIC_PYTHON (
  "%MUSIC_PYTHON%" -c "import numpy" >nul 2>&1 && set PY="%MUSIC_PYTHON%"
)
if not defined PY (
  py -3 -c "import numpy" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  python -c "import numpy" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  python3 -c "import numpy" >nul 2>&1 && set "PY=python3"
)
if not defined PY (
  echo numpy の入った Python が見つかりません。
  echo   pip install -r requirements.txt を実行するか、環境変数 MUSIC_PYTHON に python.exe のパスを設定してください。
  set "CODE=1"
  goto :end
)

%PY% python\cli.py project all %*
set "CODE=%ERRORLEVEL%"

echo.
if "%CODE%"=="0" (
  echo 完了しました。試聴カタログ data\library\index.html の「生成済みプロジェクト」タブで確認できます。
) else (
  echo 生成できませんでした（終了コード %CODE%）。上のメッセージと data\projects\^<ジョブ^>\logs\ を確認してください。
)

:end
rem ダブルクリックで開いた場合に結果を読めるよう、ウィンドウを閉じずに待つ
pause
exit /b %CODE%
