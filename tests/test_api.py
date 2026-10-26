import cv2
from fastapi.testclient import TestClient

from app.main import app
from tests.test_doccheck import card

client = TestClient(app)


def post_event(jid, **e):
    r = client.post(f"/journeys/{jid}/events", json=e)
    assert r.status_code == 200, r.text


def test_full_rescue_flow():
    jid = client.post("/journeys").json()["journey_id"]
    post_event(jid, type="step_view", step="kyc", ts=0)
    post_event(jid, type="upload_failed", step="kyc", ts=10, code="IMG_CROPPED")
    assert not client.get(f"/journeys/{jid}/rescue", params={"now": 12, "dry": True}).json()["detection"]["stalled"]
    post_event(jid, type="upload_failed", step="kyc", ts=20, code="IMG_CROPPED")

    first = client.get(f"/journeys/{jid}/rescue", params={"now": 22, "lang": "hi"}).json()
    assert first["action"] == "guided_recapture" and first["lang"] == "hi"

    post_event(jid, type="upload_failed", step="kyc", ts=40, code="IMG_BLUR")
    second = client.get(f"/journeys/{jid}/rescue", params={"now": 42}).json()
    assert second["action"] == "human_handoff" and second["escalated"]

    log = client.get("/audit").json()
    assert [row["action"] for row in log if row["journey_id"] == jid] == ["human_handoff", "guided_recapture"]


def test_doccheck_endpoint():
    ok, buf = cv2.imencode(".png", card(offset_x=-120))
    r = client.post("/doccheck", files={"file": ("aadhaar.png", buf.tobytes(), "image/png")})
    assert "IMG_CROPPED" in r.json()["issues"]


def test_kfs_and_explain():
    assert "APR" in client.get("/kfs/apr", params={"lang": "hi"}).json()["text"]
    assert client.get("/kfs/nonsense").status_code == 404
    assert client.get("/explain", params={"action": "explain_kfs", "lang": "hi"}).status_code == 200


def test_unknown_journey_and_speak_without_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert client.post("/journeys/nope/events", json={"type": "submit", "step": "review", "ts": 1}).status_code == 404
    assert client.post("/speak", json={"text": "hello"}).status_code == 503
