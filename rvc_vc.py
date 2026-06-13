#!/usr/bin/env python3
"""
芯伴X1 变声器 v2 — WORLD 声码器 + MCEP 平滑 + GV 后滤波

优化 (基于 2026.06 多路学术调研):
  - Harvest F0 提取 (替代 DIO，儿童声更准)
  - N_FFT=2048 (WORLD 48kHz 标准)
  - MCEP 频谱平滑 (消除机器人感)
  - GV 方差后滤波 (恢复谱动态)
  - 抗混叠 + 去直流滤波
  - 自适应频谱融合

预设模式: python3 rvc_vc.py [child|cartoon|deep|robot|whisper|warm|chipmunk|giant]
音色模式: python3 rvc_vc.py --profile <音色名> --text "你好呀"
"""

import subprocess, tempfile, os, sys, wave
import numpy as np
import pyworld as pw
import pysptk

TEXT = "今天天气不错"
DEVICE = "plughw:0,0"
SR = 48000
FRAME_PERIOD = 5.0
F0_FLOOR = 50.0
F0_CEIL = 1200.0
N_FFT = 2048
MCEP_ORDER = 40
MCEP_ALPHA = 0.77


# ─── 分析 / 合成 ──────────────────────────────────────────

def analyze(x, fs):
    """Harvest F0 + CheapTrick + D4C (优化版)"""
    x = x.astype(np.float64)
    f0, t = pw.harvest(x, fs,
                       f0_floor=F0_FLOOR,
                       f0_ceil=F0_CEIL,
                       frame_period=FRAME_PERIOD)
    sp = pw.cheaptrick(x, f0, t, fs, fft_size=N_FFT)
    ap = pw.d4c(x, f0, t, fs, fft_size=N_FFT)
    return f0, sp, ap, t


def synthesize(f0, sp, ap, fs):
    """WORLD 合成 + 后处理"""
    y = pw.synthesize(f0, sp, ap, fs, frame_period=FRAME_PERIOD)
    y = y.astype(np.float64)
    y = _anti_alias(y, fs)
    y = _dc_filter(y, fs)
    return y


def _anti_alias(y, fs, cutoff=20000):
    from scipy.signal import butter, filtfilt
    b, a = butter(4, cutoff / (fs / 2), btype='low')
    return filtfilt(b, a, y)


def _dc_filter(y, fs, cutoff=70):
    from scipy.signal import butter, filtfilt
    b, a = butter(2, cutoff / (fs / 2), btype='high')
    return filtfilt(b, a, y)


# ─── MCEP 频谱平滑 ─────────────────────────────────────────

def mcep_smooth(sp, order=MCEP_ORDER, alpha=MCEP_ALPHA):
    """MCEP 降维重建 → 消除帧间抖动，减少机器人感"""
    n_frames, n_bins = sp.shape
    sp_sm = np.zeros_like(sp)
    for i in range(n_frames):
        mgc = pysptk.sp2mc(sp[i], order=order, alpha=alpha)
        sp_sm[i] = pysptk.mc2sp(mgc, alpha=alpha, fftlen=(n_bins - 1) * 2)
    return sp_sm


# ─── GV 后滤波 ─────────────────────────────────────────────

def gv_postfilter(sp_mod, sp_orig, strength=0.55):
    """全局方差恢复：减轻过度平滑"""
    eps = 1e-8
    gv_orig = np.var(sp_orig, axis=0) + eps
    gv_mod = np.var(sp_mod, axis=0) + eps
    gv_ratio = np.sqrt(gv_orig / gv_mod)
    gv_ratio = np.clip(gv_ratio, 0.7, 1.4)

    blend = 1.0 + (gv_ratio - 1.0) * strength
    sp_mean = np.mean(sp_mod, axis=0)
    return (sp_mod - sp_mean) * blend + sp_mean


# ─── F0 平滑 ───────────────────────────────────────────────

