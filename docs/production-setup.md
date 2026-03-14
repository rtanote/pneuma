# Production デプロイ手順

対象: Ubuntu 24.04 LTS サーバー
配置先: `~/dev/pneuma`

## 前提

- Docker + Docker Compose がインストール済み
- Python 3.12+ がインストール済み
- Git でリポジトリにアクセス可能

## 1. USB センサードライバ

OMRON 2JCIE-BU01 は FTDI 社の USB-シリアル変換チップを使用しているが、
Linux カーネルの標準 `ftdi_sio` ドライバにはこのデバイスの Vendor/Product ID
(0590:00d4) が登録されていない。そのため、udev ルールで自動認識させる必要がある。

### udev ルール作成

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0590", ATTR{idProduct}=="00d4", \
  RUN+="/sbin/modprobe ftdi_sio", \
  RUN+="/bin/sh -c \"echo 0590 00d4 > /sys/bus/usb-serial/drivers/ftdi_sio/new_id\""' \
  | sudo tee /etc/udev/rules.d/99-2jcie-bu01.rules
```

このルールは以下を行う:
- `SUBSYSTEM=="usb"` — USB デバイスの接続を監視
- `ATTR{idVendor}=="0590"` — OMRON の Vendor ID でフィルタ
- `ATTR{idProduct}=="00d4"` — 2JCIE-BU01 の Product ID でフィルタ
- `modprobe ftdi_sio` — FTDI シリアルドライバをカーネルにロード
- `echo 0590 00d4 > .../new_id` — このデバイスを ftdi_sio ドライバに動的登録

### ルール反映とパーミッション

```bash
sudo udevadm control --reload-rules
sudo usermod -aG dialout $USER
# 再ログインが必要
```

- `reload-rules` で udev にルールファイルの再読み込みを指示
- シリアルデバイス (`/dev/ttyUSBx`) は `dialout` グループに属するため、実行ユーザーをこのグループに追加する
- グループ変更の反映にはログアウト→再ログインが必要

### 確認

```bash
# センサーを USB に接続した状態で:
lsusb | grep 0590          # OMRON デバイスが表示されること
ls -la /dev/ttyUSB*         # /dev/ttyUSB0 等が存在すること
```

> **Note:** USB ポートの抜き差しや他の USB-シリアルデバイスの有無により、
> デバイス番号が `/dev/ttyUSB0` ではなく `/dev/ttyUSB1` 等になる場合がある。
> `.env` の `SENSOR_PORT` を実際のデバイスパスに合わせること。

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
