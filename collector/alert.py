import json
import logging
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

log = logging.getLogger(__name__)

BOCCO_API_KEY = os.getenv("BOCCO_API_KEY", "")
BOCCO_ROOM_ID = os.getenv("BOCCO_ROOM_ID", "")
ALERT_COOLDOWN_MIN = int(os.getenv("ALERT_COOLDOWN_MIN", "30"))
ALERT_STATE_PATH = os.getenv("ALERT_STATE_PATH", "./alert_state.json")

BOCCO_API_BASE = "https://api.bocco.me/alpha"

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
    if not BOCCO_API_KEY or not BOCCO_ROOM_ID:
        log.warning("BOCCO emo credentials not configured, skipping alert")
        return False

    try:
        resp = requests.post(
            f"{BOCCO_API_BASE}/rooms/{BOCCO_ROOM_ID}/messages",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={
                "apikey": BOCCO_API_KEY,
                "message": message,
                "media": "text",
            },
            timeout=10,
        )
        resp.raise_for_status()
        log.info("BOCCO emo spoke: %s", message)
        return True
    except Exception:
        log.exception("BOCCO emo API call failed")
        return False


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

    save_state(state)
