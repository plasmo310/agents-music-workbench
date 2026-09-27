-- 全曲を見渡すための親プロジェクトを作る。各曲の .rpp をサブプロジェクトとして並べる。
-- 曲ごとにトラックを分け、時間方向には曲を順に並べる（再生すると全曲が順に流れる）。
--   音源が1つ  : 1曲 = 1トラック（トラック名 = 曲名）
--   音源が複数 : 曲のフォルダトラックの中に音源ごとの子トラック。フォルダ内のソロ切り替えで聴き比べられる
-- アイテムをダブルクリックすると、その曲の編集用プロジェクトが開く。
local ARGS = assert(MUSIC_JOB, 'MUSIC_JOB が設定されていません')
local common = dofile(ARGS.lua_dir .. 'common.lua')
local data = dofile(ARGS.data)

local function source_of(item)
  local source = reaper.GetMediaItemTake_Source(reaper.GetActiveTake(item))
  return reaper.GetMediaSourceType(source, ''), reaper.GetMediaSourceFileName(source, '')
end

local function norm(path) return (path:gsub('\\', '/')):lower() end

local function add_track(project, name, depth)
  local index = reaper.CountTracks(project)
  reaper.InsertTrackAtIndex(index, false)
  local track = reaper.GetTrack(project, index)
  reaper.GetSetMediaTrackInfo_String(track, 'P_NAME', name, true)
  reaper.SetMediaTrackInfo_Value(track, 'I_FOLDERDEPTH', depth)
  return track, index
end

-- InsertMedia は「読み込んだメディアをコピー」設定で曲プロジェクトを複製してしまうため、ソースを直接作る。
-- 曲側の =START / =END マーカーの範囲が使われ、プロキシ（.rpp-PROX）は曲フォルダに作られる。
local function add_subproject(track, rpp, entry, take_name)
  local item = reaper.AddMediaItemToTrack(track)
  local take = reaper.AddTakeToMediaItem(item)
  local source = reaper.PCM_Source_CreateFromFile(rpp)
  reaper.SetMediaItemTake_Source(take, source)
  local length = reaper.GetMediaSourceLength(source)
  reaper.SetMediaItemInfo_Value(item, 'D_POSITION', entry.start)
  reaper.SetMediaItemInfo_Value(item, 'D_LENGTH', length > 0 and length or entry.length)
  local kind, file = source_of(item)
  assert(kind == 'RPP_PROJECT', 'サブプロジェクトとして読み込まれていません（' .. kind .. '）: ' .. rpp)
  assert(norm(file) == norm(rpp), '曲プロジェクトが複製されて読み込まれました（REAPER設定「読み込んだメディアをプロジェクトフォルダにコピー」を確認）: ' .. file)
  reaper.GetSetMediaItemTakeInfo_String(take, 'P_NAME', take_name, true)
end

common.run(ARGS.log, function(ctx)
  ctx.say('START overview ' .. #data.entries)
  -- 開かれたままだと、曲のプレビュー音声（.rpp-PROX）が使用中になり作り直せない
  local paths = { data.rpp }
  for _, entry in ipairs(data.entries) do
    for _, rpp in pairs(entry.versions) do paths[#paths + 1] = rpp end
  end
  common.assert_not_open(paths, '全曲まとめまたは曲のプロジェクト')
  local project = ctx.new_tab()
  reaper.SetCurrentBPM(project, 120, false)
  local single = #data.profiles == 1
  local expected = {}  -- 再読み込み後の照合用：{トラック番号, 開始位置, 参照先}
  for idx, entry in ipairs(data.entries) do
    local name = string.format('%02d %s', idx, entry.title)
    local versions = {}
    for _, prof in ipairs(data.profiles) do
      if entry.versions[prof.name] then versions[#versions + 1] = prof end
    end
    if single then
      local track, index = add_track(project, name, 0)
      local prof = versions[1]
      if prof then
        add_subproject(track, entry.versions[prof.name], entry, entry.title .. ' / ' .. prof.label)
        expected[#expected + 1] = { index = index, start = entry.start, rpp = entry.versions[prof.name] }
      end
    else
      local folder = add_track(project, name, #versions > 0 and 1 or 0)
      for k, prof in ipairs(versions) do
        local track, index = add_track(project, prof.label, k == #versions and -1 or 0)
        add_subproject(track, entry.versions[prof.name], entry, entry.title .. ' / ' .. prof.label)
        expected[#expected + 1] = { index = index, start = entry.start, rpp = entry.versions[prof.name] }
      end
    end
    reaper.AddProjectMarker2(project, true, entry.start, entry.start + entry.length, name, -1, 0)
  end
  reaper.GetSetProjectNotes(project, true, data.notes)
  reaper.SetEditCurPos2(project, 0, true, false)
  common.settle(0.5)
  reaper.Main_SaveProjectEx(project, data.rpp, 8)

  project = ctx.reopen(project, data.rpp)
  common.settle(0.5)
  for _, want in ipairs(expected) do
    local track = assert(reaper.GetTrack(project, want.index), '再読み込み後にトラックがありません: ' .. want.index)
    local found
    for i = 0, reaper.CountTrackMediaItems(track) - 1 do
      local item = reaper.GetTrackMediaItem(track, i)
      if math.abs(reaper.GetMediaItemInfo_Value(item, 'D_POSITION') - want.start) < 1e-3 then found = item end
    end
    assert(found, '再読み込み後にアイテムがありません: ' .. want.rpp)
    local kind, file = source_of(found)
    assert(kind == 'RPP_PROJECT' and norm(file) == norm(want.rpp), '参照先が一致しません: ' .. file)
  end
  ctx.say('OVERVIEW items=' .. #expected .. ' tracks=' .. reaper.CountTracks(project) .. ' ' .. data.rpp)
  ctx.close_tab(project)
end)
