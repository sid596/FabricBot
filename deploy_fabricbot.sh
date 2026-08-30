#!/bin/bash

set -e

# ================================================================
# FabricBot - DigitalOcean Deployment Script
# ================================================================
#
# Run this FROM the local FabricBot project folder:
#
#     chmod +x deploy_fabricbot.sh
#     ./deploy_fabricbot.sh
#
# This script:
#   1. Connects to the DigitalOcean server
#   2. Updates Ubuntu
#   3. Installs Python, Nginx, Git, Certbot, etc.
#   4. Creates the fabricbot system user
#   5. Uploads the current FabricBot project
#   6. Creates a Python virtual environment
#   7. Installs requirements
#   8. Creates a systemd service
#   9. Starts FabricBot with Gunicorn
#  10. Configures Nginx
#  11. Configures HTTPS with Let's Encrypt
#  12. Runs basic health checks
#
# IMPORTANT:
#   - Your DNS A record must point to the server before HTTPS setup.
#   - Your .env is copied to the server.
#   - Do NOT commit .env to GitHub.
#
# ================================================================


# ------------------------------------------------
# CONFIGURATION
# ------------------------------------------------

SERVER_IP="64.227.138.31"
SERVER_USER="root"

APP_NAME="fabricbot"
APP_DIR="/opt/fabricbot"
SERVICE_NAME="fabricbot"

# Ask for domain
echo ""
echo "================================================"
echo " FabricBot Deployment"
echo "================================================"
echo ""

read -p "Enter your domain (example: bot.yourdomain.com): " DOMAIN
read -p "Enter your email for Let's Encrypt: " SSL_EMAIL

if [ -z "$DOMAIN" ]; then
    echo "ERROR: Domain cannot be empty."
    exit 1
fi

if [ -z "$SSL_EMAIL" ]; then
    echo "ERROR: Email cannot be empty."
    exit 1
fi


# ------------------------------------------------
# LOCAL CHECKS
# ------------------------------------------------

echo ""
echo "Checking local FabricBot project..."

if [ ! -f "server.py" ]; then
    echo "ERROR: server.py not found."
    echo "Run this script from inside your FabricBot folder."
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found."
    echo "Your project should contain requirements.txt."
    exit 1
fi

if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: .env was not found."
    echo "FabricBot may fail if it requires environment variables."
    echo ""
    read -p "Continue anyway? (y/N): " CONTINUE

    if [[ "$CONTINUE" != "y" && "$CONTINUE" != "Y" ]]; then
        exit 1
    fi
fi


# ------------------------------------------------
# TEST SSH
# ------------------------------------------------

echo ""
echo "Testing SSH connection..."

ssh -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=accept-new \
    "${SERVER_USER}@${SERVER_IP}" \
    "echo 'SSH connection successful.'"


# ------------------------------------------------
# CREATE TEMPORARY ARCHIVE
# ------------------------------------------------

echo ""
echo "Preparing FabricBot project..."

TEMP_ARCHIVE="/tmp/fabricbot_deploy.tar.gz"

tar \
    --exclude=".git" \
    --exclude="__pycache__" \
    --exclude=".DS_Store" \
    --exclude="*.pyc" \
    -czf "$TEMP_ARCHIVE" .


# ------------------------------------------------
# UPLOAD PROJECT
# ------------------------------------------------

echo ""
echo "Uploading FabricBot to server..."

scp "$TEMP_ARCHIVE" \
    "${SERVER_USER}@${SERVER_IP}:/tmp/fabricbot_deploy.tar.gz"


# ------------------------------------------------
# SERVER SETUP
# ------------------------------------------------

echo ""
echo "Setting up Ubuntu server..."

ssh "${SERVER_USER}@${SERVER_IP}" \
    "APP_DIR='$APP_DIR' APP_NAME='$APP_NAME' SERVICE_NAME='$SERVICE_NAME' DOMAIN='$DOMAIN' SSL_EMAIL='$SSL_EMAIL' bash -s" <<'REMOTE_SCRIPT'

set -e

echo ""
echo "================================================"
echo " Updating Ubuntu"
echo "================================================"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get upgrade -y


echo ""
echo "================================================"
echo " Installing system packages"
echo "================================================"

apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    build-essential \
    nginx \
    git \
    curl \
    wget \
    unzip \
    certbot \
    python3-certbot-nginx


echo ""
echo "================================================"
echo " Creating FabricBot user"
echo "================================================"

if ! id "$APP_NAME" >/dev/null 2>&1; then
    useradd \
        --system \
        --create-home \
        --shell /bin/bash \
        "$APP_NAME"
fi


echo ""
echo "================================================"
echo " Preparing application directory"
echo "================================================"

