import logging
import os
import random
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from alert import check_and_alert

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SENSOR_PORT = os.getenv("SENSOR_PORT", "/dev/ttyUSB0")
INTERVAL_SEC = int(os.getenv("INTERVAL_SEC", "60"))
LOCATION_TAG = os.getenv("LOCATION_TAG", "living_room")
MOCK_SENSOR = os.getenv("MOCK_SENSOR", "false").lower() == "true"

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "home")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "air_quality")


_sensor_conn = None

ERROR_LABELS = {0: "communication", 1: "out_of_range", 2: "frozen", 3: "initialization"}
ERROR_SENSORS = ["temperature", "humidity", "light", "pressure", "noise", "tvoc", "eco2"]


def read_error_status():
    """Read error status register (0x5401) and return dict of sensor errors."""
    raw = _sensor_conn.get(0x5401)
    payload = raw[2:]  # skip address bytes
    errors = {}
    for i, name in enumerate(ERROR_SENSORS):
        if i >= len(payload):
            break
        byte = payload[i]
        if byte:
            flags = [label for bit, label in ERROR_LABELS.items() if byte & (1 << bit)]
            errors[name] = flags
            log.warning("Sensor error: %s = %s (0x%02x)", name, flags, byte)
    return errors


def read_sensor_real():
    """Read data from the real OMRON 2JCIE-BU01 sensor."""
    global _sensor_conn
    from omron_2jcie_bu01 import Omron2JCIE_BU01

    if _sensor_conn is None:
        _sensor_conn = Omron2JCIE_BU01.serial(SENSOR_PORT)
        log.info("Sensor serial connection opened on %s", SENSOR_PORT)

    raw = _sensor_conn.latest_data_long()
    return {
        "temperature": float(raw.temperature),
        "humidity": float(raw.humidity),
        "pressure": float(raw.pressure),
        "illuminance": float(raw.light),
        "noise": float(raw.noise),
        "eco2": float(raw.eCO2),
        "tvoc": float(raw.eTVOC),
        "discomfort_index": float(raw.thi),
        "heat_stroke": float(raw.wbgt),
    }


def read_sensor_mock():
    """Generate realistic mock sensor data for development."""
    return {
        "temperature": round(random.uniform(20.0, 28.0), 2),
        "humidity": round(random.uniform(40.0, 70.0), 2),
        "pressure": round(random.uniform(1005.0, 1020.0), 2),
        "illuminance": round(random.uniform(50.0, 500.0), 1),
        "noise": round(random.uniform(30.0, 55.0), 2),
        "eco2": round(random.uniform(400.0, 1200.0), 0),
        "tvoc": round(random.uniform(10.0, 500.0), 0),
        "discomfort_index": round(random.uniform(65.0, 80.0), 2),
        "heat_stroke": round(random.uniform(18.0, 28.0), 2),
    }


read_sensor = read_sensor_mock if MOCK_SENSOR else read_sensor_real


def write_to_influx(client: InfluxDBClient, data: dict):
    """Write sensor data to InfluxDB."""
    write_api = client.write_api(write_options=SYNCHRONOUS)
    point = (
        Point("environment")
        .tag("location", LOCATION_TAG)
        .time(datetime.now(timezone.utc), WritePrecision.S)
    )
    for field, value in data.items():
        point = point.field(field, value)
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)


def main():
    mode = "MOCK" if MOCK_SENSOR else f"SENSOR ({SENSOR_PORT})"
    log.info("Starting collector: mode=%s, interval=%ds, location=%s", mode, INTERVAL_SEC, LOCATION_TAG)

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

    while True:
        try:
            data = read_sensor()
            log.info("Read: temp=%.1f°C hum=%.1f%% eco2=%.0fppm", data["temperature"], data["humidity"], data["eco2"])
        except Exception:
            log.exception("Sensor read failed, skipping cycle")
            time.sleep(INTERVAL_SEC)
            continue

        if not MOCK_SENSOR:
            try:
                errors = read_error_status()
                if "eco2" in errors:
                    data["eco2_error"] = True
                if "tvoc" in errors:
                    data["tvoc_error"] = True
            except Exception:
                log.exception("Error status read failed")

        try:
            write_to_influx(client, data)
        except Exception:
            log.exception("InfluxDB write failed, will retry next cycle")

        try:
            check_and_alert(data)
        except Exception:
            log.exception("Alert check failed")

        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
