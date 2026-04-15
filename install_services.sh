#!/bin/bash

set -e

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Определяем директорию, где находится сам скрипт
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Если PROJECT_DIR не задан через окружение, используем директорию скрипта
PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"

BOT_SCRIPT="main.py"
WEB_SCRIPT="web_admin.py"
BOT_SERVICE_NAME="mtproto-bot"
WEB_SERVICE_NAME="mtproto-webadmin"
USER="root"
GROUP="root"

INSTALL_BOT=false
INSTALL_WEB=false

# Функция вывода справки
show_help() {
    cat <<EOF
Установка systemd сервисов для MTProto бота и веб-админки.

Использование:
    $0 [OPTIONS]

Опции:
    --bot         Установить только бота (mtproto-bot.service)
    --web         Установить только веб-админку (mtproto-webadmin.service)
    --all         Установить оба сервиса (то же, что --bot --web)
    --help        Показать эту справку

Примеры:
    $0 --bot           # установить только бота
    $0 --web           # установить только веб-админку
    $0 --all           # установить оба сервиса

Переменные окружения (можно задать перед запуском):
    PROJECT_DIR        путь к проекту (по умолчанию: директория скрипта)
    USER               пользователь для запуска (по умолчанию: root)
    GROUP              группа (по умолчанию: root)

EOF
}

# Разбор аргументов
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --bot)
            INSTALL_BOT=true
            shift
            ;;
        --web)
            INSTALL_WEB=true
            shift
            ;;
        --all)
            INSTALL_BOT=true
            INSTALL_WEB=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Неизвестный аргумент: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Если не выбрано ничего — показываем справку
if [ "$INSTALL_BOT" = false ] && [ "$INSTALL_WEB" = false ]; then
    echo -e "${RED}Ошибка: не указано, что устанавливать. Используйте --bot, --web или --all.${NC}"
    show_help
    exit 1
fi

# Проверяем директорию проекта
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}Ошибка: директория $PROJECT_DIR не найдена${NC}"
    exit 1
fi

# Проверяем наличие необходимых файлов
if [ "$INSTALL_BOT" = true ] && [ ! -f "$PROJECT_DIR/$BOT_SCRIPT" ]; then
    echo -e "${RED}Ошибка: $PROJECT_DIR/$BOT_SCRIPT не найден${NC}"
    exit 1
fi

if [ "$INSTALL_WEB" = true ] && [ ! -f "$PROJECT_DIR/$WEB_SCRIPT" ]; then
    echo -e "${RED}Ошибка: $PROJECT_DIR/$WEB_SCRIPT не найден${NC}"
    exit 1
fi

# Определяем путь к python3
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    echo -e "${RED}Ошибка: python3 не найден в PATH${NC}"
    exit 1
fi

echo -e "${GREEN}Настройка:${NC}"
echo "  Директория проекта: $PROJECT_DIR"
echo "  Пользователь: $USER"
echo "  Группа: $GROUP"
echo "  Python: $PYTHON_PATH"
echo ""

# Функция установки сервиса
install_service() {
    local service_name=$1
    local script_file=$2
    local description=$3
    local after_target=$4
    local requires=$5
    local service_file="/etc/systemd/system/${service_name}.service"

    echo -e "${YELLOW}Установка $service_name...${NC}"

    cat > "$service_file" <<EOF
[Unit]
Description=$description
After=$after_target
$requires

[Service]
Type=simple
User=$USER
Group=$GROUP
WorkingDirectory=$PROJECT_DIR
Environment="PYTHONUNBUFFERED=1"
ExecStart=$PYTHON_PATH $PROJECT_DIR/$script_file
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    echo -e "${GREEN}  ✓ Создан $service_file${NC}"
}

# Устанавливаем бота
if [ "$INSTALL_BOT" = true ]; then
    install_service "$BOT_SERVICE_NAME" "$BOT_SCRIPT" "MTProto Telegram Bot" "network.target" ""
fi

# Устанавливаем веб-админку
if [ "$INSTALL_WEB" = true ]; then
    install_service "$WEB_SERVICE_NAME" "$WEB_SCRIPT" "MTProto Web Admin Panel (Flask)" "network.target" ""
fi

# Перезагружаем systemd и включаем автозапуск
echo -e "\n${YELLOW}Применение изменений...${NC}"
systemctl daemon-reload

# Включаем и запускаем каждый сервис
if [ "$INSTALL_BOT" = true ]; then
    systemctl enable "$BOT_SERVICE_NAME"
    systemctl start "$BOT_SERVICE_NAME"
    echo -e "${GREEN}✓ $BOT_SERVICE_NAME включён и запущен${NC}"
fi

if [ "$INSTALL_WEB" = true ]; then
    systemctl enable "$WEB_SERVICE_NAME"
    systemctl start "$WEB_SERVICE_NAME"
    echo -e "${GREEN}✓ $WEB_SERVICE_NAME включён и запущен${NC}"
fi

# Показываем статус
echo -e "\n${GREEN}Статус установленных сервисов:${NC}"
if [ "$INSTALL_BOT" = true ]; then
    echo -e "\n${YELLOW}--- $BOT_SERVICE_NAME ---${NC}"
    systemctl status "$BOT_SERVICE_NAME" --no-pager -l | head -20
fi

if [ "$INSTALL_WEB" = true ]; then
    echo -e "\n${YELLOW}--- $WEB_SERVICE_NAME ---${NC}"
    systemctl status "$WEB_SERVICE_NAME" --no-pager -l | head -20
fi

echo -e "\n${GREEN}Установка завершена. Команды управления:${NC}"
if [ "$INSTALL_BOT" = true ]; then
    echo "  systemctl start|stop|restart $BOT_SERVICE_NAME"
    echo "  journalctl -u $BOT_SERVICE_NAME -f"
fi
if [ "$INSTALL_WEB" = true ]; then
    echo "  systemctl start|stop|restart $WEB_SERVICE_NAME"
    echo "  journalctl -u $WEB_SERVICE_NAME -f"
fi