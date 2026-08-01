from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path("D:/Jarvis")
VOICE_DIR = ROOT / "Voices"
VOICE_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
TARGETS = {
    BASE_URL: VOICE_DIR / "en_US-lessac-medium.onnx",
    BASE_URL + ".json": VOICE_DIR / "en_US-lessac-medium.onnx.json",
}

for url, target in TARGETS.items():
    if target.exists() and target.stat().st_size > 0:
        print(f"exists {target}")
        continue
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, target)
    print(f"saved {target}")

print("PIPER_VOICE_READY")