def smooth_f0(f0, window=3):
    from scipy.ndimage import uniform_filter1d
    voiced = f0 > 0
    if voiced.sum() < 3:
        return f0
    f0_sm = f0.copy()
    f0_sm[voiced] = uniform_filter1d(f0_sm[voiced], size=window)
    return f0_sm


# ─── 频谱操控 (预设用) ────────────────────────────────────

def warp_sp(sp, factor):
    n_bins = sp.shape[1]
    old = np.arange(n_bins)
    new = np.clip(old * factor, 0, n_bins - 1)
    out = np.zeros_like(sp)
    for i in range(sp.shape[0]):
        out[i] = np.interp(new, old, sp[i])
    return out


def brighten_sp(sp, amount=0.3):
    return sp + np.linspace(0, amount, sp.shape[1])


def whisper_ap(f0, ap):
    ap_new = np.clip(ap + 20.0, -60, 0)
    f0_new = f0.copy()
    mask = f0_new > 0
    f0_new[mask] = np.random.uniform(80, 180, mask.sum())
    return f0_new, ap_new


def robotize_sp_ap(sp, ap, quantize_bits=6):
    sp_max = sp.max()
    sp_q = np.round(sp / (sp_max / (2 ** quantize_bits))) * (sp_max / (2 ** quantize_bits))
    ap_q = np.round(ap / 10) * 10
    return sp_q, ap_q


# ─── 音色指纹 ──────────────────────────────────────────────

