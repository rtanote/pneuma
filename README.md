# Pneuma - Air Quality Monitor

OMRON 2JCIE-BU01 USB environment sensor monitoring system.

## Architecture

```
2JCIE-BU01 (USB)
      │
      ▼
┌─────────────────────────────────┐
│  collector.py → InfluxDB 2.x   │
│  alert.py    → BOCCO emo API   │
│  main.py     ← FastAPI :8000   │
│  Grafana            :3000      │
└─────────────────────────────────┘
      │
      ├── Grafana Web UI
      ├── LaMetric (push.py)
      └── BOCCO emo (voice alerts)
```

## Development Setup (Windows 11)

### Prerequisites

- [Conda](https://docs.conda.io/) (Miniconda or Anaconda)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 1. Create conda environment

```bash
conda env create -f environment.yml
conda activate pneuma
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env: set MOCK_SENSOR=true for development without sensor
```

### 3. Start InfluxDB + Grafana

```bash
docker compose up -d
```

- InfluxDB UI: http://localhost:8086 (admin / adminpassword)
- Grafana: http://localhost:3000 (admin / admin)

### 4. Run the collector

```bash
cd collector && python collector.py
```

### 5. Run the API server

```bash
cd api && uvicorn main:app --reload
```

API endpoints:
- `GET /api/latest` - Latest sensor readings
- `GET /api/history?hours=24` - Historical data
- `GET /api/summary` - LaMetric summary
- `GET /health` - Health check

## Production Setup (Ubuntu)

See [docs/production-setup.md](docs/production-setup.md) for deployment instructions.

## Environment Variables

See [.env.example](.env.example) for all configuration options.
