import array
import hashlib
import json
import math
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.request
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
RATE = 24000
VOICE = "Shuxian"

def command(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)

def main():
    out = ROOT / "assets/audio"
    out.mkdir(parents=True, exist_ok=True)
    final = out / "ora-009-shuxian.mp3"
    records = []
    position = 0
    with tempfile.TemporaryDirectory(prefix="ep009-") as td:
        temp = pathlib.Path(td)
        combined = temp / "complete.wav"
        with wave.open(str(combined), "wb") as dest:
            dest.setnchannels(1)
            dest.setsampwidth(2)
            dest.setframerate(RATE)
            for index in range(3):
                source = json.loads((ROOT / f".podcast/ep009-group-{index}.json").read_text(encoding="utf-8"))
                speech = source["speech"]
                if "".join(c["text"] for c in speech["original_characters"]) != source["group"]["text"]:
                    raise ValueError("Returned speech text differs from the approved script")
                raw = temp / f"source-{index}.pcm"
                urllib.request.urlretrieve(speech["audio_url"], raw)
                wav = temp / f"source-{index}.wav"
                source_args = ["-i", str(raw)] if raw.read_bytes()[:4] == b"RIFF" else ["-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", str(raw)]
                command("ffmpeg", "-y", "-v", "error", *source_args, "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(wav))
                with wave.open(str(wav)) as inp:
                    samples = array.array("h", inp.readframes(inp.getnframes()))
                if sys.byteorder != "little":
                    samples.byteswap()
                rms = math.sqrt(sum(int(v) * int(v) for v in samples) / len(samples))
                peak = max(abs(v) for v in samples)
                gain = min(32767 * 0.1 / rms, 32767 * 0.92 / peak)
                block = array.array("h", (round(v * gain) for v in samples))
                records.append({"part": index + 1, "start": position / RATE, "end": (position + len(block)) / RATE, "text": source["group"]["text"], "voice": VOICE})
                if sys.byteorder != "little":
                    block.byteswap()
                dest.writeframes(block.tobytes())
                position += len(block)
                if index < 2:
                    pause = round(0.35 * RATE)
                    dest.writeframes(b"\x00\x00" * pause)
                    position += pause
                print(f"Saved narration part {index + 1}", flush=True)
        command("ffmpeg", "-y", "-v", "error", "-i", str(combined), "-c:a", "libmp3lame", "-b:a", "128k", "-ar", str(RATE), "-ac", "1", "-metadata", "title=欧拉好猫新手课堂 EP009 Shuxian女声版", "-metadata", "artist=Shuxian", str(final))
    duration = position / RATE
    meta = {"episode": "EP009", "voice": VOICE, "voice_id": "6c364011f30747c9a0a89eec3787cadc", "duration": duration, "speed": 1, "sha256": hashlib.sha256(final.read_bytes()).hexdigest(), "parts": records, "spoken_scope": "episode body only", "playback_download_tests": "not run, as requested"}
    (out / "ora-009-shuxian.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    minutes, seconds = divmod(round(duration), 60)
    label = f"{minutes}分{seconds:02d}秒"
    page_path = ROOT / "episodes/ora-009.html"
    page = page_path.read_text(encoding="utf-8")
    page = page.replace('<link rel="stylesheet" href="/assets/read-aloud.css">', "").replace('<script src="/assets/read-aloud.js" defer></script>', "")
    player = f'''<aside class="episode-audio" id="read-aloud" aria-label="第九期Shuxian女声音频" data-no-read>
<h2 style="font-size:21px;margin:0 0 12px">第九期 · Shuxian 女声版</h2>
<p style="margin:0 0 12px;color:#687477">Shuxian 女声 · {label} · 仅节目正文</p>
<audio id="episode-audio" controls preload="metadata" style="width:100%" src="/assets/audio/ora-009-shuxian.mp3">浏览器不支持音频播放。</audio>
<p style="margin:12px 0 0;font-size:14px"><a href="/assets/audio/ora-009-shuxian.mp3" download="ora-009-shuxian.mp3">下载完整音频 MP3</a></p>
<noscript>可直接播放或下载完整音频。</noscript>
</aside>'''
    anchor = '<div class="intro">'
    if anchor not in page:
        raise ValueError("Episode 009 player insertion target is missing")
    page = page.replace(anchor, player + "\n" + anchor, 1)
    page = page.replace("</style>", ".episode-audio{background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px;margin:22px 0 30px}audio{display:block}\n</style>")
    page = page.replace("建议收听约15–18分钟", f"Shuxian 女声音频 {label}")
    page_path.write_text(page, encoding="utf-8")
    index_path = ROOT / "index.html"
    index_page = index_path.read_text(encoding="utf-8")
    for card in re.findall(r'<article class="episode">[\s\S]*?</article>', index_page):
        if "/episodes/ora-009.html" in card:
            replacement = card.replace("建议 15–18 分钟", f"女声 · {label}").replace('href="/episodes/ora-009.html">阅读本期资料', 'href="/episodes/ora-009.html#read-aloud">播放Shuxian女声')
            index_page = index_page.replace(card, replacement)
            break
    index_path.write_text(index_page, encoding="utf-8")
    print(json.dumps({"duration": duration, "duration_label": label, "bytes": final.stat().st_size, "sha256": meta["sha256"]}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
