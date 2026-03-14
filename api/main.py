import os

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "home")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "air_quality")

app = FastAPI(title="Pneuma API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()


@app.get("/api/latest")
def get_latest():
    query = f"""
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -1h)
          |> filter(fn: (r) => r._measurement == "environment")
          |> last()
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    tables = query_api.query(query)
    if not tables or not tables[0].records:
        return {"error": "no data"}

    record = tables[0].records[0]
    fields = [
        "temperature", "humidity", "pressure", "illuminance",
        "noise", "eco2", "tvoc", "discomfort_index", "heat_stroke",
    ]
    result = {
        "timestamp": record.get_time().isoformat(),
        "location": record.values.get("location", ""),
    }
    for f in fields:
        result[f] = record.values.get(f)
    return result


@app.get("/api/history")
def get_history(hours: int = Query(default=24, ge=1, le=168)):
    query = f"""
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r._measurement == "environment")
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    tables = query_api.query(query)
    results = []
    for table in tables:
        for record in table.records:
            row = {
                "timestamp": record.get_time().isoformat(),
                "location": record.values.get("location", ""),
            }
            for f in ["temperature", "humidity", "pressure", "illuminance",
                       "noise", "eco2", "tvoc", "discomfort_index", "heat_stroke"]:
                row[f] = record.values.get(f)
            results.append(row)
    return results


@app.get("/api/summary")
def get_summary():
    latest = get_latest()
    if "error" in latest:
        return latest
    return {
        "eco2": latest.get("eco2"),
        "temperature": latest.get("temperature"),
        "humidity": latest.get("humidity"),
        "eco2_alert": (latest.get("eco2") or 0) >= 1000,
    }


@app.get("/health")
def health():
    try:
        healthy = client.ping()
        return {"status": "ok" if healthy else "degraded", "influxdb": healthy}
    except Exception as e:
        return {"status": "error", "influxdb": False, "detail": str(e)}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
