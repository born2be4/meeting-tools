# Bitrix24 Integration

Python-клиент для Bitrix24 REST API через webhook.

## Возможности
- Отправка сообщений в чаты (`im.message.add`)
- Создание задач (`tasks.task.add`)
- Список чатов и задач
- Отправка саммари встреч в чат
- Создание задач из протокола встречи

## Настройка

```bash
export BITRIX_WEBHOOK_BASE="https://your-domain.bitrix24.ru/rest/USER_ID/WEBHOOK_TOKEN/"
```

## Использование

### CLI
```bash
# Отправить сообщение в чат
python3 bitrix_client.py chat-send "chat123" "Привет!"

# Список чатов
python3 bitrix_client.py chat-list

# Создать задачу
python3 bitrix_client.py task-create "Подготовить отчёт" --responsible 6025 --deadline 2026-04-10

# Отправить саммари встречи
python3 bitrix_client.py meeting-send "chat123" "03.04.2026" "Обсудили бюджет Q2..."
```

### Как библиотека
```python
from bitrix_client import send_message, create_task, send_meeting_summary

# Chat
send_message("chat123", "Текст сообщения")

# Task
create_task("Задача из встречи", responsible_id=6025, deadline="2026-04-10")

# Meeting summary → chat + tasks
send_meeting_summary("chat123", "03.04.2026", "Ключевые решения:...")
create_meeting_tasks("03.04.2026", [
    {"title": "Подготовить бюджет", "responsible_id": 6025},
    {"title": "Согласовать план", "responsible_id": 1234},
])
```

## Правила
- Перед отправкой в чат проверять доступность через `im.dialog.get`
- `ACCESS_ERROR` = проблема прав/членства webhook-аккаунта в чате
- Для Semily: использовать webhook `bot1@semily.ru` (user_id=6025)
