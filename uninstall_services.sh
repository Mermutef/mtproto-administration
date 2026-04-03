#!/bin/bash
if [ "$1" = "--bot" ]; then
    systemctl stop mtproto-bot
    systemctl disable mtproto-bot
    rm -f /etc/systemd/system/mtproto-bot.service
    echo "Бот удалён"
elif [ "$1" = "--web" ]; then
    systemctl stop mtproto-webadmin
    systemctl disable mtproto-webadmin
    rm -f /etc/systemd/system/mtproto-webadmin.service
    echo "Веб-админка удалена"
elif [ "$1" = "--all" ]; then
    systemctl stop mtproto-bot mtproto-webadmin
    systemctl disable mtproto-bot mtproto-webadmin
    rm -f /etc/systemd/system/mtproto-bot.service /etc/systemd/system/mtproto-webadmin.service
    echo "Оба сервиса удалены"
else
    echo "Использование: $0 --bot | --web | --all"
fi
systemctl daemon-reload