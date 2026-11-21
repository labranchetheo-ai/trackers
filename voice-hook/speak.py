#!/usr/bin/env python3
"""Claude Code "Stop" hook: reads Claude's last answer aloud with ElevenLabs.

On/off: the voice is active only if ~/.claude/voice_on exists.
Key: read from the ELEVENLABS_API_KEY environment variable (never stored here).
Standard library only. Playback uses afplay (macOS).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "j1qkMM79X5JLC4ZM86vA")
MODEL_ID = "eleven_flash_v2_5"
MAX_CHARS = 600
CLAUDE_DIR = Path.home() / ".claude"
FLAG = CLAUDE_DIR / "voice_on"
PID_FILE = Path(tempfile.gettempdir()) / "claude_voice.pid"


def last_text_from_transcript(path):
    """Fallback: last assistant text found in the JSONL transcript."""
    text = ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                content = (entry.get("message") or {}).get("content") or []
                if isinstance(content, str):
                    parts = [content]
                else:
                    parts = [c.get("text", "") for c in content
                             if isinstance(c, dict) and c.get("type") == "text"]
                joined = "\n".join(p for p in parts if p.strip())
                if joined:
                    text = joined
    except OSError:
        pass
    return text


def clean(md):
    """Turns markdown into speakable text: no code, no tables."""
    t = re.sub(r"```.*?(```|$)", " ", md, flags=re.S)        # code blocks
    t = re.sub(r"^\s*\|.*$", "", t, flags=re.M)               # table rows
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)                # images
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)            # links -> text
    t = re.sub(r"https?://\S+", "", t)                        # bare URLs
    t = re.sub(r"`([^`]*)`", r"\1", t)                        # inline code
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)       # headings
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)                # quotes
    t = re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", t, flags=re.M)  # bullets
    t = re.sub(r"^\s*([-*_]\s*){3,}$", "", t, flags=re.M)     # horizontal rules
    t = re.sub(r"(\*\*|__|\*|~~)", "", t)                     # bold/italic
    t = re.sub(r"<[^>]+>", "", t)                             # HTML tags
    # A line without final punctuation (heading, bullet) gets a period: better prosody.
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    lines = [l if l[-1] in ".!?:;…" else l + "." for l in lines]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def shorten(text):
    if len(text) <= MAX_CHARS:
        return text
    head = text[:MAX_CHARS]
    cut = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
    head = head[:cut + 1] if cut > MAX_CHARS // 3 else head.rsplit(" ", 1)[0] + "…"
    return head + " La suite est à l'écran."


def stop_previous_playback():
    try:
        os.kill(int(PID_FILE.read_text()), 15)
    except (OSError, ValueError):
        pass


def tts(text, key):
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        "?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": MODEL_ID,
                         "language_code": "fr"}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def speak(text):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY manquante")
    audio = tts(text, key)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio)
    stop_previous_playback()
    player = subprocess.Popen(["afplay", f.name])
    PID_FILE.write_text(str(player.pid))
    player.wait()
    os.unlink(f.name)


def main():
    # Manual test: python3 speak.py "Bonjour"
    if len(sys.argv) > 1:
        speak(shorten(clean(" ".join(sys.argv[1:]))))
        return
    if not FLAG.exists():
        return
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    raw = data.get("last_assistant_message") or ""
    if not raw and data.get("transcript_path"):
        raw = last_text_from_transcript(data["transcript_path"])
    text = shorten(clean(raw))
    if text:
        speak(text)


if __name__ == "__main__":
    main()
