import pytest

from pakka import policy
from pakka.agent import rescue
from pakka.explain import KFS_TERMS, explain
from pakka.models import Event
from pakka.pii import mask

STALLED = [Event(type="upload_failed", step="kyc", ts=1, code="IMG_CROPPED"),
           Event(type="upload_failed", step="kyc", ts=2, code="IMG_CROPPED")]


def test_choose_walks_the_list_then_hands_off():
    assert policy.choose("wrong_format", 0) == "convert_file"
    assert policy.choose("wrong_format", 1) == "guided_recapture"
    assert policy.choose("wrong_format", 3) == "human_handoff"
    assert policy.choose("timeout", 5) == "schedule_callback"
    assert policy.choose("something_new", 0) == "human_handoff"


def test_check_blocks_unapproved_actions():
    with pytest.raises(policy.PolicyViolation):
        policy.check("bad_photo", "explain_kfs")
    policy.check("bad_photo", "guided_recapture")


def test_every_action_has_both_languages():
    for actions in policy.load()["blockers"].values():
        for a in actions:
            assert explain(a, "en") and explain(a, "hi")


def test_agent_rescue_in_hindi():
    out = rescue("t1", STALLED, now=5, lang="hi")
    assert out.detection.blocker == "bad_photo"
    assert out.action == "guided_recapture"
    assert out.needs_consent and out.policy_ok and not out.escalated
    assert "कोना" in out.message


def test_agent_escalates_after_repeated_attempts():
    out = rescue("t1", STALLED, now=5, attempts=3)
    assert out.action == "human_handoff" and out.escalated


def test_agent_does_nothing_when_not_stalled():
    out = rescue("t2", [Event(type="step_view", step="basic", ts=0)], now=10)
    assert out.action is None and out.message is None


def test_kfs_explanation_covers_every_term():
    for lang in ("en", "hi"):
        text = explain("explain_kfs", lang)
        assert all(t[lang] in text for t in KFS_TERMS.values())


def test_pii_is_masked():
    s = mask("Aadhaar 1234 5678 9012, PAN ABCDE1234F, phone 9876543210, mail a.b@x.in")
    assert "1234" not in s and "ABCDE" not in s and "9876" not in s and "@" not in s
