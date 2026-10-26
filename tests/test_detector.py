from pakka.detector import detect
from pakka.models import Event


def ev(type, step, ts, code=None):
    return Event(type=type, step=step, ts=ts, code=code)


def test_two_cropped_uploads_is_bad_photo():
    events = [ev("step_view", "kyc", 0), ev("upload_failed", "kyc", 10, "IMG_CROPPED"),
              ev("upload_failed", "kyc", 20, "IMG_CROPPED")]
    d = detect(events, now=25)
    assert d.stalled and d.blocker == "bad_photo" and d.code == "IMG_CROPPED"


def test_one_failure_then_success_is_not_stalled():
    events = [ev("step_view", "kyc", 0), ev("upload_failed", "kyc", 10, "IMG_BLUR"),
              ev("upload_ok", "kyc", 20)]
    assert not detect(events, now=200).stalled


def test_one_failure_and_idle_is_stalled():
    events = [ev("step_view", "kyc", 0), ev("upload_failed", "kyc", 10, "IMG_GLARE")]
    assert not detect(events, now=50).stalled
    assert detect(events, now=110).blocker == "bad_photo"


def test_wrong_format():
    events = [ev("upload_failed", "kyc", 1, "FILE_FORMAT"), ev("upload_failed", "kyc", 2, "FILE_FORMAT")]
    assert detect(events, now=5).blocker == "wrong_format"


def test_liveness_and_digilocker():
    assert detect([ev("liveness_failed", "kyc", 1), ev("liveness_failed", "kyc", 9)], 10).blocker == "liveness"
    assert detect([ev("digilocker_error", "kyc", 1, "NOT_REGISTERED")], 2).blocker == "digilocker"


def test_offer_hesitation_needs_time_or_repeated_backs():
    base = [ev("step_view", "offer", 0), ev("kfs_open", "offer", 5)]
    assert not detect(base, now=60).stalled
    assert detect(base, now=120).blocker == "offer_jargon"
    backs = [ev("step_view", "offer", 0), ev("back", "offer", 3), ev("back", "offer", 6)]
    assert detect(backs, now=8).blocker == "offer_jargon"


def test_timeout_and_submit():
    assert detect([ev("step_view", "bank", 0)], now=700).blocker == "timeout"
    assert detect([ev("session_expired", "basic", 3)], now=4).blocker == "timeout"
    assert not detect([ev("step_view", "review", 0), ev("submit", "review", 5)], now=9999).stalled


def test_empty():
    assert not detect([], 0).stalled
