from __future__ import annotations

import os
from pathlib import Path


def configure_runtime_environment(root: Path = Path("D:/Jarvis")) -> None:
    """Force third-party runtime cache/model locations under the Jarvis root."""
    cache = root / "Cache"
    temp = root / "Temp"
    models = root / "Models"
    for path in (cache, temp, models):
        path.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache / "huggingface"))
    os.environ.setdefault("HF_HUB_CACHE", str(cache / "huggingface" / "hub"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache))
    os.environ.setdefault("PIP_CACHE_DIR", str(cache / "pip"))
    os.environ.setdefault("TMP", str(temp))
    os.environ.setdefault("TEMP", str(temp))
