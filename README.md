# 📋 Meeting Tools

Набор инструментов для автоматизации работы со встречами:
- Получение конспектов из Яндекс.Телемост
- Интеграция с Bitrix24 (чат + задачи)
- Сохранение в Shared Brain

## Архитектура

```
Яндекс.Почта (IMAP)
    │
    ▼
┌──────────────────┐
│ Telemost Fetcher │  ← cron каждые 2 часа
│  (telemost-fetcher/fetcher.py)
└────────┬─────────┘
         │
    ┌────┴────┐
    ▼         ▼
Shared    Файлы .txt
Brain     (notes/)
    │
    ▼
┌──────────────────┐
│   AI Agent       │  ← Ирида / Нокс
│   (summary)      │
└────────┬─────────┘
         │
    ┌────┴────┐
    ▼         ▼
Telegram   Bitrix24
(протокол) (чат + задачи)
```

## Компоненты

### 1. [Telemost Fetcher](telemost-fetcher/)
Забирает расшифровки встреч из Яндекс.Почты:
- IMAP подключение (OAuth или пароль приложения)
- Фильтр: `keeper@telemost.yandex.ru`, тема "Конспект встречи"
- Скачивает .txt вложения
- Записывает в Shared Brain
- Работает по cron (каждые 2 часа)

### 2. [Bitrix Integration](bitrix-integration/)
Python-клиент для Bitrix24 REST API:
- Отправка сообщений в чаты
- Создание задач из протокола встречи
- Список чатов и задач
- CLI + библиотека

### 3. [OpenClaw Skills](skills/)
Скиллы для AI-агентов:
- `telemost-notes` — инструкция для агента по работе с конспектами
- Агент делает summary, отправляет через Telegram/Bitrix

## Быстрый старт

### Telemost Fetcher
```bash
cd telemost-fetcher

# Вариант 1: пароль приложения
export YANDEX_APP_PASSWORD="your-password"

# Забрать конспекты
python3 fetcher.py --all
```

### Bitrix Client
```bash
cd bitrix-integration

export BITRIX_WEBHOOK_BASE="https://your-domain.bitrix24.ru/rest/USER_ID/TOKEN/"

# Отправить сообщение
python3 bitrix_client.py chat-send "chat123" "Привет!"

# Создать задачу
python3 bitrix_client.py task-create "Задача из встречи"
```

## Полный пайплайн (пример)

```bash
# 1. Забрать новые конспекты
cd telemost-fetcher && python3 fetcher.py --all

# 2. Прочитать последний конспект
LATEST=$(ls -t notes/*.txt | head -1)
echo "Файл: $LATEST"

# 3. Сделать summary (через AI-агента или вручную)
SUMMARY="Обсудили бюджет Q2, решили увеличить на 15%..."

# 4. Отправить в Bitrix-чат
cd ../bitrix-integration
python3 bitrix_client.py meeting-send "chat123" "$(date +%d.%m.%Y)" "$SUMMARY"

# 5. Создать задачи
python3 bitrix_client.py task-create "Подготовить новый бюджет" --responsible 6025 --deadline 2026-04-10
```

## Деплой

### Текущий
- **Telemost Fetcher**: cron на OpenClaw (Гефест, каждые 2ч)
- **Bitrix Client**: используется Иридой через exec
- **Shared Brain**: localhost:8084

### Новый сервер
1. Клонировать репо
2. Настроить `.env` для каждого компонента
3. Добавить в cron / systemd

## Переменные окружения

| Переменная | Компонент | Описание |
|---|---|---|
| `YANDEX_APP_PASSWORD` | telemost-fetcher | Пароль приложения Яндекс |
| `YANDEX_OAUTH_CLIENT_ID` | telemost-fetcher | OAuth client_id (альтернатива) |
| `YANDEX_OAUTH_CLIENT_SECRET` | telemost-fetcher | OAuth client_secret |
| `BITRIX_WEBHOOK_BASE` | bitrix-integration | Webhook URL Bitrix24 |
| `BRAIN_API_KEY` | telemost-fetcher | Ключ Shared Brain |
