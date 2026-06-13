#!/usr/bin/env python3
"""
芯伴X1 音色指纹提取器
从参考录音提取 F0 / 频谱包络 / 非周期分量统计 → JSON 音色文件

用法:
  # 1. 先录音
  arecord -D plughw:0,0 -d 10 -f S16_LE -r 48000 -c 1 my_voice.wav

  # 2. 提取音色指纹
  python3 voice_profile.py my_voice.wav --name "我的声音"

  # 3. 列出已保存的音色
  python3 voice_profile.py --list

  # 4. 用音色说话 (配合 rvc_vc.py)
  python3 rvc_vc.py --profile "我的声音" --text "你好呀"
"""

import json, os, sys, argparse, wave
import numpy as np
import pyworld as pw

SR = 48000
FRAME_PERIOD = 5.0       # ms
N_FFT = 2048              # WORLD 标准 48kHz
PROFILE_DIR = os.path.join(os.path.dirname(__file__), "voice_profiles")
os.makedirs(PROFILE_DIR, exist_ok=True)


# ─── WORLD 分析 ──────────────────────────────────────────────

def world_analyze(x, fs):
    x = x.astype(np.float64)
    f0, t = pw.harvest(x, fs,
                       f0_floor=50.0,
                       f0_ceil=1200.0,
                       frame_period=FRAME_PERIOD)
    sp = pw.cheaptrick(x, f0, t, fs, fft_size=N_FFT)
    ap = pw.d4c(x, f0, t, fs, fft_size=N_FFT)
    return f0, sp, ap


# ─── 音色指纹提取 ────────────────────────────────────────────

def extract_fingerprint(wav_path):
    """从 WAV 提取完整音色指纹"""
    with wave.open(wav_path, "r") as w:
        nf = w.getnframes()
        nc = w.getnchannels()
        fs_in = w.getframerate()
        pcm = w.readframes(nf)

    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    if nc == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)

    # 重采样
    if fs_in != SR:
        from scipy.signal import resample_poly
        import fractions
        ratio = fractions.Fraction(SR, fs_in)
        samples = resample_poly(samples, ratio.numerator, ratio.denominator)
        samples = samples.astype(np.float64)

    duration = len(samples) / SR
    print(f"   📂 {os.path.basename(wav_path)}: {duration:.1f}s @ {SR}Hz")

    # WORLD 分析
    print("   🔍 WORLD 分析 (DIO + CheapTrick + D4C)...")
    f0, sp, ap = world_analyze(samples, SR)

    # ── F0 统计 (仅浊音帧) ──
    voiced = f0[f0 > 0]
    if len(voiced) < 5:
        raise ValueError("浊音帧太少，请录制更长的语音（建议 ≥5 秒）")

    f0_stats = {
        "mean":  float(np.mean(voiced)),
        "median": float(np.median(voiced)),
        "std":   float(np.std(voiced)),
        "min":   float(np.min(voiced)),
        "max":   float(np.max(voiced)),
        "p5":    float(np.percentile(voiced, 5)),
        "p95":   float(np.percentile(voiced, 95)),
    }

    # ── 频谱包络统计 ──
    sp_mean = np.mean(sp, axis=0)         # 平均频谱形状
    sp_std = np.std(sp, axis=0)           # 频谱变化范围

    # 频谱倾斜 (线性拟合 → 斜率)
    n_bins = sp.shape[1]
    freq_axis = np.arange(n_bins)
    tilt_coeffs = np.polyfit(freq_axis, sp_mean, 1)
    spectral_tilt = float(tilt_coeffs[0])

    # 频谱质心
    centroid = float(np.sum(freq_axis * np.abs(sp_mean)) / max(np.sum(np.abs(sp_mean)), 1e-8))

    sp_stats = {
        "mean":     sp_mean.tolist(),
        "std":      sp_std.tolist(),
        "tilt":     spectral_tilt,
        "centroid": centroid,
        "n_bins":   n_bins,
    }

    # ── 非周期分量统计 ──
    ap_mean = float(np.mean(ap))
    ap_std  = float(np.std(ap))

    ap_stats = {
        "mean": ap_mean,
        "std":  ap_std,
    }

    # ── 浊音比例 ──
    voice_ratio = float(len(voiced) / len(f0))

    # 打印摘要
    print(f"   📊 F0: {f0_stats['mean']:.0f}Hz (范围 {f0_stats['min']:.0f}-{f0_stats['max']:.0f})")
    print(f"   📊 频谱质心: bin {centroid:.1f}, 倾斜: {spectral_tilt:.4f}")
    print(f"   📊 气声: {ap_mean:.1f}dB, 浊音比: {voice_ratio:.0%}")

    return {
        "f0":        f0_stats,
        "sp":        sp_stats,
        "ap":        ap_stats,
        "voice_ratio": voice_ratio,
        "duration_sec": duration,
        "sr":        SR,
        "n_fft":     N_FFT,
        "frame_period_ms": FRAME_PERIOD,
    }


