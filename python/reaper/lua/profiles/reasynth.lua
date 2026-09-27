-- ReaSynth（REAPER標準）用の音源プロファイル。
-- 追加の音源がなくても流れ全体を試せるようにするためのもの。音色は簡素。
local NOISE_DRUM = { snare = true, hat = true, clap = true, noise = true }

return {
  label = 'ReaSynth',
  plugin = 'VSTi: ReaSynth (Cockos)',
  gate_trim = 0.02,
  gate_trim_drum = 0.01,

  track_gain = function(t)
    if t.role == 'drum' and NOISE_DRUM[t.voice] then return 0.2 end
    return 0.5
  end,

  configure = function(p, t)
    local drum, bass, pad, arp = t.role == 'drum', t.role == 'bass', t.role == 'pad', t.role == 'arp'
    local v = t.voice
    p.number('Volume', -6)
    p.set('Square mix', 0); p.set('Saw mix', 0); p.set('Triangle mix', 0); p.set('Extra sine mix', 0)
    if bass or pad or v == 'triangle' or v == 'flute' or v == 'chipflute' or v == 'kick' or v == 'tom' then
      p.set('Triangle mix', 1)
    elseif v == 'saw' or v == 'brass' or v == 'strings' then
      p.set('Saw mix', 0.8)
    elseif v == 'pulse' or v == 'pulse12' or v == 'square' then
      p.set('Square mix', 0.8)
      p.number('Pulse Width', v == 'square' and 0.5 or v == 'pulse' and 0.25 or 0.125)
    else
      p.set('Extra sine mix', 0.8); p.set('Triangle mix', 0.4)  -- ベル・プラック系
    end
    -- ReaSynth にノイズ源はないため、打楽器は短い音程感のある音で代用する
    p.number('Attack', pad and 40 or 2)
    p.number('Decay', drum and (v == 'hat' and 25 or 70) or arp and 120 or 250)
    p.number('Sustain', (drum or arp) and -60 or pad and -3 or bass and -4 or -8)
    p.number('Release', drum and 15 or pad and 180 or 60)
    if drum and NOISE_DRUM[v] then p.note('ノイズ源がないため音程のある短音で代用') end
  end,
}