def load_profile(name_or_path):
    import json
    if os.path.exists(name_or_path):
        path = name_or_path
    else:
        profile_dir = os.path.join(os.path.dirname(__file__), "voice_profiles")
        path = os.path.join(profile_dir, f"{name_or_path}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"音色 '{name_or_path}' 不存在")
    with open(path) as f:
        return json.load(f)


# ─── 音色迁移 (优化版) ─────────────────────────────────────

def apply_profile(f0, sp, ap, fs, profile):
    tgt_sp_mean = np.array(profile["sp"]["mean"])
    src_sp_mean = np.mean(sp, axis=0)
    n_bins = sp.shape[1]

    # 对齐 bin 数
    if len(tgt_sp_mean) != n_bins:
        old_idx = np.linspace(0, len(tgt_sp_mean) - 1, len(tgt_sp_mean))
        new_idx = np.linspace(0, len(tgt_sp_mean) - 1, n_bins)
        tgt_sp_mean = np.interp(new_idx, old_idx, tgt_sp_mean)

    eps = 1e-6

    # ── F0 ──
    voiced = f0 > 0
    f0_new = f0.copy()
    if voiced.sum() > 0:
        src_mean = np.mean(f0[voiced])
        scale = profile["f0"]["mean"] / max(src_mean, 1)
        f0_new[voiced] = f0[voiced] * scale
        p5, p95 = profile["f0"]["p5"], profile["f0"]["p95"]
        f0_new[voiced] = np.clip(f0_new[voiced], p5 * 0.7, p95 * 1.3)
        print(f"   🎵 F0: {src_mean:.0f} → {np.mean(f0_new[voiced]):.0f} Hz "
              f"(目标 {profile['f0']['mean']:.0f}Hz)")

    # ── SP 自适应融合 ──
    ratio = (tgt_sp_mean + eps) / (src_sp_mean + eps)
    ratio = np.clip(ratio, 0.2, 5.0)
    log_diff = np.abs(np.log(ratio + eps))
    confidence = np.exp(-log_diff * 0.5)
    blend = 0.85 * confidence
    blend = np.clip(blend, 0.3, 0.95)

    sp_new = sp * (1.0 - blend) + sp * ratio * blend

    # 方差补偿
    src_var = np.var(sp, axis=0)
    tgt_var = np.ones_like(src_var) * np.var(tgt_sp_mean)
    sp_var = np.var(sp_new, axis=0)
    var_ratio = np.clip((tgt_var + eps) / (sp_var + eps), 0.8, 1.5)
    sp_new = (sp_new - np.mean(sp_new, axis=0)) * var_ratio + np.mean(sp_new, axis=0)

    print(f"   🎛️  频谱迁移: 质心偏移 {profile['sp']['centroid']:.0f}")

    # ── AP ──
    tgt_ap = profile["ap"]["mean"]
    src_ap_mean = float(np.nan_to_num(np.mean(ap), nan=-5.0))
    ap_new = ap + np.clip(tgt_ap - src_ap_mean, -10, 10)
    ap_new = np.nan_to_num(ap_new, nan=-5.0)
    print(f"   🌬️  气声: {src_ap_mean:.1f} → {np.mean(ap_new):.1f}dB "
          f"(目标 {tgt_ap:.1f}dB)")

    return f0_new, sp_new, ap_new


# ─── 预设 ──────────────────────────────────────────────────

def apply_preset(f0, sp, ap, fs, preset):
    print(f"   🔊 预设: {preset}")
    if preset == "child":
        print("   👶 儿童声 — F0×1.5 + 共振峰×1.25")
        f0 = f0 * 1.5; sp = warp_sp(sp, 1.25)
    elif preset == "cartoon":
        print("   🐱 卡通声 — F0×1.8 + 共振峰×1.45 + 提亮")
        f0 = f0 * 1.8; sp = warp_sp(sp, 1.45); sp = brighten_sp(sp, 0.25)
    elif preset == "deep":
        print("   🎙️  深沉声 — F0×0.65 + 共振峰×0.72")
        f0 = f0 * 0.65; sp = warp_sp(sp, 0.72)
    elif preset == "robot":
        print("   🤖 机器人 — 频谱量化 + 低通")
        f0 = f0 * 1.15
        sp, ap = robotize_sp_ap(sp, ap, quantize_bits=5)
        cutoff = sp.shape[1] // 3
        sp[:, cutoff:] *= np.linspace(1, 0.05, sp.shape[1] - cutoff)
    elif preset == "whisper":
        print("   🌬️  耳语 — 全气声化")
        f0, ap = whisper_ap(f0, ap)
    elif preset == "warm":
        print("   ☕ 温暖人声 — 低频增强")
        sp = sp + np.linspace(0.15, -0.10, sp.shape[1])
    elif preset == "chipmunk":
        print("   🐿️  花栗鼠 — F0×2.2 + 共振峰×1.6")
        f0 = f0 * 2.2; sp = warp_sp(sp, 1.6)
    elif preset == "giant":
        print("   🦍 巨人声 — F0×0.45 + 共振峰×0.55")
        f0 = f0 * 0.45; sp = warp_sp(sp, 0.55)
    else:
        print(f"   → 直通 ({preset})")
    return f0, sp, ap


# ─── TTS → WORLD ──────────────────────────────────────────

def tts_to_world(text):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        raw = f.name
    try:
        subprocess.run([
            "espeak-ng", "-v", "cmn", "-s", "135", "-p", "50",
            "-a", "75", "-w", raw, text,
        ], check=True, stderr=subprocess.DEVNULL)

        with wave.open(raw, "r") as w:
            nf = w.getnframes()
            nc = w.getnchannels()
            fs_in = w.getframerate()
            pcm = w.readframes(nf)

        samples = np.frombuffer(pcm, dtype=np.int16).astype(float)
        if nc == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)

        if fs_in != SR:
            from scipy.signal import resample_poly
            import fractions
            ratio = fractions.Fraction(SR, fs_in)
            samples = resample_poly(samples, ratio.numerator, ratio.denominator)

        dur = len(samples) / SR
        print(f'\n🎙️  "{text}" ({dur:.1f}s @ {SR}Hz)  → WORLD 声码器')
        f0, sp, ap, t = analyze(samples, SR)

        voiced = f0[f0 > 0]
        if len(voiced) > 0:
            print(f"   📊 源F0: {voiced.min():.0f}-{voiced.max():.0f} Hz "
                  f"({len(t)}帧, N_FFT={N_FFT})")

        return f0, sp, ap
    finally:
        os.unlink(raw)


