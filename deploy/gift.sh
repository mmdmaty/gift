#!/usr/bin/env bash
# Raha Gift server menu — installed as /usr/local/bin/gift by deploy/install.sh
#
#   gift                 interactive menu
#   gift start|stop|restart|status

set -uo pipefail

APP_NAME="raha-gift"
APP_USER="raha"
APP_DIR="/opt/raha_gift"
ENV_FILE="/etc/raha_gift/raha_gift.env"

c_green=$'\e[32m'; c_yellow=$'\e[33m'; c_red=$'\e[31m'; c_bold=$'\e[1m'; c_reset=$'\e[0m'

if [[ $EUID -ne 0 ]]; then
    exec sudo "$0" "$@"
fi

manage() {
    sudo -u "$APP_USER" env $(grep -v '^#' "$ENV_FILE" | xargs) \
        "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" "$@"
}

site_state() {
    if systemctl is-active --quiet "$APP_NAME"; then
        echo "${c_green}running${c_reset}"
    else
        echo "${c_red}stopped${c_reset}"
    fi
}

pause() { read -rp "Press Enter to continue..." _; }

confirm() {
    local answer
    read -rp "$1 Type 'yes' to confirm: " answer
    [[ "$answer" == "yes" ]]
}

ask_days() {
    local days
    read -rp "Only delete items older than how many days? (0 = everything) [0]: " days
    days="${days:-0}"
    [[ "$days" =~ ^[0-9]+$ ]] || { echo "${c_red}Not a number.${c_reset}" >&2; return 1; }
    echo "$days"
}

start_site()   { systemctl start "$APP_NAME" && echo "${c_green}Site started.${c_reset}"; }
stop_site()    { systemctl stop "$APP_NAME" && echo "${c_yellow}Site stopped.${c_reset}"; }
restart_site() { systemctl restart "$APP_NAME" && echo "${c_green}Site restarted.${c_reset}"; }

show_status() {
    echo "Site:  $(site_state)"
    echo "Nginx: $(systemctl is-active nginx)"
    echo
    echo "${c_bold}Disk:${c_reset}"
    df -h / | tail -1 | awk '{print "  used " $3 " of " $2 " (" $5 "), free " $4}'
    echo "  chat media: $(du -sh "$APP_DIR/media/chat" 2>/dev/null | cut -f1 || echo 0)"
    echo "  database:   $(du -sh "$APP_DIR/db.sqlite3" 2>/dev/null | cut -f1 || echo 0)"
}

delete_messages() {
    local days
    days="$(ask_days)" || return
    local scope="ALL chat messages"
    [[ "$days" -gt 0 ]] && scope="chat messages older than $days days"
    confirm "${c_red}This permanently deletes $scope and their attachments.${c_reset}" || { echo "Cancelled."; return; }
    manage cleanup_chat --messages --older-than "$days"
    # reclaim the space SQLite keeps after deletes
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" -c \
        "import sqlite3; sqlite3.connect('$APP_DIR/db.sqlite3').execute('VACUUM')"
}

delete_media() {
    local days
    days="$(ask_days)" || return
    local scope="ALL chat media (photos, files, voice messages)"
    [[ "$days" -gt 0 ]] && scope="chat media older than $days days"
    confirm "${c_red}This permanently deletes $scope. Text messages are kept.${c_reset}" || { echo "Cancelled."; return; }
    echo "Chat media before: $(du -sh "$APP_DIR/media/chat" 2>/dev/null | cut -f1 || echo 0)"
    manage cleanup_chat --media --older-than "$days"
}

show_logs() { journalctl -u "$APP_NAME" -n 50 --no-pager; }

case "${1:-}" in
    start)   start_site; exit ;;
    stop)    stop_site; exit ;;
    restart) restart_site; exit ;;
    status)  show_status; exit ;;
    "")      ;;
    *)       echo "Usage: gift [start|stop|restart|status]"; exit 1 ;;
esac

while true; do
    clear
    echo "${c_bold}=========== Raha Gift ===========${c_reset}"
    echo "  Site is: $(site_state)"
    echo "---------------------------------"
    echo "  1) Start site"
    echo "  2) Stop site"
    echo "  3) Restart site"
    echo "  4) Status & disk usage"
    echo "  5) Delete chat messages"
    echo "  6) Delete chat media"
    echo "  7) Show site logs"
    echo "  0) Exit"
    echo "---------------------------------"
    read -rp "Choose: " choice
    echo
    case "$choice" in
        1) start_site ;;
        2) stop_site ;;
        3) restart_site ;;
        4) show_status ;;
        5) delete_messages ;;
        6) delete_media ;;
        7) show_logs ;;
        0|q) exit 0 ;;
        *) echo "Invalid choice." ;;
    esac
    echo
    pause
done
