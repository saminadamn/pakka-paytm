import cv2
import numpy as np

BLUR_MIN = 60.0
GLARE_MAX = 0.06
EDGE_MARGIN = 0.02


def check_image(data: bytes) -> dict:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "issues": ["FILE_FORMAT"], "metrics": {}}
    return check_array(img)


def check_array(img: np.ndarray) -> dict:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    glare = float((gray >= 250).mean())
    cropped, found = _card_touches_edge(gray)

    issues = []
    if cropped:
        issues.append("IMG_CROPPED")
    if sharpness < BLUR_MIN:
        issues.append("IMG_BLUR")
    if glare > GLARE_MAX:
        issues.append("IMG_GLARE")

    return {
        "ok": not issues,
        "issues": issues,
        "metrics": {"sharpness": round(sharpness, 1), "glare_ratio": round(glare, 4),
                    "card_found": found, "size": [w, h]},
    }


def _card_touches_edge(gray: np.ndarray) -> tuple[bool, bool]:
    h, w = gray.shape
    _, mask = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False, False
    card = max(contours, key=cv2.contourArea)
    if cv2.contourArea(card) < 0.15 * w * h:
        return False, False
    x, y, cw, ch = cv2.boundingRect(card)
    mx, my = int(w * EDGE_MARGIN), int(h * EDGE_MARGIN)
    touches = x <= mx or y <= my or x + cw >= w - mx or y + ch >= h - my
    return touches, True