# ─── 播放 ──────────────────────────────────────────────────

def play_audio(audio, fs, volume=1.0):
    audio = audio * volume
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.98, neginf=-0.98)
    audio = np.clip(audio, -0.98, 0.98)
    out_i16 = (audio * 32767).astype(np.int16)
    stereo = np.column_stack([out_i16, out_i16]).ravel().tobytes()
    print(f"🔊 → {DEVICE}\n")
    proc = subprocess.Popen(
        ["aplay", "-q", "-D", DEVICE, "-f", "S16_LE", "-r", str(fs), "-c", "2"],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = proc.communicate(stereo)
    print("✅ 完成\n" if proc.returncode == 0 else f"❌ {stderr.decode().strip()}\n")


# ─── 主流程 ────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="芯伴X1 变声器 v2")
    parser.add_argument("preset", nargs="?", default="child",
                        help="预设名称")
    parser.add_argument("--profile", "-p", default=None,
                        help="音色指纹名称或路径")
    parser.add_argument("--text", "-t", default=TEXT,
                        help="要说的文本")
    parser.add_argument("--pitch", type=float, default=1.0,
                        help="音高缩放")
    parser.add_argument("--volume", "-v", type=float, default=1.0,
                        help="音量缩放")
    parser.add_argument("--no-gv", action="store_true",
                        help="禁用 GV 后滤波")
    parser.add_argument("--no-mcep", action="store_true",
                        help="禁用 MCEP 平滑")
    args = parser.parse_args()

    print("🎤 芯伴X1 变声器 v2 (Harvest + MCEP + GV)")

    # TTS → WORLD
    f0, sp, ap = tts_to_world(args.text)

    # ── 音色模式 ──
    if args.profile:
        print(f"   🎭 音色模式: {args.profile}")
        profile = load_profile(args.profile)

        print(f"   🎯 目标: F0均值 {profile['f0']['mean']:.0f}Hz, "
              f"浊音比 {profile['voice_ratio']:.0%}")

        # 保存原始 SP (GV 用)
        sp_orig = sp.copy()

        # MCEP 平滑
        if not args.no_mcep:
            print("   🧹 MCEP 平滑 ...")
            sp = mcep_smooth(sp)

        # 音色迁移
        f0_mod, sp_mod, ap_mod = apply_profile(f0, sp, ap, SR, profile)

        # GV 后滤波
        if not args.no_gv:
            print("   📈 GV 后滤波 ...")
            sp_mod = gv_postfilter(sp_mod, sp_orig, strength=0.55)
    else:
        # ── 预设模式 ──
        preset = args.preset
        print(f"   预设: {preset}\n")
        sp_orig = sp.copy()

        if not args.no_mcep:
            sp = mcep_smooth(sp)

        f0_mod, sp_mod, ap_mod = apply_preset(f0, sp, ap, SR, preset)

        if not args.no_gv:
            sp_mod = gv_postfilter(sp_mod, sp_orig, strength=0.5)

        if f0_mod is not None and (f0_mod > 0).sum() > 0:
            print(f"   📊 修改后 F0: {f0_mod[f0_mod>0].min():.0f}-"
                  f"{f0_mod[f0_mod>0].max():.0f} Hz")

    # F0 平滑
    f0_mod = smooth_f0(f0_mod)

    # 音高微调
    if args.pitch != 1.0:
        mask = f0_mod > 0
        old = np.mean(f0_mod[mask]) if mask.sum() > 0 else 0
        f0_mod[mask] *= args.pitch
        new = np.mean(f0_mod[mask]) if mask.sum() > 0 else 0
        print(f"   🎚️  音高: {old:.0f} → {new:.0f} Hz (×{args.pitch:.2f})")

    # 合成
    print("   🔄 合成 + 后处理 ...")
    output = synthesize(f0_mod, sp_mod, ap_mod, SR)
    play_audio(output, SR, volume=args.volume)


if __name__ == "__main__":
    main()
