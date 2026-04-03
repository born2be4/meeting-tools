# Telemost Meeting Notes Fetcher

Скрипт для автоматического получения расшифровок встреч Яндекс.Телемост из почты.

## Пайплайн

```
Яндекс.Почта (IMAP) → скачать .txt → Shared Brain + Ирида → Ким в TG
```

## Настройка

### Вариант 1: Пароль приложения (проще)

1. Зайди в https://id.yandex.ru/security/app-passwords
2. Создай пароль для "Почта"
3. Задай переменную:
   ```bash
   export YANDEX_APP_PASSWORD="сгенерированный-пароль"
   ```

### Вариант 2: OAuth (QR код)

1. Зарегистрируй приложение: https://oauth.yandex.ru/client/new
   - Название: "Telemost Fetcher"
   - Платформа: **Устройство** (device)
   - Права: `mail:imap_full`
   - Redirect URI: не нужен (device flow)
2. Запиши `client_id` и `client_secret`
3. Задай переменные:
   ```bash
   export YANDEX_OAUTH_CLIENT_ID="id"
   export YANDEX_OAUTH_CLIENT_SECRET="secret"
   ```
4. Запусти авторизацию:
   ```bash
   python3 fetcher.py --auth
   ```
   Отсканируй QR код, введи код на странице Яндекса.

## Использование

```bash
# Первый запуск — авторизация
python3 fetcher.py --auth

# Забрать расшифровки + Brain + Iris
python3 fetcher.py --all

# Только забрать (без Brain/Iris)
python3 fetcher.py --fetch --dry-run

# Cron: каждые 30 минут
*/30 * * * * cd /Users/kimbubnov/.openclaw/workspace/scripts/telemost-fetcher && python3 fetcher.py --all >> /tmp/telemost-fetcher.log 2>&1
```

## Файлы

- `fetcher.py` — основной скрипт
- `tokens.json` — OAuth токены (автосоздаётся)
- `state.json` — обработанные UID (автосоздаётся)
- `notes/` — сохранённые расшифровки .txt
- `pending_iris/` — маркеры для отправки через Ириду

## Конфигурация

| Переменная | Описание |
|---|---|
| `YANDEX_APP_PASSWORD` | Пароль приложения (приоритет) |
| `YANDEX_OAUTH_CLIENT_ID` | OAuth client_id |
| `YANDEX_OAUTH_CLIENT_SECRET` | OAuth client_secret |
| `BRAIN_API_KEY` | Ключ Shared Brain (дефолт встроен) |
