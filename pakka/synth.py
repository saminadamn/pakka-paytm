import random

from .models import Event

FAILURES = ["bad_photo", "wrong_format", "liveness", "offer_jargon", "timeout"]
STEPS = ["basic", "kyc", "offer", "bank", "review"]


def _walk(rng: random.Random, until: str, t: float = 0.0) -> tuple[list[Event], float]:
    events = []
    for step in STEPS:
        t += rng.uniform(5, 40)
        events.append(Event(type="step_view", step=step, ts=t))
        if step == "kyc" and until != "kyc":
            t += rng.uniform(10, 30)
            events.append(Event(type="upload_ok", step="kyc", ts=t))
        if step == until:
            break
    return events, t


def journey(kind: str, rng: random.Random) -> tuple[list[Event], float]:
    if kind == "bad_photo":
        ev, t = _walk(rng, "kyc")
        for _ in range(rng.randint(2, 3)):
            t += rng.uniform(8, 25)
            ev.append(Event(type="upload_failed", step="kyc", ts=t,
                            code=rng.choice(["IMG_CROPPED", "IMG_BLUR", "IMG_GLARE"])))
        return ev, t + rng.uniform(5, 60)

    if kind == "wrong_format":
        ev, t = _walk(rng, "kyc")
        for _ in range(rng.randint(2, 3)):
            t += rng.uniform(8, 25)
            ev.append(Event(type="upload_failed", step="kyc", ts=t, code="FILE_FORMAT"))
        return ev, t + rng.uniform(5, 60)

    if kind == "liveness":
        ev, t = _walk(rng, "kyc")
        for _ in range(rng.randint(2, 4)):
            t += rng.uniform(10, 30)
            ev.append(Event(type="liveness_failed", step="kyc", ts=t, code="LIVENESS"))
        return ev, t + rng.uniform(5, 60)

    if kind == "offer_jargon":
        ev, t = _walk(rng, "offer")
        if rng.random() < 0.5:
            t += rng.uniform(5, 20)
            ev.append(Event(type="kfs_open", step="offer", ts=t))
            return ev, t + rng.uniform(95, 400)
        for _ in range(2):
            t += rng.uniform(5, 20)
            ev.append(Event(type="back", step="offer", ts=t))
        return ev, t + rng.uniform(5, 60)

    if kind == "timeout":
        ev, t = _walk(rng, rng.choice(["basic", "bank", "review"]))
        if rng.random() < 0.5:
            ev.append(Event(type="session_expired", step=ev[-1].step, ts=t + 1))
            return ev, t + rng.uniform(2, 30)
        return ev, t + rng.uniform(620, 3000)

    if kind == "clean_complete":
        ev, t = _walk(rng, "review")
        t += rng.uniform(5, 30)
        ev.append(Event(type="submit", step="review", ts=t))
        return ev, t + rng.uniform(1, 600)

    if kind == "clean_near_miss":
        choice = rng.randint(0, 2)
        if choice == 0:
            ev, t = _walk(rng, "kyc")
            t += 10
            ev.append(Event(type="upload_failed", step="kyc", ts=t, code="IMG_BLUR"))
            return ev, t + rng.uniform(5, 80)
        if choice == 1:
            ev, t = _walk(rng, "offer")
            t += 10
            ev.append(Event(type="kfs_open", step="offer", ts=t))
            return ev, t + rng.uniform(5, 80)
        ev, t = _walk(rng, "kyc")
        t += 10
        ev.append(Event(type="upload_failed", step="kyc", ts=t, code="IMG_CROPPED"))
        t += 15
        ev.append(Event(type="upload_ok", step="kyc", ts=t))
        return ev, t + rng.uniform(5, 80)

    raise ValueError(kind)


def dataset(n_per_failure: int = 80, n_complete: int = 50, n_near_miss: int = 50, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    plan = [(k, k) for k in FAILURES for _ in range(n_per_failure)]
    plan += [("clean_complete", None)] * n_complete + [("clean_near_miss", None)] * n_near_miss
    rows = []
    for i, (kind, label) in enumerate(plan):
        events, now = journey(kind, rng)
        rows.append({"id": f"j{i:04d}", "kind": kind, "label": label, "events": events, "now": now})
    return rows
