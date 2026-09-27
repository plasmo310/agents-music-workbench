-- 全曲を見渡すための親プロジェクトを作る。各曲の .rpp をサブプロジェクトとして並べる。
-- トラック = 音源プロファイル。同じ曲の各音源版は同じ時刻に置き、ソロの切り替えで聴き比べられる。
-- アイテムをダブルクリックすると、その曲の編集用プロジェクトが開く。
local ARGS = assert(MUSIC_JOB, 'MUSIC_JOB が設定されていません')
local common = dofile(ARGS.lua_dir .. 'common.lua')
local data = dofile(ARGS.data)

local function item_at(track, position)
  for i = 0, reaper.CountTrackMediaItems(track) - 1 do
    local item = reaper.GetTrackMediaItem(track, i)
    if math.abs(reaper.GetMediaItemInfo_Value(item, 'D_POSITION') - position) < 1e-3 then return item end
  end
end

local function source_of(item)
  local source = reaper.GetMediaItemTake_Source(reaper.GetActiveTake(item))
  return reaper.GetMediaSourceType(source, ''), reaper.GetMediaSourceFileName(source, '')
end

local function norm(path) return (path:gsub('\\', '/')):lower() end

common.run(ARGS.log, function(ctx)
  ctx.say('START overview ' .. #data.entries)
  local project = ctx.new_tab()
  reaper.SetCurrentBPM(project, 120, false)
  local tracks = {}
  for i, prof in ipairs(data.profiles) do
    reaper.InsertTrackAtIndex(i - 1, false)
    tracks[i] = reaper.GetTrack(project, i - 1)
    reaper.GetSetMediaTrackInfo_String(tracks[i], 'P_NAME', prof.label, true)
  end
  local expected = 0
  for idx, entry in ipairs(data.entries) do
    for i, prof in ipairs(data.profiles) do
      local rpp = entry.versions[prof.name]
      if rpp then
        -- InsertMedia は「読み込んだメディアをコピー」設定で曲プロジェクトを複製してしまうため、ソースを直接作る。
        -- 曲側の =START / =END マーカーの範囲が使われ、プロキシ（.rpp-PROX）は曲フォルダに作られる。
        local item = reaper.AddMediaItemToTrack(tracks[i])
        local take = reaper.AddTakeToMediaItem(item)
        local source = reaper.PCM_Source_CreateFromFile(rpp)
        reaper.SetMediaItemTake_Source(take, source)
        local length = reaper.GetMediaSourceLength(source)
        reaper.SetMediaItemInfo_Value(item, 'D_POSITION', entry.start)
        reaper.SetMediaItemInfo_Value(item, 'D_LENGTH', length > 0 and length or entry.length)
        local kind, file = source_of(item)
        assert(kind == 'RPP_PROJECT', 'サブプロジェクトとして読み込まれていません（' .. kind .. '）: ' .. rpp)
        assert(norm(file) == norm(rpp), '曲プロジェクトが複製されて読み込まれました（REAPER設定「読み込んだメディアをプロジェクトフォルダにコピー」を確認）: ' .. file)
        reaper.GetSetMediaItemTakeInfo_String(reaper.GetActiveTake(item), 'P_NAME', entry.title .. ' / ' .. prof.label, true)
        expected = expected + 1
      end
    end
    reaper.AddProjectMarker2(project, true, entry.start, entry.start + entry.length, string.format('%02d %s', idx, entry.title), -1, 0)
  end
  reaper.GetSetProjectNotes(project, true, data.notes)
  reaper.SetEditCurPos2(project, 0, true, false)
  common.settle(0.5)
  reaper.Main_SaveProjectEx(project, data.rpp, 8)

  project = ctx.reopen(project, data.rpp)
  common.settle(0.5)
  local found = 0
  for i, prof in ipairs(data.profiles) do
    local tr = reaper.GetTrack(project, i - 1)
    for _, entry in ipairs(data.entries) do
      local rpp = entry.versions[prof.name]
      if rpp then
        local item = assert(item_at(tr, entry.start), '再読み込み後にアイテムがありません: ' .. entry.title .. ' / ' .. prof.label)
        local kind, file = source_of(item)
        assert(kind == 'RPP_PROJECT' and norm(file) == norm(rpp), '参照先が一致しません: ' .. file)
        found = found + 1
      end
    end
  end
  assert(found == expected, 'サブプロジェクト数が一致しません: ' .. found .. ' / ' .. expected)
  ctx.say('OVERVIEW items=' .. found .. ' ' .. data.rpp)
  ctx.close_tab(project)
end)
