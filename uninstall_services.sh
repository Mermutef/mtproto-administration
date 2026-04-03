#!/bin/bash

# Определяем директорию скрипта (может пригодиться, если захотим удалять файлы проекта)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"

if [ "$1" = "--bot" ]; then
    systemctl stop mtproto-bot 2>/dev/null
    systemctl disable mtproto-bot 2>/dev/null
    rm -f /etc/systemd/system/mtproto-bot.service
    echo "Бот удалён"
elif [ "$1" = "--web" ]; then
    systemctl stop mtproto-webadmin 2>/dev/null
    systemctl disable mtproto-webadmin 2>/dev/null
    rm -f /etc/systemd/system/mtproto-webadmin.service
    echo "Веб-админка удалена"
elif [ "$1" = "--all" ]; then
    systemctl stop mtproto-bot mtproto-webadmin 2>/dev/null
    systemctl disable mtproto-bot mtproto-webadmin 2>/dev/null
    rm -f /etc/systemd/system/mtproto-bot.service /etc/systemd/system/mtproto-webadmin.service
    echo "Оба сервиса удалены"
else
    echo "Использование: $0 --bot | --web | --all"
    exit 1
fi
systemctl daemon-reload