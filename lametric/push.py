"""Manual test script for LaMetric push.

Production alerts are handled by collector/alert.py.
This script is for standalone testing:
    python lametric/push.py
"""
import logging
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

API_BASE = f"http://localhost:{os.getenv('API_PORT', '8000')}"
DEVICE_IP = os.getenv("LAMETRIC_DEVICE_IP", "")
API_KEY = os.getenv("LAMETRIC_API_KEY", "")
APP_ID = os.getenv("LAMETRIC_APP_ID", "")
WIDGET_ID = os.getenv("LAMETRIC_WIDGET_ID", "")

ICON_NORMAL = "i3764"   # cloud icon
ICON_WARNING = "a27283"  # warning red


def fetch_summary() -> dict:
    resp = requests.get(f"{API_BASE}/api/summary", timeout=10)
    resp.raise_for_status()
    return resp.json()


def push_to_lametric(summary: dict):
    icon = ICON_WARNING if summary.get("eco2_alert") else ICON_NORMAL
    frames = [
        {"icon": icon, "text": f"CO2: {int(summary['eco2'])}ppm"},
        {"icon": "i2056", "text": f"{summary['temperature']:.1f}°C"},
        {"icon": "i863", "text": f"{summary['humidity']:.1f}%"},
    ]

    url = f"http://{DEVICE_IP}:8080/api/v2/widget/update/{APP_ID}/{WIDGET_ID}"
    resp = requests.post(
        url,
        auth=("dev", API_KEY),
        json={"frames": frames},
        timeout=10,
    )
    resp.raise_for_status()
    log.info("Pushed to LaMetric: CO2=%dppm temp=%.1f°C hum=%.1f%%",
             summary["eco2"], summary["temperature"], summary["humidity"])


def main():
    try:
        summary = fetch_summary()
    except Exception:
        log.exception("Failed to fetch summary from API")
        sys.exit(1)

    try:
        push_to_lametric(summary)
    except Exception:
        log.exception("Failed to push to LaMetric")
        sys.exit(1)


if __name__ == "__main__":
    main()
