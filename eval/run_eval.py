import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pakka import policy  # noqa: E402
from pakka.agent import rescue  # noqa: E402
from pakka.detector import detect  # noqa: E402
from pakka.explain import KFS_TERMS, explain  # noqa: E402
from pakka.models import Event  # noqa: E402
from pakka.synth import dataset  # noqa: E402

OUT = Path(__file__).with_name("results.json")
SCENARIOS = Path(__file__).with_name("scenarios.json")


def detection_report(rows):
    labels = sorted({r["label"] or "none" for r in rows})
    confusion = defaultdict(Counter)
    for r in rows:
        d = detect(r["events"], r["now"])
        confusion[r["label"] or "none"][d.blocker or "none"] += 1
    per_class = {}
    for c in labels:
        tp = confusion[c][c]
        fn = sum(confusion[c].values()) - tp
        fp = sum(confusion[o][c] for o in labels if o != c)
        per_class[c] = {
            "precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "n": sum(confusion[c].values()),
        }
    correct = sum(confusion[c][c] for c in labels)
    return {"accuracy": round(correct / len(rows), 3), "per_class": per_class,
            "confusion": {k: dict(v) for k, v in confusion.items()}}


def policy_report(rows):
    checks = violations = handoffs_at_3 = stalled = 0
    for r in rows:
        for attempts in range(5):
            out = rescue(r["id"], r["events"], r["now"], attempts=attempts)
            if not out.detection.stalled:
                break
            checks += 1
            if not out.policy_ok or out.action not in policy.allowed(out.detection.blocker):
                violations += 1
            if attempts == 3:
                stalled += 1
                handoffs_at_3 += out.action == "human_handoff"
    return {"actions_checked": checks, "violations": violations,
            "handoff_rate_after_3_attempts": round(handoffs_at_3 / stalled, 3) if stalled else None}


def kfs_report():
    missing = []
    for lang in ("en", "hi"):
        text = explain("explain_kfs", lang)
        missing += [f"{t}:{lang}" for t, v in KFS_TERMS.items() if v[lang] not in text]
    return {"terms": len(KFS_TERMS), "languages": 2, "missing": missing}


def latency_report(rows):
    times = [rescue(r["id"], r["events"], r["now"], lang="hi").latency_ms for r in rows]
    times.sort()
    return {"p50_ms": round(statistics.median(times), 2), "p95_ms": round(times[int(0.95 * len(times)) - 1], 2),
            "note": "agent only, no network calls"}


def scenario_report():
    cases = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    failed = []
    for c in cases:
        events = [Event(**e) for e in c["events"]]
        out = rescue(c["id"], events, c["now"], attempts=c.get("attempts", 0), lang=c.get("lang", "en"))
        if out.detection.blocker != c["expect_blocker"] or out.action != c["expect_action"]:
            failed.append({"id": c["id"], "got": [out.detection.blocker, out.action],
                           "want": [c["expect_blocker"], c["expect_action"]]})
    return {"scenarios": len(cases), "passed": len(cases) - len(failed), "failed": failed}


def main():
    rows = dataset()
    results = {
        "dataset": {"journeys": len(rows), "by_kind": dict(Counter(r["kind"] for r in rows))},
        "detection": detection_report(rows),
        "policy": policy_report(rows),
        "kfs_explanations": kfs_report(),
        "latency": latency_report(rows),
        "scripted_scenarios": scenario_report(),
    }
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    d, p, s = results["detection"], results["policy"], results["scripted_scenarios"]
    print(f"journeys: {len(rows)}  detection accuracy: {d['accuracy']}")
    for c, m in d["per_class"].items():
        print(f"  {c:<14} precision {m['precision']}  recall {m['recall']}  n={m['n']}")
    print(f"policy: {p['actions_checked']} actions checked, {p['violations']} violations, "
          f"handoff after 3 attempts {p['handoff_rate_after_3_attempts']}")
    print(f"kfs: {results['kfs_explanations']}")
    print(f"latency: {results['latency']}")
    print(f"scripted scenarios: {s['passed']}/{s['scenarios']} passed")
    return 0 if not s["failed"] and not p["violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
