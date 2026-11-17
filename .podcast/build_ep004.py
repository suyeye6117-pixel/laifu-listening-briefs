import array
import hashlib
import html
import json
import math
import pathlib
import re
import statistics
import subprocess
import sys
import tempfile
import urllib.request
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/audio"
RATE = 24000
GAP = 0.28

def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)

def probe(path):
    result = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(result)["format"]["duration"])

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / "ora-004-duet.mp3"
    with tempfile.TemporaryDirectory(prefix="ep004-") as td:
        temp = pathlib.Path(td)
        groups = []
        for index in range(5):
            data = json.loads((ROOT / f".podcast/ep004-group-{index}.json").read_text())
            group, speech = data["group"], data["speech"]
            chars = speech["original_characters"]
            if "".join(c["text"] for c in chars) != group["text"]:
                raise ValueError(f"Transcript mismatch in group {index}")
            if any(c["end_time"] < c["start_time"] for c in chars):
                raise ValueError("Invalid returned timestamps")
            raw = temp / f"source-{index}.pcm"
            urllib.request.urlretrieve(speech["audio_url"], raw)
            blob = raw.read_bytes()
            # The server may return WAV or raw PCM. Use measured properties.
            if blob[:4] == b"RIFF":
                with wave.open(str(raw)) as w:
                    original_rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
                    source_duration = w.getnframes() / original_rate
                source_args = ["-i", str(raw)]
            else:
                implied_rate = len(blob) / (2 * speech["duration"])
                original_rate = min([8000, 16000, 22050, 24000, 32000, 44100, 48000], key=lambda v: abs(v - implied_rate))
                channels, width = 1, 2
                source_duration = len(blob) / (width * channels * original_rate)
                source_args = ["-f", "s16le", "-ar", str(original_rate), "-ac", "1", "-i", str(raw)]
            if abs(source_duration - speech["duration"]) > 0.3:
                raise ValueError(f"Audio duration mismatch: {source_duration} / {speech['duration']}")
            wav = temp / f"source-{index}.wav"
            run("ffmpeg", "-y", "-v", "error", *source_args, "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(wav))
            with wave.open(str(wav)) as w:
                samples = array.array("h", w.readframes(w.getnframes()))
            if sys.byteorder != "little":
                samples.byteswap()
            rms = math.sqrt(sum(int(v) * int(v) for v in samples) / len(samples))
            peak = max(abs(v) for v in samples)
            if rms < 50 or peak < 100:
                raise ValueError("Empty or inaudible generated speech")
            gain = min(32767 * 0.1 / rms, 32767 * 0.92 / peak)
            groups.append((data, samples, gain))
            print(f"group={index}, duration={source_duration:.3f}, rate={original_rate}, gain={gain:.3f}", flush=True)

        turns = {}
        for data, samples, gain in groups:
            group, speech = data["group"], data["speech"]
            chars = speech["original_characters"]
            for span in group["spans"]:
                start, end = span["start"], span["end"]
                active = [c for c in chars[start:end] if c["text"].strip()]
                first_time = active[0]["start_time"]
                last_time = active[-1]["end_time"]
                # Keep a little boundary silence without borrowing adjacent dialogue.
                before = [c["end_time"] for c in chars[:start] if c["text"].strip()]
                after = [c["start_time"] for c in chars[end:] if c["text"].strip()]
                t0 = max(0.0, first_time - 0.07, (before[-1] + first_time) / 2 if before else 0.0)
                t1 = min(len(samples) / RATE, last_time + 0.10, (last_time + after[0]) / 2 if after else len(samples) / RATE)
                section = array.array("h", (round(v * gain) for v in samples[round(t0 * RATE):round(t1 * RATE)]))
                turns[span["turnId"]] = {
                    "samples": section,
                    "speaker": group["speaker"],
                    "voice": "Mengyao" if group["speaker"] == "A" else "Haoran",
                    "text": group["text"][start:end],
                    "source_group": group["id"],
                    "source_start": round(t0, 4),
                    "source_end": round(t1, 4),
                }
        if sorted(turns) != list(range(34)):
            raise ValueError("Missing dialogue turns")
        combined = temp / "dialogue.wav"
        position = 0
        timeline = []
        with wave.open(str(combined), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            for tid in range(34):
                turn = turns[tid]
                sample_count = len(turn["samples"])
                record = {k: v for k, v in turn.items() if k != "samples"}
                record.update({"turn": tid + 1, "start": round(position / RATE, 4), "end": round((position + sample_count) / RATE, 4)})
                timeline.append(record)
                block = turn["samples"]
                if sys.byteorder != "little":
                    block.byteswap()
                w.writeframes(block.tobytes())
                position += sample_count
                if tid < 33:
                    w.writeframes(b"\x00\x00" * round(GAP * RATE))
                    position += round(GAP * RATE)
        run("ffmpeg", "-y", "-v", "error", "-i", str(combined),
            "-c:a", "libmp3lame", "-b:a", "128k", "-ar", str(RATE), "-ac", "1",
            "-metadata", "title=欧拉好猫新手课堂 EP004 男女对话版",
            "-metadata", "artist=Haoran & Mengyao", str(final))
        duration = probe(final)
        if abs(duration - position / RATE) > 0.2:
            raise ValueError("Final encoded duration mismatch")
        run("ffmpeg", "-v", "error", "-i", str(final), "-f", "null", "-")
        metadata = {
            "episode": "EP004", "duration": duration, "sample_rate": RATE,
            "voices": {"A": "Mengyao", "B": "Haoran"},
            "sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "turns": timeline, "speech_speed": 1.0,
            "validation": {"returned_transcript_matches": True, "all_34_turns_present": True, "full_decode_passed": True},
            "listening_review": "Full listening review remains a user check; timing and decoding checks do not certify pronunciation."
        }
        (OUT / "ora-004-duet.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        minutes, seconds = divmod(round(duration), 60)
        page_path = ROOT / "episodes/ora-004.html"
        page = page_path.read_text(encoding="utf-8")
        page = page.replace('<link rel="stylesheet" href="/assets/read-aloud.css">', "")
        page = page.replace('<script src="/assets/read-aloud.js" defer></script>', "")
        player = f'''<aside class="episode-audio" aria-label="第四期男女对话音频" data-no-read>
<h2 style="font-size:21px;margin:0 0 12px">第四期 · 男女对话版</h2>
<p style="margin:0 0 12px;color:#687477">Haoran 男声 × Mengyao 女声 · {minutes}分{seconds:02d}秒 · 仅节目正文</p>
<audio id="episode-audio" controls preload="metadata" style="width:100%" src="/assets/audio/ora-004-duet.mp3">浏览器不支持音频播放。</audio>
<p style="margin:12px 0 0;font-size:14px"><a href="/assets/audio/ora-004-duet.mp3" download="ora-004-duet.mp3">下载完整音频 MP3</a></p>
<noscript>可直接播放或下载完整音频。</noscript>
</aside>'''
        page, count = re.subn(r'<aside class="read-aloud"[\s\S]*?</aside>', lambda m: player, page, count=1)
        if count != 1:
            raise ValueError("Expected exactly one episode player")
        page = page.replace("</style>", ".episode-audio{background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px;margin:22px 0 30px}audio{display:block}\n</style>")
        page = page.replace("建议收听 16–20 分钟", f"男女对话音频 {minutes}分{seconds:02d}秒")
        page_path.write_text(page, encoding="utf-8")
        print(json.dumps({"duration": duration, "duration_label": f"{minutes}:{seconds:02d}", "bytes": final.stat().st_size, "sha256": metadata["sha256"], "turn_count": len(timeline)}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
