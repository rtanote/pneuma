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
      ├── macOS WidgetKit
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

### 4. Run the collector (mock mode)

```bash
python collector/collector.py
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

### System dependencies

```bash
# FTDI USB driver for 2JCIE-BU01
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0590", ATTR{idProduct}=="00d4", \
  RUN+="/sbin/modprobe ftdi_sio", \
  RUN+="/bin/sh -c \"echo 0590 00d4 > /sys/bus/usb-serial/drivers/ftdi_sio/new_id\""' \
  | sudo tee /etc/udev/rules.d/99-2jcie-bu01.rules

sudo usermod -aG dialout $USER
```

### Install InfluxDB 2.x

Follow the [official guide](https://docs.influxdata.com/influxdb/v2/install/?t=Linux).
Initial setup: Org=`home`, Bucket=`air_quality`.

### Install Grafana

Follow the [official guide](https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/).
Copy `grafana/dashboard.json` to provisioning directory for auto-loading.

### Deploy application

```bash
sudo useradd -r -s /bin/false pneuma
sudo mkdir -p /opt/pneuma /var/lib/air-monitor
sudo chown pneuma:pneuma /var/lib/air-monitor

sudo cp -r . /opt/pneuma/
cd /opt/pneuma
python -m venv venv
source venv/bin/activate
pip install -r collector/requirements.txt -r api/requirements.txt -r lametric/requirements.txt

sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now air-collector air-api air-lametric.timer
```

## Environment Variables

See [.env.example](.env.example) for all configuration options.
