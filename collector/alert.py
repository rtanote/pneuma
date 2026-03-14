import json
import logging
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

log = logging.getLogger(__name__)

BOCCO_ACCESS_TOKEN = os.getenv("BOCCO_ACCESS_TOKEN", "")
BOCCO_REFRESH_TOKEN = os.getenv("BOCCO_REFRESH_TOKEN", "")
BOCCO_ROOM_ID = os.getenv("BOCCO_ROOM_ID", "")
ALERT_COOLDOWN_MIN = int(os.getenv("ALERT_COOLDOWN_MIN", "30"))
ALERT_STATE_PATH = os.getenv("ALERT_STATE_PATH", "./alert_state.json")

LAMETRIC_DEVICE_IP = os.getenv("LAMETRIC_DEVICE_IP", "")
LAMETRIC_API_KEY = os.getenv("LAMETRIC_API_KEY", "")
LAMETRIC_APP_ID = os.getenv("LAMETRIC_APP_ID", "")
LAMETRIC_WIDGET_ID = os.getenv("LAMETRIC_WIDGET_ID", "")

THRESHOLDS = {
    "eco2_1000": {
        "check": lambda d: d["eco2"] >= 1000,
        "message": "CO2濃度が高くなっています。換気してください。",
    },
    "eco2_1500": {
        "check": lambda d: d["eco2"] >= 1500,
        "message": "CO2濃度がかなり高いです。すぐに換気してください。",
    },
    "heat_stroke": {
        "check": lambda d: d["temperature"] >= 28 and d["humidity"] >= 70,
        "message": "室温と湿度が高くなっています。熱中症に注意してください。",
    },
    "tvoc_1000": {
        "check": lambda d: d["tvoc"] >= 1000,
        "message": "空気中のVOCが高い値を示しています。換気をお勧めします。",
    },
}

_room_client = None


def _get_room_client():
    """Get or create a cached BOCCO emo room client."""
    global _room_client
    if _room_client is not None:
        return _room_client

    from emo_platform import Client, Tokens

    client = Client(
        tokens=Tokens(
            access_token=BOCCO_ACCESS_TOKEN,
            refresh_token=BOCCO_REFRESH_TOKEN,
        ),
        use_cached_credentials=True,
    )
    _room_client = client.create_room_client(BOCCO_ROOM_ID)
    log.info("BOCCO emo room client created for room %s", BOCCO_ROOM_ID)
    return _room_client


def load_state() -> dict:
    if not os.path.exists(ALERT_STATE_PATH):
        return {key: None for key in THRESHOLDS}
    with open(ALERT_STATE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict):
    with open(ALERT_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_cooled_down(state: dict, key: str) -> bool:
    last = state.get(key)
    if last is None:
        return True
    last_dt = datetime.fromisoformat(last)
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
    return elapsed >= ALERT_COOLDOWN_MIN


def speak_bocco(message: str) -> bool:
    if not BOCCO_ACCESS_TOKEN or not BOCCO_ROOM_ID:
        log.warning("BOCCO emo credentials not configured, skipping alert")
        return False

    try:
        room_client = _get_room_client()
        room_client.send_msg(message)
        log.info("BOCCO emo spoke: %s", message)
        return True
    except Exception:
        log.exception("BOCCO emo API call failed")
        return False


def push_lametric(data: dict):
    """Push alert data to LaMetric (optional, never raises)."""
    if not LAMETRIC_DEVICE_IP or not LAMETRIC_API_KEY:
        return

    try:
        icon = "a27283"  # warning red
        frames = [
            {"icon": icon, "text": f"CO2: {int(data['eco2'])}ppm"},
            {"icon": "i2056", "text": f"{data['temperature']:.1f}C"},
            {"icon": "i863", "text": f"{data['humidity']:.1f}%"},
        ]
        url = f"http://{LAMETRIC_DEVICE_IP}:8080/api/v2/widget/update/{LAMETRIC_APP_ID}/{LAMETRIC_WIDGET_ID}"
        requests.post(
            url,
            auth=("dev", LAMETRIC_API_KEY),
            json={"frames": frames},
            timeout=10,
        )
        log.info("LaMetric alert pushed: CO2=%dppm", data["eco2"])
    except Exception:
        log.exception("LaMetric push failed (non-critical)")


def check_and_alert(data: dict):
    state = load_state()

    for key, threshold in THRESHOLDS.items():
        if not threshold["check"](data):
            continue
        if not is_cooled_down(state, key):
            continue

        log.info("Alert triggered: %s", key)
        if speak_bocco(threshold["message"]):
            state[key] = datetime.now(timezone.utc).isoformat()
            push_lametric(data)

    save_state(state)
