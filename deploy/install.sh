#!/usr/bin/env bash
# Raha Gift easy installer — Ubuntu 24.04+ / Debian 13+
#
#   sudo bash deploy/install.sh
#
# Copies the project to /opt/raha_gift, sets up a Python venv, a systemd
# service (daphne), nginx, a Let's Encrypt certificate, and the `gift` menu.
# Safe to re-run to update the code: the database and media are kept.

set -euo pipefail

APP_NAME="raha-gift"
APP_USER="raha"
APP_DIR="/opt/raha_gift"
CONF_DIR="/etc/raha_gift"
ENV_FILE="$CONF_DIR/raha_gift.env"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
NGINX_SITE="/etc/nginx/sites-available/$APP_NAME"
PORT=8000

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

c_green=$'\e[32m'; c_yellow=$'\e[33m'; c_red=$'\e[31m'; c_reset=$'\e[0m'
info() { echo "${c_green}==>${c_reset} $*"; }
warn() { echo "${c_yellow}[!]${c_reset} $*"; }
die()  { echo "${c_red}[x]${c_reset} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root: sudo bash $0"
command -v apt-get >/dev/null || die "Only Debian/Ubuntu (apt) is supported."
[[ -f "$SRC_DIR/manage.py" ]] || die "manage.py not found in $SRC_DIR"

# ---------------------------------------------------------------- questions
existing_domain=""
[[ -f "$ENV_FILE" ]] && existing_domain="$(grep -oP '^DOMAIN=\K.*' "$ENV_FILE" || true)"

read -rp "Domain (e.g. rahagift.ir)${existing_domain:+ [$existing_domain]}: " DOMAIN
DOMAIN="${DOMAIN:-$existing_domain}"
DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die "Invalid domain: $DOMAIN"

read -rp "Also serve www.$DOMAIN? (its DNS must point here too) [y/N]: " WITH_WWW
DOMAINS=("$DOMAIN")
[[ "${WITH_WWW,,}" == y* ]] && DOMAINS+=("www.$DOMAIN")

read -rp "Email for Let's Encrypt (expiry notices): " EMAIL
[[ "$EMAIL" == *@* ]] || die "Invalid email."

# ---------------------------------------------------------------- packages
info "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx rsync curl >/dev/null

python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' \
    || die "Django 6.1 needs Python 3.12+ (found $(python3 --version)). Use Ubuntu 24.04+ or Debian 13+."

# ---------------------------------------------------------------- DNS check
SERVER_IP="$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)"
for d in "${DOMAINS[@]}"; do
    resolved="$(getent ahostsv4 "$d" | awk '{print $1; exit}' || true)"
    if [[ -z "$resolved" ]]; then
        warn "$d does not resolve yet. Add an A record pointing to ${SERVER_IP:-this server}."
    elif [[ -n "$SERVER_IP" && "$resolved" != "$SERVER_IP" ]]; then
        warn "$d points to $resolved, but this server is $SERVER_IP (fine if behind a proxy)."
    fi
done

# ---------------------------------------------------------------- code
id "$APP_USER" &>/dev/null || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

FIRST_INSTALL=0
[[ -f "$APP_DIR/manage.py" ]] || FIRST_INSTALL=1

info "Copying project to $APP_DIR..."
mkdir -p "$APP_DIR"
RSYNC_EXCLUDES=(--exclude venv --exclude .venv --exclude __pycache__ --exclude .git
                --exclude .claude --exclude .env --exclude staticfiles --exclude '*.pyc')
if [[ $FIRST_INSTALL -eq 0 ]]; then
    # updates never overwrite live data
    RSYNC_EXCLUDES+=(--exclude /db.sqlite3 --exclude /media)
fi
rsync -a --delete "${RSYNC_EXCLUDES[@]}" "$SRC_DIR/" "$APP_DIR/"
mkdir -p "$APP_DIR/media"

# ---------------------------------------------------------------- env file
mkdir -p "$CONF_DIR"
if [[ -f "$ENV_FILE" ]] && grep -q '^DJANGO_SECRET_KEY=' "$ENV_FILE"; then
    SECRET_KEY="$(grep -oP '^DJANGO_SECRET_KEY=\K.*' "$ENV_FILE")"
else
    SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
fi
HTTPS_ON="$( [[ -f "$ENV_FILE" ]] && grep -oP '^DJANGO_HTTPS=\K.*' "$ENV_FILE" || echo 0)"

write_env() {
    local hosts origins
    hosts="$(IFS=,; echo "${DOMAINS[*]}")"
    origins=""
    for d in "${DOMAINS[@]}"; do origins+="https://$d,http://$d,"; done
    cat > "$ENV_FILE" <<EOF
DOMAIN=$DOMAIN
DJANGO_SECRET_KEY=$SECRET_KEY
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=$hosts
DJANGO_CSRF_TRUSTED_ORIGINS=${origins%,}
DJANGO_HTTPS=$1
EOF
    chmod 640 "$ENV_FILE"
    chown root:"$APP_USER" "$ENV_FILE"
}
write_env "${HTTPS_ON:-0}"

# ---------------------------------------------------------------- python
info "Setting up Python environment..."
[[ -x "$APP_DIR/venv/bin/python" ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirments.txt"

chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

manage() {
    sudo -u "$APP_USER" env $(grep -v '^#' "$ENV_FILE" | xargs) \
        "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" "$@"
}
info "Running migrations and collecting static files..."
manage migrate --noinput
manage collectstatic --noinput -v 0

# ---------------------------------------------------------------- systemd
info "Creating systemd service $APP_NAME..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Raha Gift (Django / daphne)
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/venv/bin/daphne --bind 127.0.0.1 --port $PORT --proxy-headers config.asgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now "$APP_NAME" >/dev/null
systemctl restart "$APP_NAME"

# ---------------------------------------------------------------- nginx
info "Configuring nginx..."
cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAINS[*]};

    client_max_body_size 20M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias $APP_DIR/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        # overwrite (not append) so clients can't spoof their IP and dodge the login ban
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
    }
}
EOF
ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/$APP_NAME"
# nginx (www-data) needs to read static and media
chmod o+x "$APP_DIR"
chmod -R o+rX "$APP_DIR/staticfiles" "$APP_DIR/media"
nginx -t
systemctl reload nginx

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow 'Nginx Full' >/dev/null
fi

# ---------------------------------------------------------------- SSL
info "Requesting SSL certificate from Let's Encrypt..."
CERTBOT_ARGS=()
for d in "${DOMAINS[@]}"; do CERTBOT_ARGS+=(-d "$d"); done
if certbot --nginx --non-interactive --agree-tos --redirect -m "$EMAIL" "${CERTBOT_ARGS[@]}"; then
    write_env 1
    systemctl restart "$APP_NAME"
    SITE_URL="https://$DOMAIN"
else
    warn "Could not get a certificate (check DNS), site is on plain HTTP for now."
    warn "Once DNS is fixed, re-run this installer or: sudo certbot --nginx -d $DOMAIN"
    SITE_URL="http://$DOMAIN"
fi

# ---------------------------------------------------------------- gift menu
install -m 755 "$APP_DIR/deploy/gift.sh" /usr/local/bin/gift
sed -i 's/\r$//' /usr/local/bin/gift

# ---------------------------------------------------------------- admin user
if [[ $FIRST_INSTALL -eq 1 ]]; then
    read -rp "Create an admin (superuser) account now? [y/N]: " MAKE_ADMIN
    [[ "${MAKE_ADMIN,,}" == y* ]] && manage createsuperuser
fi

echo
info "Done! Site: $SITE_URL"
info "Manage it any time with:  sudo gift"
