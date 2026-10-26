import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pakka.synth import FAILURES, journey  # noqa: E402

EXPECTED_ACTION = {
    "bad_photo": {0: "guided_recapture", 1: "human_handoff", 3: "human_handoff"},
    "wrong_format": {0: "convert_file", 1: "guided_recapture", 3: "human_handoff"},
    "liveness": {0: "retry_liveness_tips", 1: "switch_to_video_kyc", 3: "human_handoff"},
    "offer_jargon": {0: "explain_kfs", 1: "schedule_callback", 3: "human_handoff"},
    "timeout": {0: "send_resume_link", 1: "schedule_callback", 3: "schedule_callback"},
}


def main():
    rng = random.Random(99)
    cases = []
    attempts_cycle = [0, 0, 1, 3, 0]
    for kind in FAILURES:
        for i in range(5):
            events, now = journey(kind, rng)
            a = attempts_cycle[i]
            cases.append({
                "id": f"{kind}-{i + 1}", "attempts": a, "lang": "hi" if i % 2 else "en",
                "events": [e.model_dump() for e in events], "now": round(now, 2),
                "expect_blocker": kind, "expect_action": EXPECTED_ACTION[kind][a],
            })
    for i in range(5):
        kind = "clean_complete" if i < 2 else "clean_near_miss"
        events, now = journey(kind, rng)
        cases.append({
            "id": f"{kind}-{i + 1}", "attempts": 0, "lang": "en",
            "events": [e.model_dump() for e in events], "now": round(now, 2),
            "expect_blocker": None, "expect_action": None,
        })
    out = Path(__file__).with_name("scenarios.json")
    out.write_text(json.dumps(cases, indent=1), encoding="utf-8")
    print(f"wrote {len(cases)} scenarios to {out.name}")


if __name__ == "__main__":
    main()
