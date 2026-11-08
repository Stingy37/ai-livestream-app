#!/usr/bin/env bash
# Deploy (or redeploy) the broadcast server to the EC2 instance. Run FROM ICRN:
#
#   bash ec2/deploy.sh                 # server + website
#   bash ec2/deploy.sh --server-only   # server.py + unit only; the deployed website is left as it is
#
# Idempotent: keeps an existing API token and TLS certificate, overwrites server.py and the
# website, (re)installs the systemd unit, restarts it, checks /healthz, then copies the token and
# the certificate back to secrets/ (so src/broadcast/publisher.py can authenticate and pin TLS).
#
# Settings (environment variables, defaults shown):
#   EC2_SSH_HOST=ubuntu@54.221.147.143   EC2_SSH_KEY=~/.ssh/weather-dev
#   EC2_PUBLIC_IP=54.221.147.143         EC2_PUBLIC_DNS=ec2-54-221-147-143.compute-1.amazonaws.com
#   EC2_PORT=8443                        S3_BUCKET=weather-livestream-716747745410-dev   AWS_REGION=us-east-1
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EC2_SSH_HOST="${EC2_SSH_HOST:-ubuntu@54.221.147.143}"
EC2_SSH_KEY="${EC2_SSH_KEY:-$HOME/.ssh/weather-dev}"
EC2_PUBLIC_IP="${EC2_PUBLIC_IP:-54.221.147.143}"
EC2_PUBLIC_DNS="${EC2_PUBLIC_DNS:-ec2-54-221-147-143.compute-1.amazonaws.com}"
EC2_PORT="${EC2_PORT:-8443}"
S3_BUCKET="${S3_BUCKET:-weather-livestream-716747745410-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
KEEP_PACKAGES="${KEEP_PACKAGES:-3}"
SECRETS_DIR="$REPO_ROOT/secrets"

SERVER_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --server-only) SERVER_ONLY=1 ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

SSH_OPTS=(-o IdentitiesOnly=yes -o PasswordAuthentication=no -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 -i "$EC2_SSH_KEY")
ssh_ec2() { ssh "${SSH_OPTS[@]}" "$EC2_SSH_HOST" "$@"; }

echo "==> copying server + website to $EC2_SSH_HOST"
ssh_ec2 'mkdir -p ~/weather-livestream/html ~/weather-livestream-data/packages'
scp "${SSH_OPTS[@]}" -q "$REPO_ROOT/ec2/server.py" "$EC2_SSH_HOST:~/weather-livestream/server.py"
scp "${SSH_OPTS[@]}" -q "$REPO_ROOT/ec2/weather-livestream.service" "$EC2_SSH_HOST:~/weather-livestream/weather-livestream.service"
if [[ "$SERVER_ONLY" == "1" ]]; then
    echo "    (--server-only: website not copied)"
else
    scp "${SSH_OPTS[@]}" -q "$REPO_ROOT/html/champi-desk.html" "$EC2_SSH_HOST:~/weather-livestream/html/champi-desk.html"
fi

echo "==> configuring token, certificate and systemd unit (needs sudo on the instance)"
ssh_ec2 "EC2_PUBLIC_IP='$EC2_PUBLIC_IP' EC2_PUBLIC_DNS='$EC2_PUBLIC_DNS' EC2_PORT='$EC2_PORT' S3_BUCKET='$S3_BUCKET' AWS_REGION='$AWS_REGION' KEEP_PACKAGES='$KEEP_PACKAGES' bash -s" <<'REMOTE'
set -euo pipefail
sudo mkdir -p /etc/weather-livestream/tls
sudo chown -R ubuntu:ubuntu /etc/weather-livestream
chmod 700 /etc/weather-livestream /etc/weather-livestream/tls
ENV=/etc/weather-livestream/env
if [[ -f "$ENV" ]] && grep -q '^API_TOKEN=' "$ENV"; then
    TOKEN="$(grep '^API_TOKEN=' "$ENV" | head -1 | cut -d= -f2-)"
    echo "keeping existing API token"
else
    TOKEN="$(openssl rand -hex 32)"
    echo "generated a new API token"
fi
umask 077
cat > "$ENV" <<EOT
API_TOKEN=$TOKEN
BUCKET=$S3_BUCKET
REGION=$AWS_REGION
DATA_DIR=/home/ubuntu/weather-livestream-data
WEB_DIR=/home/ubuntu/weather-livestream/html
BIND=0.0.0.0
PORT=$EC2_PORT
CERT=/etc/weather-livestream/tls/server.crt
KEY=/etc/weather-livestream/tls/server.key
KEEP_PACKAGES=$KEEP_PACKAGES
PRESIGN_TTL=900
EOT
chmod 600 "$ENV"
if [[ ! -f /etc/weather-livestream/tls/server.crt ]]; then
    echo "generating a self-signed certificate (10 years)"
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout /etc/weather-livestream/tls/server.key -out /etc/weather-livestream/tls/server.crt \
        -subj "/CN=weather-livestream" \
        -addext "subjectAltName=IP:$EC2_PUBLIC_IP,IP:127.0.0.1,DNS:$EC2_PUBLIC_DNS,DNS:localhost" >/dev/null 2>&1
    chmod 600 /etc/weather-livestream/tls/server.key
else
    echo "keeping existing certificate"
fi
sudo cp ~/weather-livestream/weather-livestream.service /etc/systemd/system/weather-livestream.service
sudo systemctl daemon-reload
sudo systemctl enable weather-livestream >/dev/null 2>&1
sudo systemctl restart weather-livestream
for i in $(seq 1 20); do
    if curl -sk --max-time 3 "https://127.0.0.1:$EC2_PORT/healthz" | grep -q '"ok": true'; then
        echo "server healthy on port $EC2_PORT"
        exit 0
    fi
    sleep 1
done
echo "server did not become healthy; last log lines:" >&2
sudo journalctl -u weather-livestream --no-pager -n 30 >&2 || true
exit 1
REMOTE

echo "==> copying the token and certificate back to $SECRETS_DIR"
mkdir -p "$SECRETS_DIR"
umask 077
ssh_ec2 "grep '^API_TOKEN=' /etc/weather-livestream/env | cut -d= -f2-" > "$SECRETS_DIR/ec2_api_token"
ssh_ec2 "cat /etc/weather-livestream/tls/server.crt" > "$SECRETS_DIR/ec2_server.crt"
chmod 600 "$SECRETS_DIR/ec2_api_token" "$SECRETS_DIR/ec2_server.crt"
if [[ ! -s "$SECRETS_DIR/ec2_api_token" || ! -s "$SECRETS_DIR/ec2_server.crt" ]]; then
    echo "failed to fetch the token or certificate" >&2
    exit 1
fi
echo "==> done. token: $SECRETS_DIR/ec2_api_token  cert: $SECRETS_DIR/ec2_server.crt"
echo "    direct url https://$EC2_PUBLIC_IP:$EC2_PORT/ needs inbound TCP $EC2_PORT in the security group;"
echo "    until then: bash scripts/ec2_tunnel.sh  (then https://localhost:8443/)"
