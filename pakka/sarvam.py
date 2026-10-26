import base64
import json
import os
import urllib.request

from .pii import mask

API = "https://api.sarvam.ai"
LANG_CODES = {"en": "en-IN", "hi": "hi-IN"}


def enabled() -> bool:
    return bool(os.getenv("SARVAM_API_KEY"))


def tts(text: str, lang: str = "hi") -> bytes:
    body = {
        "text": mask(text)[:1500],
        "target_language_code": LANG_CODES.get(lang, "hi-IN"),
        "model": os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
    }
    req = urllib.request.Request(
        f"{API}/text-to-speech",
        data=json.dumps(body).encode(),
        headers={"api-subscription-key": os.environ["SARVAM_API_KEY"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read())
    return base64.b64decode(payload["audios"][0])
