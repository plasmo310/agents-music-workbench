-- 音源版どうしの音量差で比較が偏らないよう、各プロジェクトのマスター音量を合わせて preview_matched.wav を書き出す。
-- ゲインは Python 側（level.py）が preview.wav を解析して決め、MUSIC_JOB.data に渡す。
local ARGS = assert(MUSIC_JOB, 'MUSIC_JOB が設定されていません')
local common = dofile(ARGS.lua_dir .. 'common.lua')
local items = dofile(ARGS.data)

common.run(ARGS.log, function(ctx)
  ctx.say('START level_match ' .. #items)
  -- 曲のプロジェクトや全曲まとめが開かれていると、保存時のプレビュー音声（.rpp-PROX）の作り直しで止まる
  for _, job in ipairs(items) do
    common.assert_not_open({ job.rpp, job.overview }, '音量を合わせるプロジェクトまたは全曲まとめ')
  end
  for _, job in ipairs(items) do
    local project = ctx.reopen(ctx.new_tab(), job.rpp)
    common.settle(0.25)
    local master = reaper.GetMasterTrack(project)
    reaper.SetMediaTrackInfo_Value(master, 'D_VOL', job.gain)
    assert(math.abs(reaper.GetMediaTrackInfo_Value(master, 'D_VOL') - job.gain) < 1e-5, 'マスター音量を設定できません')
    reaper.GetSetProjectInfo_String(project, 'RENDER_PATTERN', 'preview_matched', true)
    reaper.Main_SaveProjectEx(project, job.rpp, 8)

    project = ctx.reopen(project, job.rpp)
    common.settle(0.25)
    assert(math.abs(reaper.GetMediaTrackInfo_Value(reaper.GetMasterTrack(project), 'D_VOL') - job.gain) < 1e-5, 'マスター音量が保存されていません')
    local notes = 0
    for ti = 0, reaper.CountTracks(project) - 1 do
      local tr = reaper.GetTrack(project, ti)
      local fx = reaper.TrackFX_GetInstrument(tr)
      assert(fx >= 0 and not reaper.TrackFX_GetOffline(tr, fx), '再読み込み後に音源がありません')
      for i = 0, reaper.CountTrackMediaItems(tr) - 1 do
        local take = reaper.GetActiveTake(reaper.GetTrackMediaItem(tr, i))
        assert(reaper.TakeIsMIDI(take), '編集できないアイテムがあります')
        local _, n = reaper.MIDI_CountEvts(take)
        notes = notes + n
      end
    end
    common.render(job.folder .. '/preview_matched.wav')
    reaper.Main_SaveProjectEx(project, job.rpp, 8)
    ctx.say(string.format('MATCHED %s %s gain=%.4f notes=%d', job.key, job.profile, job.gain, notes))
    ctx.close_tab(project)
  end
end)
