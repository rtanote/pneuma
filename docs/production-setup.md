# Production デプロイ手順

対象: Ubuntu 24.04 LTS サーバー
配置先: `~/dev/pneuma`

## 前提

- Docker + Docker Compose がインストール済み
- Python 3.12+ がインストール済み
- Git でリポジトリにアクセス可能

## 1. USB センサードライバ

```bash
# FTDI USB ドライバ（2JCIE-BU01 用 udev ルール）
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0590", ATTR{idProduct}=="00d4", \
  RUN+="/sbin/modprobe ftdi_sio", \
  RUN+="/bin/sh -c \"echo 0590 00d4 > /sys/bus/usb-serial/drivers/ftdi_sio/new_id\""' \
  | sudo tee /etc/udev/rules.d/99-2jcie-bu01.rules

sudo udevadm control --reload-rules
sudo usermod -aG dialout $USER
# 再ログインが必要
```

## 2. プロジェクト配置

```bash
cd ~/dev
git clone git@github.com:rtanote/pneuma.git
cd pneuma
```

## 3. Python 仮想環境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r collector/requirements.txt -r api/requirements.txt -r lametric/requirements.txt
```

## 4. 環境変数

```bash
cp .env.example .env
# .env を編集:
#   SENSOR_PORT=/dev/ttyUSB0
#   MOCK_SENSOR=false
#   BOCCO_ACCESS_TOKEN=...
#   BOCCO_REFRESH_TOKEN=...
#   BOCCO_ROOM_ID=...
#   LAMETRIC_DEVICE_IP=...
#   LAMETRIC_API_KEY=...
```

## 5. Docker Compose (InfluxDB + Grafana)

```bash
docker compose up -d
docker compose ps
```

確認:
- InfluxDB: http://localhost:8086
- Grafana: http://localhost:3000 (admin / admin)

## 6. systemd サービス

systemd ファイル内のパスを環境に合わせて編集してからコピー:

```bash
sudo cp systemd/pneuma-collector.service /etc/systemd/system/
sudo cp systemd/pneuma-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pneuma-collector pneuma-api
```

ステータス確認:
```bash
sudo systemctl status pneuma-collector
sudo systemctl status pneuma-api
sudo journalctl -u pneuma-collector -f
```

## 7. cron (LaMetric push)

```bash
crontab -e
```

以下を追記（パスは環境に合わせて変更）:
```cron
# Pneuma LaMetric Push
# ====================
PNEUMA_DIR=$HOME/dev/pneuma
PNEUMA_PYTHON=$HOME/dev/pneuma/.venv/bin/python
PNEUMA_LOG=$HOME/dev/pneuma/logs

# 5分ごと - LaMetric 表示更新
*/5 * * * * cd $PNEUMA_DIR && $PNEUMA_PYTHON lametric/push.py >> $PNEUMA_LOG/lametric.log 2>&1

# 毎月1日 - ログローテーション
0 0 1 * * find $PNEUMA_LOG -name "*.log" -mtime +30 -delete
```

ログディレクトリ作成:
```bash
mkdir -p ~/dev/pneuma/logs
```

## 8. 動作確認

```bash
# センサー認識
ls /dev/ttyUSB*

# collector ログ
sudo journalctl -u pneuma-collector -f

# API
curl http://localhost:8000/api/latest

# Grafana ダッシュボード
# ブラウザで http://<server-ip>:3000

# Docker コンテナ
docker compose ps
```

## 更新手順

```bash
cd ~/dev/pneuma
git pull
source .venv/bin/activate
pip install -r collector/requirements.txt -r api/requirements.txt
sudo systemctl restart pneuma-collector pneuma-api
```
