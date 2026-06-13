#!/usr/bin/env python3
"""
芯伴X1 TTS — edge-tts 高质量语音合成
无需变声，直接用微软神经语音，零机械感

用法:
  python3 tts_speak.py "小朋友你好"
  python3 tts_speak.py --voice xiaoxiao "今天天气真好"
  python3 tts_speak.py --list   # 列出可用中文声音
"""

import asyncio, edge_tts, sys, os, tempfile, subprocess

VOICES = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",    # 温暖活泼女声 ★推荐
    "xiaoyi":   "zh-CN-XiaoyiNeural",      # 轻柔治愈女声
    "yunyang":  "zh-CN-YunyangNeural",     # 专业男声
    "yunxi":    "zh-CN-YunxiNeural",       # 阳光男声
    "xiaobei":  "zh-CN-liaoning-XiaobeiNeural",  # 东北话女声
    "xiaoni":   "zh-CN-shaanxi-XiaoniNeural",    # 陕西话女声
    "yunjian":  "zh-CN-YunjianNeural",     # 成熟男声
    "xiaoxuan": "zh-CN-XiaoxuanNeural",    # 知性女声
}


async def speak(text, voice="xiaoxiao", out_mp3=None):
    short = VOICES.get(voice, voice)
    tts = edge_tts.Communicate(text, short)
    if out_mp3 is None:
        out_mp3 = tempfile.mktemp(suffix=".mp3", prefix="tts_")
    await tts.save(out_mp3)
    return out_mp3


def play(mp3_path, volume=1.0):
    """ffplay 播放，volume>1.0 可软件放大"""
    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
    if volume != 1.0:
        cmd += ["-af", f"volume={volume:.1f}"]
    cmd.append(mp3_path)
    subprocess.run(cmd, timeout=30)


async def list_voices():
    voices = await edge_tts.list_voices()
    zh = [v for v in voices if 'zh-CN' in v['Locale']]
    print(f"\n🎤 可用中文语音 ({len(zh)}):\n")
    for v in zh:
        print(f"  {v['ShortName']:<35} {v['Gender']:<8} {v['Locale']}")
    print(f"\n💡 预设别名: {', '.join(VOICES.keys())}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="芯伴X1 TTS — edge-tts 高质量语音")
    parser.add_argument("text", nargs="*", default=["你好"], help="要说的文本")
    parser.add_argument("--voice", "-v", default="xiaoxiao", help="语音别名")
    parser.add_argument("--volume", type=float, default=1.0, help="音量倍数 (1=正常, 3=三倍)")
    parser.add_argument("--list", "-l", action="store_true", help="列出可用声音")
    args = parser.parse_args()

    if args.list:
        await list_voices()
        return

    text = " ".join(args.text)
    name = VOICES.get(args.voice, args.voice)

    vol_str = f"  (音量×{args.volume:.0f})" if args.volume != 1.0 else ""
    print(f"🎤 {name}{vol_str}")
    print(f"💬 {text}")

    mp3 = await speak(text, args.voice)
    print("🔊 播放中...")
    play(mp3, volume=args.volume)
    os.unlink(mp3)


if __name__ == "__main__":
    asyncio.run(main())
