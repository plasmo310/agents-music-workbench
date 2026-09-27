-- Native Instruments MASSIVE 用の音源プロファイル（MASSIVE X ではありません）。
-- 同じフレーズの役割に合わせ、リード・プラック・ベース・パッド・ノイズ打楽器を個別に設計する。
-- パラメーター名・選択肢は MASSIVE 1.5 を REAPER 上で確認したもの。
local NOISE_DRUM = { snare = true, hat = true, clap = true, noise = true }

return {
  label = 'MASSIVE',
  plugin = 'VST3i: Massive (Native Instruments)',
  gate_trim = 0.025,
  gate_trim_drum = 0.01,

  track_gain = function(t)
    if t.role == 'drum' and NOISE_DRUM[t.voice] then return 0.25 end
    return 0.4
  end,

  configure = function(p, t)
    local drum, bass, pad, arp = t.role == 'drum', t.role == 'bass', t.role == 'pad', t.role == 'arp'
    local v = t.voice
    p.set('OSC1-AMP', 0.75); p.set('OSC2-AMP', 0); p.set('OSC3-AMP', 0); p.set('NOISE-AMP', 0)

    local wavetable = 'Squ-Sw I'
    if bass or v == 'kick' or v == 'tom' or v == 'triangle' or v == 'chipflute' or v == 'flute' then wavetable = 'Sin-Tri' end
    if v == 'chipbell' or v == 'bell' or v == 'glass' or v == 'vibes' then wavetable = 'Additiv I' end
    if arp or v == 'chippluck' or v == 'pluck' or v == 'guitar' or v == 'marimba' then wavetable = 'Woody' end
    if v == 'fm' or v == 'ep' then wavetable = 'Sinarm I' end
    p.option('OSC1-WAVETABLE', wavetable)
    p.set('OSC1-POSITION', bass and 0.12 or arp and 0.28 or wavetable == 'Additiv I' and 0.19 or 0.38)
    p.set('OSC1-FLT.ROUTING', 0)
    p.set('FILTER-1/2-CROSSFADE', 0)
    p.option('FILTER1-TYPE', v == 'hat' and 'Highpass 2' or 'Lowpass 4')
    p.set('FILTER1-CUT/PRM.1', v == 'hat' and 0.62 or bass and 0.43 or arp and 0.64 or pad and 0.55 or 0.7)
    p.set('FILTER1-RES/PRM.3', bass and 0.12 or 0.06)
    if drum and NOISE_DRUM[v] then
      p.set('OSC1-AMP', v == 'snare' and 0.10 or 0)
      p.set('NOISE-AMP', 0.65)
      p.set('NOISE-COLOR', v == 'hat' and 0.87 or 0.48)
      p.set('NOISE-FLTR. ROUTING', 0)
    end
    -- ENVELOPE4 がアンプエンベロープ
    p.set('ENVELOPE4-ATT.TME', pad and 0.24 or 0.005)
    p.set('ENVELOPE4-DEC.TME', drum and (v == 'hat' and 0.09 or 0.19) or arp and 0.28 or 0.36)
    p.set('ENVELOPE4-DEC.LEV', drum and 0 or arp and 0.12 or bass and 0.65 or pad and 0.7 or 0.45)
    p.set('ENVELOPE4-SUST.LEV', drum and 0 or arp and 0.12 or bass and 0.65 or pad and 0.7 or 0.45)
    p.set('ENVELOPE4-REL. TME', drum and 0.025 or arp and 0.055 or pad and 0.2 or 0.085)
    p.set('ENVELOPE4-VELOCITY', 0.55)
    p.set('MASTER-VOLUME', 0.42)
    if not drum and not bass then
      p.option('MASTER FX1-TYPE', 'Reverb Sm')
      p.set('MASTER FX1-DRY WET', t.loop and 0.10 or 0.065)
      p.set('MASTER FX1-PRM.2', 0.22)
      p.set('MASTER FX1-PRM.3', 0.35)
    end
  end,
  -- MASSIVE のベンド幅はホストのパラメーターとして公開されていないため自動設定しない
}
