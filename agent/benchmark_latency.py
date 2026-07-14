"""Day 14: measures real per-stage and end-to-end turn latency.

Not a live-call test - isolates each stage the same way Day 4/5/6's own
verification did, so a slow stage can't hide behind another one's
timing. Run standalone: python benchmark_latency.py
"""

import asyncio
import statistics
import time
import wave

import numpy as np

from pipeline.llm import QwenLLM
from pipeline.stt import WhisperSTT
from pipeline.tts import KokoroTTS

TEST_WAV = r"C:\Users\SAAD\AppData\Local\Temp\stt_test.wav"
TEST_TRANSCRIPTS = [
    "Hi, I saw your ad and I am interested in learning more about your product.",
    "Your pricing is way too expensive compared to competitors.",
    "Can I speak to a real person please?",
    "Yes that sounds great, can we meet next Tuesday at 3pm?",
    "How does this compare to what we're already using?",
]
TEST_REPLIES = [
    "Sure, I would be happy to help. What time works best for you?",
    "I understand your concern about the price.",
    "Of course, let me transfer you.",
]


def load_wav_float32(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        frames = w.readframes(w.getnframes())
    samples = np.frombuffer(frames, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0


async def bench_stt(stt: WhisperSTT, trials: int = 5) -> list[float]:
    audio = load_wav_float32(TEST_WAV)
    timings = []
    for _ in range(trials):
        t0 = time.time()
        await stt._transcribe(audio)
        timings.append(time.time() - t0)
    return timings


async def bench_llm(llm: QwenLLM, trials: int = 5) -> list[float]:
    timings = []
    for i in range(trials):
        text = TEST_TRANSCRIPTS[i % len(TEST_TRANSCRIPTS)]
        t0 = time.time()
        await llm.generate(text, timeout=45.0)
        timings.append(time.time() - t0)
    return timings


async def bench_tts(tts: KokoroTTS, trials: int = 5) -> list[float]:
    timings = []
    for i in range(trials):
        text = TEST_REPLIES[i % len(TEST_REPLIES)]
        t0 = time.time()
        tts._kokoro.create(text, voice="af_heart")
        timings.append(time.time() - t0)
    return timings


def report(name: str, timings: list[float]) -> None:
    print(
        f"{name}: mean={statistics.mean(timings)*1000:.0f}ms "
        f"min={min(timings)*1000:.0f}ms max={max(timings)*1000:.0f}ms "
        f"(n={len(timings)})"
    )


async def main() -> None:
    print("Loading models (not timed)...")
    stt = WhisperSTT()
    llm = QwenLLM()
    tts = KokoroTTS()

    print("\n--- Warming up (first call always pays a cold-start cost) ---")
    await bench_stt(stt, trials=1)
    await bench_llm(llm, trials=1)
    await bench_tts(tts, trials=1)

    print("\n--- Baseline: 5 trials per stage, warm ---")
    stt_times = await bench_stt(stt, trials=5)
    llm_times = await bench_llm(llm, trials=5)
    tts_times = await bench_tts(tts, trials=5)

    report("STT (faster-whisper tiny.en, 2s chunk)", stt_times)
    report("LLM (Qwen2.5:7b via Ollama)", llm_times)
    report("TTS (Kokoro int8)", tts_times)

    total = statistics.mean(stt_times) + statistics.mean(llm_times) + statistics.mean(tts_times)
    print(f"\nEstimated turn latency (sum of means): {total*1000:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
