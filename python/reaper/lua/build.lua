-- 選択された曲ごとに、音源プロファイル別のREAPERプロジェクトを作成・検証・レンダーする。
-- python python/cli.py project build から、MUSIC_JOB を設定したうえで実行される。
local ARGS = assert(MUSIC_JOB, 'MUSIC_JOB が設定されていません')
local common = dofile(ARGS.lua_dir .. 'common.lua')
local job = dofile(ARGS.job)

local TAIL = 0.35      -- SEの余韻枠（秒）
local RENDER_RATE = 48000
local WAV24 = 'ZXZhdxgAAQ=='  -- WAV / 24-bit PCM

local function by_part(cue)
  local groups = {}
  for _, n in ipairs(cue.notes) do
    groups[n.part] = groups[n.part] or {}
    table.insert(groups[n.part], n)
  end
  return groups
end

local function insert_bend(take, ppq, value)
  value = math.max(0, math.min(16383, math.floor(value + 0.5)))
  reaper.MIDI_InsertCC(take, false, false, ppq, 0xE0, 0, value & 127, value >> 7)
end

local function fill_take(take, start, notes, sec, trim, bend_range)
  for _, n in ipairs(notes) do
    local t0 = start + n.start * sec
    local len = n.dur * sec
    local gate = math.max(0.012, len - trim)
    local a = reaper.MIDI_GetPPQPosFromProjTime(take, t0)
    local b = reaper.MIDI_GetPPQPosFromProjTime(take, t0 + gate)
    assert(reaper.MIDI_InsertNote(take, false, false, a, b, 0, n.pitch, n.vel, true), 'ノートを挿入できません')
    if n.glide ~= 0 and bend_range > 0 then
      local steps = 24
      for s = 0, steps do
        local ppq = a + (b - a) * s / steps
        insert_bend(take, ppq, 8192 + n.glide / bend_range * 8191 * s / steps)
      end
      insert_bend(take, b + 1, 8192)
    end
  end
  reaper.MIDI_Sort(take)
end