# ─── 保存 / 加载 ─────────────────────────────────────────────

def save_profile(name, fingerprint):
    path = os.path.join(PROFILE_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(fingerprint, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 音色已保存: {path}")
    return path


def load_profile(name):
    path = os.path.join(PROFILE_DIR, f"{name}.json")
    if not os.path.exists(path):
        # 尝试直接作为路径
        if os.path.exists(name):
            path = name
        else:
            raise FileNotFoundError(f"音色 '{name}' 不存在 ({path})")
    with open(path, "r") as f:
        return json.load(f)


def list_profiles():
    if not os.path.exists(PROFILE_DIR):
        return []
    profiles = []
    for fn in sorted(os.listdir(PROFILE_DIR)):
        if fn.endswith(".json"):
            path = os.path.join(PROFILE_DIR, fn)
            with open(path) as f:
                fp = json.load(f)
            name = fn[:-5]
            f0 = fp["f0"]["mean"]
            dur = fp.get("duration_sec", "?")
            profiles.append((name, f0, dur, path))
    return profiles


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="芯伴X1 音色指纹提取器")
    parser.add_argument("wav", nargs="?", help="参考音频 WAV 路径")
    parser.add_argument("--name", "-n", default=None, help="音色名称 (默认用文件名)")
    parser.add_argument("--list", "-l", action="store_true", help="列出已保存的音色")
    parser.add_argument("--show", "-s", default=None, help="查看指定音色的参数")
    args = parser.parse_args()

    if args.list:
        profiles = list_profiles()
        if not profiles:
            print("📭 暂无已保存的音色")
        else:
            print(f"🎤 已保存的音色 ({len(profiles)}):\n")
            print(f"  {'名称':<16} {'F0均值':>8} {'时长':>6}  路径")
            print(f"  {'-'*16} {'-'*8} {'-'*6}  {'-'*40}")
            for name, f0, dur, path in profiles:
                print(f"  {name:<16} {f0:>7.0f}Hz {str(dur)+'s':>5}  {path}")
        return

    if args.show:
        fp = load_profile(args.show)
        print(f"🎤 音色: {args.show}")
        print(f"   F0: 均值 {fp['f0']['mean']:.0f}Hz, "
              f"中位数 {fp['f0']['median']:.0f}Hz, "
              f"范围 {fp['f0']['min']:.0f}-{fp['f0']['max']:.0f}Hz")
        print(f"   频谱: 倾斜 {fp['sp']['tilt']:.4f}, 质心 bin {fp['sp']['centroid']:.1f}")
        print(f"   气声: {fp['ap']['mean']:.1f}dB, 浊音比 {fp['voice_ratio']:.0%}")
        print(f"   时长: {fp['duration_sec']:.1f}s")
        return

    if not args.wav:
        parser.print_help()
        return

    name = args.name or os.path.splitext(os.path.basename(args.wav))[0]
    print(f"\n🎤 提取音色指纹: {name}")
    fp = extract_fingerprint(args.wav)
    save_profile(name, fp)


if __name__ == "__main__":
    main()