mkdir -p "$APP_DIR"

rm -rf "${APP_DIR:?}/"*

tar \
    -xzf /tmp/fabricbot_deploy.tar.gz \
    -C "$APP_DIR"


echo ""
echo "================================================"
echo " Creating Python virtual environment"
echo "================================================"

python3 -m venv "$APP_DIR/venv"

"$APP_DIR/venv/bin/python" -m pip install --upgrade pip setuptools wheel


echo ""
echo "================================================"
echo " Installing Python dependencies"
echo "================================================"

"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"


echo ""
echo "================================================"
echo " Fixing permissions"
echo "================================================"

chown -R "$APP_NAME:$APP_NAME" "$APP_DIR"

chmod 600 "$APP_DIR/.env" 2>/dev/null || true


echo ""
echo "================================================"
echo " Testing Python compilation"
echo "================================================"

cd "$APP_DIR"

"$APP_DIR/venv/bin/python" -m py_compile \
    server.py \
    quotation.py \
    ai.py

echo "Python compilation successful."


echo ""
echo "================================================"
echo " Testing server import"
echo "================================================"

"$APP_DIR/venv/bin/python" -c \
    "import server; print('SERVER IMPORT OK')"


echo ""
echo "================================================"
echo " Creating systemd service"
echo "================================================"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=FabricBot WhatsApp Bot
After=network.target

[Service]
Type=simple

User=${APP_NAME}
Group=${APP_NAME}

WorkingDirectory=${APP_DIR}

EnvironmentFile=${APP_DIR}/.env

ExecStart=${APP_DIR}/venv/bin/gunicorn \
    --workers 1 \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    server:app

Restart=always
RestartSec=5

# Give Python enough time to shut down cleanly
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF


echo ""
echo "================================================"
echo " Enabling FabricBot service"
echo "================================================"

systemctl daemon-reload

systemctl enable "$SERVICE_NAME"

systemctl restart "$SERVICE_NAME"

sleep 3

systemctl --no-pager --full status "$SERVICE_NAME" || true


echo ""
echo "================================================"
echo " Configuring Nginx"
echo "================================================"

cat > "/etc/nginx/sites-available/${APP_NAME}" <<EOF
server {
    listen 80;
    listen [::]:80;

    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:5000;

        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
EOF


rm -f /etc/nginx/sites-enabled/default

ln -sf \
    "/etc/nginx/sites-available/${APP_NAME}" \
    "/etc/nginx/sites-enabled/${APP_NAME}"


echo ""
echo "Testing Nginx configuration..."

nginx -t

systemctl restart nginx


echo ""
echo "================================================"
echo " Local FabricBot health check"
echo "================================================"

curl -f http://127.0.0.1:5000/

echo ""


echo ""
echo "================================================"
echo " HTTPS SETUP"
echo "================================================"

echo ""
echo "Attempting Let's Encrypt certificate..."
echo ""

certbot \
    --nginx \
    --non-interactive \
    --agree-tos \
    --redirect \
    --email "$SSL_EMAIL" \
    -d "$DOMAIN"


echo ""
echo "================================================"
echo " FINAL CHECKS"
echo "================================================"

nginx -t

systemctl restart nginx

systemctl is-active --quiet "$SERVICE_NAME"

echo ""
echo "FabricBot service is RUNNING."

echo ""
echo "Testing HTTPS..."

curl -f "https://${DOMAIN}/"

echo ""

echo ""
echo "================================================"
echo " DEPLOYMENT COMPLETE"
echo "================================================"

echo ""
echo "FabricBot:"
echo "https://${DOMAIN}"

echo ""
echo "Webhook:"
echo "https://${DOMAIN}/webhook"

echo ""
echo "Service:"
echo "systemctl status ${SERVICE_NAME}"

echo ""
echo "Logs:"
echo "journalctl -u ${SERVICE_NAME} -f"

echo ""
echo "Restart:"
echo "systemctl restart ${SERVICE_NAME}"

echo ""

REMOTE_SCRIPT


# ------------------------------------------------
# CLEANUP
# ------------------------------------------------

rm -f "$TEMP_ARCHIVE"


echo ""
echo "================================================"
echo " Local deployment process finished"
echo "================================================"
echo ""

echo "Server:"
echo "    $SERVER_IP"

echo "Domain:"
echo "    https://$DOMAIN"

echo "Webhook:"
echo "    https://$DOMAIN/webhook"

echo ""

echo "Next step:"
echo "Update the WhatsApp/Meta webhook URL to:"
echo ""
echo "    https://$DOMAIN/webhook"
echo ""

echo "Then send a real WhatsApp message to FabricBot."
echo ""