local function build(ctx, cue, name, def)
  local out = ARGS.job_root .. '/' .. cue.name .. '/' .. name
  local rpp = out .. '/' .. cue.name .. '_' .. name .. '.rpp'
  if not ARGS.force and common.exists(out .. '/preview.wav') and common.exists(rpp) then
    ctx.say('SKIP ' .. cue.key .. ' ' .. name .. '（制作済み）')
    return
  end
  common.mkdir(out)
  local project = ctx.new_tab()
  local sec = 60 / cue.tempo
  reaper.SetCurrentBPM(project, cue.tempo, false)
  reaper.SetTempoTimeSigMarker(project, -1, 0, -1, -1, cue.tempo, cue.meter_num, cue.meter_den, false)

  local groups = by_part(cue)
  local settings = assert(io.open(out .. '/sound_settings.tsv', 'w'))
  settings:write('track\trole\tparameter\tnormalized\tformatted\n')
  local expected, note_total = {}, 0
  local passes = cue.loop and 3 or 1
  for ti, part in ipairs(cue.parts) do
    local notes = groups[part.name]
    reaper.InsertTrackAtIndex(ti - 1, false)
    local tr = reaper.GetTrack(project, ti - 1)
    reaper.GetSetMediaTrackInfo_String(tr, 'P_NAME', part.name .. ' / ' .. part.voices[1], true)
    local pan = 0
    for _, n in ipairs(notes) do pan = pan + n.pan end
    reaper.SetMediaTrackInfo_Value(tr, 'D_PAN', pan / #notes)
    local t = { part = part.name, role = part.role, voice = part.voices[1], voices = part.voices,
                loop = cue.loop, bend_range = part.bend_range, cue = cue }
    local gain = def.track_gain and def.track_gain(t) or 0.35
    reaper.SetMediaTrackInfo_Value(tr, 'D_VOL', gain * common.db(part.mix_db))

    local fx = reaper.TrackFX_AddByName(tr, def.plugin, false, -1)
    assert(fx >= 0, 'プラグインを読み込めません: ' .. def.plugin .. '（インストール・REAPERのプラグインスキャンを確認）')
    local p = common.fx(tr, fx, def.plugin)
    def.configure(p, t)
    if part.bend_range > 0 then
      if def.bend then def.bend(p, part.bend_range)
      else ctx.say('WARN ' .. cue.key .. ' ' .. name .. ' ' .. part.name .. ': この音源ではベンド幅を自動設定できません（滑音の幅が変わる可能性）') end
    end
    common.settle(0.25)
    p.check_options()
    expected[ti] = p.snapshot()
    for _, s in ipairs(expected[ti]) do
      settings:write(part.name .. '\t' .. part.role .. '\t' .. s.name .. '\t' .. s.normalized .. '\t' .. s.formatted .. '\n')
    end
    for _, text in ipairs(p.notes) do settings:write(part.name .. '\t' .. part.role .. '\t#\t\t' .. text .. '\n') end

    local role_trim = part.role == 'drum' and (def.gate_trim_drum or 0.01) or (def.gate_trim or 0.025)
    for rep = 0, passes - 1 do
      local start = rep * cue.duration
      local len = cue.loop and cue.duration or (cue.duration + TAIL)
      local item = reaper.CreateNewMIDIItemInProj(tr, start, start + len, false)
      local take = reaper.GetActiveTake(item)
      reaper.GetSetMediaItemTakeInfo_String(take, 'P_NAME', part.name .. (cue.loop and (' - ' .. (rep + 1) .. '周目') or ''), true)
      fill_take(take, start, notes, sec, role_trim, part.bend_range)
    end
    note_total = note_total + #notes * passes
  end
  settings:close()

  -- ループ曲は3周並べ、中央の1周を再生・ループ・レンダー範囲にする。SEは余韻枠込み。
  local r0 = cue.loop and cue.duration or 0
  local r1 = cue.loop and cue.duration * 2 or cue.duration + TAIL
  reaper.GetSet_LoopTimeRange2(project, true, true, r0, r1, false)
  reaper.GetSet_LoopTimeRange2(project, true, false, r0, r1, false)
  reaper.GetSetRepeatEx(project, cue.loop and 1 or 0)
  reaper.AddProjectMarker2(project, true, r0, r1, cue.loop and 'LOOP（中央の1周を編集・書き出し）' or 'ONE SHOT', -1, 0)
  -- サブプロジェクトとして読み込まれたときに使う範囲
  reaper.AddProjectMarker2(project, false, r0, 0, '=START', -1, 0)
  reaper.AddProjectMarker2(project, false, r1, 0, '=END', -1, 0)
  reaper.SetEditCurPos2(project, r0, false, false)
  reaper.GetSetProjectNotes(project, true, table.concat({
    cue.title, '元の曲: ' .. cue.key, '音源: ' .. def.label,
    cue.loop and 'ループ曲: 3周配置。中央の1周が再生・書き出し範囲。各周は独立したMIDIアイテム。' or 'SE: 0.35秒の余韻枠つき。',
    '音符は編集可能なMIDIとして埋め込み済み。音源のリリースと重ならないようゲートを短縮しています（共通MIDIは元の長さ）。',
    'プレビューWAVとは音色が異なります（音源による再アレンジ）。',
  }, '\n'))
  for key, value in pairs({ RENDER_SETTINGS = 0, RENDER_BOUNDSFLAG = 0, RENDER_STARTPOS = r0, RENDER_ENDPOS = r1,
      RENDER_SRATE = RENDER_RATE, RENDER_CHANNELS = 2, RENDER_TAILFLAG = 0, RENDER_DITHER = 0, RENDER_ADDTOPROJ = 0,
      RENDER_NORMALIZE = 0, RENDER_FADEIN = 0, RENDER_FADEOUT = 0 }) do
    reaper.GetSetProjectInfo(project, key, value, true)
  end
  reaper.GetSetProjectInfo_String(project, 'RENDER_FILE', out, true)
  reaper.GetSetProjectInfo_String(project, 'RENDER_PATTERN', 'preview', true)
  reaper.GetSetProjectInfo_String(project, 'RENDER_FORMAT', WAV24, true)
  reaper.GetSetProjectInfo_String(project, 'RENDER_FORMAT2', '', true)
  common.settle(0.4)
  reaper.Main_SaveProjectEx(project, rpp, 8)

  -- 保存したファイルを開き直し、音源・音色・ノート数が残っているか確認してからレンダーする
  project = ctx.reopen(project, rpp)
  common.settle(0.3)
  assert(reaper.CountTracks(project) == #cue.parts, '再読み込み後のトラック数が一致しません')
  local count = 0
  for ti, part in ipairs(cue.parts) do
    local tr = reaper.GetTrack(project, ti - 1)
    local fx = reaper.TrackFX_GetInstrument(tr)
    assert(fx >= 0 and not reaper.TrackFX_GetOffline(tr, fx), '再読み込み後に音源がロードされていません: ' .. part.name)
    for _, want in ipairs(expected[ti]) do
      local _, actual = reaper.TrackFX_GetFormattedParamValue(tr, fx, want.index, '')
      assert(actual == want.formatted, '音色設定が保存されていません ' .. part.name .. ' ' .. want.name .. ': ' .. want.formatted .. ' -> ' .. actual)
    end
    for j = 0, reaper.CountTrackMediaItems(tr) - 1 do
      local take = reaper.GetActiveTake(reaper.GetTrackMediaItem(tr, j))
      assert(reaper.TakeIsMIDI(take), 'MIDIアイテムではありません')
      local _, notes = reaper.MIDI_CountEvts(take)
      count = count + notes
    end
  end
  assert(count == note_total, 'MIDIノート数が一致しません: ' .. count .. ' / ' .. note_total)
  ctx.say('RELOADED ' .. cue.key .. ' ' .. name .. ' notes=' .. count)
  common.render(out .. '/preview.wav')
  reaper.Main_SaveProjectEx(project, rpp, 8)
  ctx.say('RENDERED ' .. cue.key .. ' ' .. name)
  ctx.close_tab(project)
end

common.run(ARGS.log, function(ctx)
  ctx.say('START build stage=' .. ARGS.stage .. ' REAPER ' .. reaper.GetAppVersion())
  local defs = {}
  for _, name in ipairs(job.profiles) do defs[name] = dofile(ARGS.lua_dir .. 'profiles/' .. name .. '.lua') end
  for index, cue in ipairs(job.cues) do
    local wanted = ARGS.stage == 'all' or (ARGS.stage == 'pilot' and index == 1) or (ARGS.stage == 'remaining' and index > 1)
    if wanted then
      for _, name in ipairs(job.profiles) do build(ctx, cue, name, defs[name]) end
    end
  end
end)
