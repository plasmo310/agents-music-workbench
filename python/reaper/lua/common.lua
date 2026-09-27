-- REAPER内で動かすスクリプトの共通処理。
-- 利用者が開いているプロジェクトには触れず、新しいプロジェクトタブだけを作成・操作・クローズする。
local M = {}

function M.logger(path)
  local file = assert(io.open(path, 'a'))
  return function(line)
    file:write(tostring(line) .. '\n')
    file:flush()
  end, function() file:close() end
end

-- deferで待つ（コルーチン内から呼ぶ）
function M.settle(seconds)
  local deadline = reaper.time_precise() + seconds
  repeat coroutine.yield() until reaper.time_precise() >= deadline
end

-- worker(say) をコルーチンで実行し、終了時に DONE / ERROR をログへ書く。
function M.run(log_path, worker)
  local say, close = M.logger(log_path)
  local original = reaper.EnumProjects(-1, '')
  local owned = {}
  local ctx = {
    say = say,
    -- 新しいタブを作り、そのプロジェクトを返す
    new_tab = function()
      reaper.Main_OnCommand(40859, 0)
      local project = reaper.EnumProjects(-1, '')
      assert(project ~= original, '新しいプロジェクトタブを作成できませんでした')
      owned[project] = true
      return project
    end,
    -- 現在のタブで rpp を開き直す（自分が作ったタブでのみ呼ぶ）
    reopen = function(project, rpp)
      assert(owned[project], '自分が作成したタブ以外は操作しません')
      reaper.Main_openProject('noprompt:' .. rpp)
      local reopened = reaper.EnumProjects(-1, '')
      owned[reopened] = true
      return reopened
    end,
    close_tab = function(project)
      if project and owned[project] and reaper.EnumProjects(-1, '') == project then
        reaper.Main_OnCommand(40860, 0)
        owned[project] = nil
      end
    end,
  }
  local co = coroutine.create(function() worker(ctx) end)
  local function finish(ok, err)
    if ok then
      say('DONE')
    else
      -- 失敗した作業タブは logs/ に保存し、未保存の変更がなければ閉じる（ファイルのロックを残さない）。
      -- 変更が残る場合は、保存確認ダイアログで止まらないよう開いたままにする。
      local current = reaper.EnumProjects(-1, '')
      if owned[current] then
        local keep = log_path:gsub('%.log$', '_failed.rpp')
        reaper.Main_SaveProjectEx(current, keep, 8)
        if reaper.IsProjectDirty(current) == 0 then
          reaper.Main_OnCommand(40860, 0)
          say('INFO 失敗時の作業タブを ' .. keep .. ' に保存して閉じました')
        else
          say('INFO 失敗時の作業タブはREAPERで開いたままです（保存せずに閉じて構いません）')
        end
      end
      say('ERROR ' .. tostring(err))
    end
    if original and reaper.ValidatePtr(original, 'ReaProject*') then reaper.SelectProjectInstance(original) end
    close()
  end
  local function tick()
    local ok, err = coroutine.resume(co)
    if not ok then
      finish(false, tostring(err) .. '\n' .. debug.traceback(co))
    elseif coroutine.status(co) ~= 'dead' then
      reaper.defer(tick)
    else
      finish(true)
    end
  end
  tick()
end

-- 書式付きの値から数値を取り出す（"3.0 ms" / "+0.00" / "-inf" 等）
local function numeric(text)
  if text:find('inf') then return text:find('-') and -math.huge or math.huge end
  return tonumber(text:match('[-+]?%d*%.?%d+'))
end

local option_cache = {}

-- 1つのFXのパラメーターを名前で設定する補助。設定した値は記録され、再読み込み後の照合に使う。
function M.fx(track, fx, plugin)
  local p = { track = track, index = fx, touched = {}, options = {}, notes = {} }
  local names = {}
  for i = 0, reaper.TrackFX_GetNumParams(track, fx) - 1 do
    local _, name = reaper.TrackFX_GetParamName(track, fx, i, '')
    if names[name] == nil then names[name] = i end
  end
  local function index_of(name)
    return assert(names[name], 'パラメーターが見つかりません: ' .. name .. '（' .. plugin .. '）')
  end
  local function formatted(i)
    local _, text = reaper.TrackFX_GetFormattedParamValue(track, fx, i, '')
    return text
  end
  function p.has(name) return names[name] ~= nil end
  -- 正規化値（0〜1）で設定
  function p.set(name, value)
    local i = index_of(name)
    assert(reaper.TrackFX_SetParamNormalized(track, fx, i, value), '設定に失敗: ' .. name)
    p.touched[i] = true
  end
  -- 表示文字列（例 "Triangle", "25%"）で選択肢を設定。値域を走査して対応する正規化値を探す。
  function p.option(name, text)
    local i = index_of(name)
    local key = plugin .. '|' .. name
    local map = option_cache[key]
    if not map then
      map = {}
      local old = reaper.TrackFX_GetParamNormalized(track, fx, i)
      for step = 0, 256 do
        reaper.TrackFX_SetParamNormalized(track, fx, i, step / 256)
        local shown = formatted(i)
        if map[shown] == nil then map[shown] = step / 256 end
      end
      reaper.TrackFX_SetParamNormalized(track, fx, i, old)
      option_cache[key] = map
    end
    local value = map[text]
    if value == nil then
      local seen = {}
      for k in pairs(map) do seen[#seen + 1] = k end
      error('選択肢 "' .. text .. '" がありません: ' .. name .. '（候補: ' .. table.concat(seen, ', ') .. '）')
    end
    p.set(name, value)
    p.options[i] = text
  end
  -- 表示上の数値（例 Attack 0.002 秒）に最も近い正規化値を二分探索で設定。値が単調増加するパラメーター用。
  function p.number(name, target)
    local i = index_of(name)
    local low, high, best, best_err = 0, 1, 0, math.huge
    for _ = 1, 26 do
      local mid = (low + high) / 2
      reaper.TrackFX_SetParamNormalized(track, fx, i, mid)
      local value = numeric(formatted(i)) or -math.huge
      local err = math.abs(value - target)
      if err < best_err then best, best_err = mid, err end
      if value < target then low = mid else high = mid end
    end
    p.set(name, best)
  end
  function p.note(text) p.notes[#p.notes + 1] = text end
  -- 設定済みパラメーターの記録（名前・正規化値・表示値）
  function p.snapshot()
    local out = {}
    for i in pairs(p.touched) do
      local _, name = reaper.TrackFX_GetParamName(track, fx, i, '')
      out[#out + 1] = { index = i, name = name, normalized = reaper.TrackFX_GetParamNormalized(track, fx, i), formatted = formatted(i) }
    end
    table.sort(out, function(a, b) return a.index < b.index end)
    return out
  end
  function p.check_options()
    for i, text in pairs(p.options) do
      local actual = formatted(i)
      assert(actual == text, '選択肢が反映されていません: ' .. text .. ' -> ' .. actual)
    end
  end
  return p
end

function M.db(value) return 10 ^ (value / 20) end

function M.mkdir(path) reaper.RecursiveCreateDirectory(path, 0) end

-- 直近の設定でレンダーする。既存ファイルがあると上書き確認ダイアログで止まるため、先に削除する。
function M.render(path)
  if M.exists(path) then
    assert(os.remove(path), '既存のファイルを削除できません（他のアプリで開いていないか確認）: ' .. path)
  end
  reaper.Main_OnCommand(42230, 0)
  assert(M.exists(path), 'レンダー結果がありません: ' .. path)
end

function M.exists(path)
  local f = io.open(path, 'rb')
  if f then f:close() return true end
  return false
end

return M
