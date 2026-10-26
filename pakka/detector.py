from collections import Counter

from .models import Detection, Event

IDLE_SECONDS = 90
TIMEOUT_SECONDS = 600
PHOTO_CODES = {"IMG_CROPPED", "IMG_BLUR", "IMG_GLARE"}


def detect(events: list[Event], now: float) -> Detection:
    if not events:
        return Detection(stalled=False)

    events = sorted(events, key=lambda e: e.ts)
    last = events[-1]

    if any(e.type == "submit" for e in events):
        return Detection(stalled=False, reasons=["application submitted"])

    step = last.step
    idle = now - last.ts
    here = [e for e in events if e.step == step]
    since_ok = _after_last(here, "upload_ok")

    if any(e.type == "session_expired" for e in here) or idle >= TIMEOUT_SECONDS:
        return Detection(stalled=True, blocker="timeout", step=step,
                         reasons=[f"idle {int(idle)}s at {step}"])

    if step == "kyc":
        fails = [e for e in since_ok if e.type == "upload_failed"]
        if len(fails) >= 2 or (fails and idle >= IDLE_SECONDS):
            code = Counter(e.code for e in fails).most_common(1)[0][0]
            blocker = "wrong_format" if code == "FILE_FORMAT" else "bad_photo"
            return Detection(stalled=True, blocker=blocker, step=step, code=code,
                             reasons=[f"{len(fails)} failed uploads", f"last code {fails[-1].code}"])

        live = [e for e in here if e.type == "liveness_failed"]
        if len(live) >= 2:
            return Detection(stalled=True, blocker="liveness", step=step,
                             reasons=[f"{len(live)} failed liveness checks"])

        if any(e.type == "digilocker_error" and e.code == "NOT_REGISTERED" for e in here):
            return Detection(stalled=True, blocker="digilocker", step=step, code="NOT_REGISTERED",
                             reasons=["user not registered on DigiLocker"])

    if step == "offer":
        opened = sum(e.type == "kfs_open" for e in here)
        backs = sum(e.type == "back" for e in here)
        if (opened and idle >= IDLE_SECONDS) or backs >= 2:
            return Detection(stalled=True, blocker="offer_jargon", step=step,
                             reasons=[f"KFS opened {opened}x", f"back {backs}x", f"idle {int(idle)}s"])

    return Detection(stalled=False, step=step)


def _after_last(events: list[Event], kind: str) -> list[Event]:
    idx = max((i for i, e in enumerate(events) if e.type == kind), default=-1)
    return events[idx + 1:]
