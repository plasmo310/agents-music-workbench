-- Magical 8bit Plug 2（YMCK）用の音源プロファイル。
-- パルス系リード、三角波系ベース、短いアルペジオ、ノイズ系打楽器を出発点に、パートの役割から音色を作る。
-- パラメーター名・選択肢はバージョン 2.x を REAPER 上で確認したもの。
local TRIANGLE = { triangle = true, chipflute = true, softchip = true, bass = true, flute = true }
local NOISE_DRUM = { snare = true, hat = true, clap = true, noise = true }

return {
  label = 'Magical 8bit Plug 2',
  plugin = 'VST3i: Magical 8bit Plug 2 (Ymck)',
  gate_trim = 0.025,
  gate_trim_drum = 0.01,

  track_gain = function(t)
    if t.role == 'drum' and NOISE_DRUM[t.voice] then return 0.25 end
    return 0.4
  end,

  -- p: 名前で設定する補助（set=正規化値 / option=表示文字列 / number=表示数値）
  -- t: { part, role, voice, voices, loop, bend_range, cue }
  configure = function(p, t)
    local drum, bass, pad, arp = t.role == 'drum', t.role == 'bass', t.role == 'pad', t.role == 'arp'
    local noise = drum and NOISE_DRUM[t.voice]
    local bell = t.voice == 'chipbell' or t.voice == 'bell' or t.voice == 'glass'
    p.set('Gain', 0.35)
    p.number('Max Poly', 8)
    p.option('Behavior', 'Non-legato')
    if noise then
      p.option('OSC Type', 'Noise')
    elseif bass or pad or TRIANGLE[t.voice] or t.voice == 'kick' or t.voice == 'tom' then
      p.option('OSC Type', 'Triangle')
    else
      p.option('OSC Type', 'Pulse/Square')
    end
    local duty = (t.voice == 'pulse') and '25%' or (t.voice == 'pulse12' or bell) and '12.5%' or '50%'
    p.option('Duty', duty)
    p.number('Attack', pad and 0.03 or 0.002)
    p.number('Decay', drum and (t.voice == 'hat' and 0.023 or 0.06) or arp and 0.10 or bell and 0.17 or 0.13)
    p.set('Sustain', drum and 0 or pad and 0.55 or bass and 0.65 or arp and 0.17 or bell and 0.08 or 0.48)
    p.number('Release', drum and 0.014 or arp and 0.028 or pad and 0.12 or 0.05)
    if t.voice == 'kick' or t.voice == 'tom' then
      p.number('Ini.Pitch', t.voice == 'kick' and 12 or 7)
      p.number('Time', 0.045)
    end
    if t.role == 'lead' and (t.voice == 'pulse' or t.voice == 'square') then
      p.set('Depth', 0.025)  -- 軽いビブラート
      p.number('Delay', 0.18)
    end
  end,

  -- 滑音（glide）があるパートはピッチベンドを受け付け、幅をMIDIと一致させる
  bend = function(p, range)
    p.option('Ignores Wheel', 'Off')
    p.number('Bend Range', range)
  end,
}
