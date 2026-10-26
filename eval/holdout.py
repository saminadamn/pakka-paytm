import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pakka.detector import detect  # noqa: E402
from pakka.models import Event  # noqa: E402

OUT = Path(__file__).with_name("holdout_results.json")


def E(type, step, ts, code=None):
    return Event(type=type, step=step, ts=ts, code=code)


def lead(rng, until):
    t, ev = 0.0, []
    for s in ["basic", "kyc", "offer", "bank", "review"]:
        t += rng.uniform(5, 40)
        ev.append(E("step_view", s, t))
        if s == until:
            return ev, t
        if s == "kyc":
            t += rng.uniform(10, 30)
            ev.append(E("upload_ok", "kyc", t))
    return ev, t


def variants(rng):
    v = {}

    def pan_ok_then_two_aadhaar_fails():
        ev, t = lead(rng, "kyc")
        ev.append(E("upload_ok", "kyc", t + 10))
        ev += [E("upload_failed", "kyc", t + 30, "IMG_GLARE"), E("upload_failed", "kyc", t + 55, "IMG_BLUR")]
        return ev, t + 70, "bad_photo"

    def one_fail_then_long_pause():
        ev, t = lead(rng, "kyc")
        ev.append(E("upload_failed", "kyc", t + 10, "IMG_CROPPED"))
        return ev, t + 10 + rng.uniform(95, 300), "bad_photo"

    def two_fails_then_walks_away():
        ev, t = lead(rng, "kyc")
        ev += [E("upload_failed", "kyc", t + 10, "IMG_BLUR"), E("upload_failed", "kyc", t + 25, "IMG_BLUR")]
        return ev, t + 25 + rng.uniform(650, 2000), "bad_photo"

    def liveness_fail_ok_fail():
        ev, t = lead(rng, "kyc")
        ev += [E("liveness_failed", "kyc", t + 10), E("upload_ok", "kyc", t + 30), E("liveness_failed", "kyc", t + 50)]
        return ev, t + 60, "liveness"

    def one_liveness_fail_then_pause():
        ev, t = lead(rng, "kyc")
        ev.append(E("liveness_failed", "kyc", t + 10))
        return ev, t + 10 + rng.uniform(120, 400), "liveness"

    def format_then_blur():
        ev, t = lead(rng, "kyc")
        ev += [E("upload_failed", "kyc", t + 10, "FILE_FORMAT"), E("upload_failed", "kyc", t + 30, "FILE_FORMAT"),
               E("upload_failed", "kyc", t + 50, "IMG_BLUR")]
        return ev, t + 60, "wrong_format"

    def kfs_back_then_pause():
        ev, t = lead(rng, "offer")
        ev += [E("kfs_open", "offer", t + 5), E("back", "offer", t + 15)]
        return ev, t + 15 + rng.uniform(95, 300), "offer_jargon"

    def idle_on_bank():
        ev, t = lead(rng, "bank")
        return ev, t + rng.uniform(650, 3000), "timeout"

    def no_digilocker():
        ev, t = lead(rng, "kyc")
        ev.append(E("digilocker_error", "kyc", t + 5, "NOT_REGISTERED"))
        return ev, t + 20, "digilocker"

    def fails_then_moves_on():
        ev, t = lead(rng, "kyc")
        ev += [E("upload_failed", "kyc", t + 10, "IMG_BLUR"), E("upload_failed", "kyc", t + 20, "IMG_BLUR"),
               E("upload_ok", "kyc", t + 40), E("step_view", "offer", t + 50)]
        return ev, t + 50 + rng.uniform(5, 60), None

    def reads_kfs_briefly():
        ev, t = lead(rng, "offer")
        ev.append(E("kfs_open", "offer", t + 5))
        return ev, t + 5 + rng.uniform(20, 85), None

    def one_back_quick():
        ev, t = lead(rng, "offer")
        ev.append(E("back", "offer", t + 5))
        return ev, t + 5 + rng.uniform(5, 60), None

    def finishes():
        ev, t = lead(rng, "review")
        ev.append(E("submit", "review", t + 10))
        return ev, t + rng.uniform(10, 5000), None

    for f in [pan_ok_then_two_aadhaar_fails, one_fail_then_long_pause, two_fails_then_walks_away,
              liveness_fail_ok_fail, one_liveness_fail_then_pause, format_then_blur, kfs_back_then_pause,
              idle_on_bank, no_digilocker, fails_then_moves_on, reads_kfs_briefly, one_back_quick, finishes]:
        v[f.__name__] = f
    return v


def main(per_variant: int = 20, seed: int = 2026):
    rng = random.Random(seed)
    v = variants(rng)
    confusion = defaultdict(Counter)
    misses = Counter()
    n = 0
    for name, make in v.items():
        for _ in range(per_variant):
            events, now, label = make()
            got = detect(events, now).blocker
            confusion[label or "none"][got or "none"] += 1
            if (got or "none") != (label or "none"):
                misses[name] += 1
            n += 1
    correct = sum(confusion[c][c] for c in confusion)
    clean = sum(confusion["none"].values())
    stalled = n - clean
    fp = clean - confusion["none"]["none"]
    fn = sum(confusion[c]["none"] for c in confusion if c != "none")
    res = {
        "journeys": n, "variants": len(v), "accuracy": round(correct / n, 3),
        "false_positive_rate": round(fp / clean, 3), "false_negative_rate": round(fn / stalled, 3),
        "missed_by_variant": dict(misses),
        "confusion": {k: dict(c) for k, c in confusion.items()},
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ["journeys", "variants", "accuracy", "false_positive_rate",
                                          "false_negative_rate", "missed_by_variant"]}, indent=1))


if __name__ == "__main__":
    main()
