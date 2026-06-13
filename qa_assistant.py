#!/usr/bin/env python3
"""
芯伴X1 问答助手 — 语音提问 → LLM百科回答 → 语音播报

用法:
  python3 qa_assistant.py              # 语音提问模式
  python3 qa_assistant.py --text "太阳有多大"   # 文字提问模式
  python3 qa_assistant.py --loop       # 连续对话模式 (Ctrl+C 退出)
"""

import asyncio, edge_tts, sys, os, tempfile, subprocess, json, wave
import requests
import speech_recognition as sr


# ═══ 配置 ═══════════════════════════════════════════════════

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"
TTS_VOICE = "zh-CN-XiaoxiaoNeural"
RECORD_SECS = 6

SYSTEM_PROMPT = (
    "你是小芯，一个运行在SC171开发板上的AI桌面伙伴，专为儿童和学生设计。"
    "你的回答要：\n"
    "1. 像百度百科一样准确、有知识含量\n"
    "2. 但语气轻松活泼，像朋友聊天，不要死板的百科腔\n"
    "3. 控制在3-5句话，简洁明了\n"
    "4. 适当使用'哇''好问题''让我想想'等口语化表达\n"
    "5. 中文回答，适合小朋友理解"
)


# ═══ ASR 语音识别 ════════════════════════════════════════════

def record_and_recognize(duration=RECORD_SECS) -> str:
    """录音 → Google ASR → 文本"""
    r = sr.Recognizer()
    with sr.Microphone(sample_rate=16000) as source:
        print("🎤 正在听... (请说话)")
        r.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = r.listen(source, timeout=duration, phrase_time_limit=duration)
        except sr.WaitTimeoutError:
            print("⏱ 未检测到语音")
            return ""

    print("🧠 识别中...")
    try:
        text = r.recognize_google(audio, language="zh-CN")
        print(f"💬 你说: {text}")
        return text.strip()
    except sr.UnknownValueError:
        print("🤷 没听清")
        return ""
    except sr.RequestError:
        print("🌐 网络不可用，试试文字输入")
        return ""


# ═══ LLM 问答 ═══════════════════════════════════════════════

def ask_llm(question: str) -> str:
    """DeepSeek API 百科问答"""
    if not API_KEY:
        return "API密钥未配置，请在环境变量设置 ANTHROPIC_API_KEY"

    print("💭 思考中...")
    try:
        resp = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                "max_tokens": 400,
                "temperature": 0.7,
            },
            timeout=15
        )
        if resp.status_code == 200:
            answer = resp.json()["choices"][0]["message"]["content"].strip()
            print(f"🤖 {answer}")
            return answer
        else:
            return f"抱歉，服务异常 ({resp.status_code})"
    except requests.Timeout:
        return "思考超时了，请再问一次"
    except Exception as e:
        return f"出错了: {e}"


# ═══ TTS 播报 ═══════════════════════════════════════════════

async def speak(text: str, voice=TTS_VOICE):
    mp3 = tempfile.mktemp(suffix=".mp3", prefix="qa_")
    tts = edge_tts.Communicate(text, voice)
    await tts.save(mp3)
    print("🔊 播报中...\n")
    subprocess.run(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", mp3],
        timeout=30)
    os.unlink(mp3)


# ═══ 主流程 ═════════════════════════════════════════════════

async def qa_round(question: str = None):
    """一轮问答"""
    if question is None:
        question = record_and_recognize()
        if not question:
            return

    answer = ask_llm(question)
    if answer:
        await speak(answer)


async def text_mode(text: str):
    """文字输入模式"""
    print(f"💬 {text}")
    answer = ask_llm(text)
    if answer:
        await speak(answer)


async def loop_mode():
    """连续对话模式"""
    print("🔄 连续问答模式 (Ctrl+C 退出)\n")
    while True:
        try:
            question = record_and_recognize()
            if question:
                if any(w in question for w in ["退出", "拜拜", "再见", "不问了"]):
                    await speak("好的，有需要随时叫我哦！")
                    print("👋 再见!")
                    break
                answer = ask_llm(question)
                if answer:
                    await speak(answer)
            print()
        except KeyboardInterrupt:
            print("\n👋 再见!")
            break


# ═══ CLI ═════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="芯伴X1 问答助手")
    parser.add_argument("--text", "-t", default=None, help="文字提问")
    parser.add_argument("--loop", "-l", action="store_true", help="连续对话")
    args = parser.parse_args()

    print("🤖 芯伴X1 问答助手\n")

    if args.text:
        asyncio.run(text_mode(args.text))
    elif args.loop:
        asyncio.run(loop_mode())
    else:
        asyncio.run(qa_round())


if __name__ == "__main__":
    main()
