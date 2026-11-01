"""Creates samples/audio/*.mp3: synthetic Bangla/Banglish speech used by the integration tests and the ASR benchmark.
Uses Microsoft's online voices through the edge-tts package (the sample TEXT is sent to that service, nothing else).
These clips are a sanity check only; they are no substitute for real recordings. Usage: python scripts/make_sample_audio.py"""
import asyncio
from pathlib import Path

import edge_tts

OUT = Path(__file__).resolve().parents[1] / "samples" / "audio"
TEXTS = {
    "bn_plain": ("bn-BD-NabanitaNeural", "ইয়েল্ড মানে কী? ধরুন দোকানের দাম একশো টাকা। বছরে ভাড়া পাচ্ছেন তিন টাকা। এটাকে বলে গ্রস ইয়েল্ড চার শতাংশ। কিন্তু খরচ বাদ দিয়া পকেটে যেটা থাকবে, সেটাই আসল নেট ইয়েল্ড।"),
    "banglish": ("bn-BD-PradeepNeural", "আজকের টপিক হলো রিয়েল এস্টেট ইনভেস্টমেন্ট। ধরুন আপনি একটা flat কিনলেন পঞ্চাশ লাখ টাকায়। মাসে পঁচিশ হাজার টাকা rent পাচ্ছেন। তাহলে gross yield হবে ছয় শতাংশ। কিন্তু maintenance আর tax বাদ দিলে net yield কমে চার শতাংশ হয়ে যায়।"),
}


def make_noise_and_silence() -> None:
    """No-speech test inputs (no network needed): 5 s of pink-ish noise and 5 s of digital silence, 16 kHz mono."""
    import numpy as np
    import soundfile as sf

    rng = np.random.default_rng(3)
    sf.write(str(OUT / "noise.wav"), (0.05 * rng.normal(size=16000 * 5)).astype("float32"), 16000)
    sf.write(str(OUT / "silent.wav"), np.zeros(16000 * 5, dtype="float32"), 16000)
    print("saved noise.wav, silent.wav")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_noise_and_silence()
    for name, (voice, text) in TEXTS.items():
        await edge_tts.Communicate(text, voice).save(str(OUT / f"{name}.mp3"))
        print("saved", OUT / f"{name}.mp3")


if __name__ == "__main__":
    asyncio.run(main())
