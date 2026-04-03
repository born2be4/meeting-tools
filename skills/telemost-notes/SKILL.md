# Telemost Notes — Скилл получения конспектов встреч

## Описание
Инструмент для получения расшифровок встреч из Яндекс.Телемост. Забирает конспекты из почты `kimbubnov@rizz.market`, сохраняет локально и в Shared Brain, отправляет протокол Киму.

## Когда использовать
- Ким просит "покажи конспект встречи", "что было на встрече", "протокол встречи"
- Ким просит "забери новые конспекты"
- Cron-задача запрашивает проверку новых конспектов
- Нужно найти что обсуждали на конкретной встрече

## Инструмент

### Скрипт
```
/Users/kimbubnov/.openclaw/workspace/scripts/telemost-fetcher/fetcher.py
```

### Команды

#### Забрать новые конспекты (основная)
```bash
cd /Users/kimbubnov/.openclaw/workspace/scripts/telemost-fetcher && \
YANDEX_APP_PASSWORD='ibxuekfqozmyezse' python3 fetcher.py --all
```

#### Только проверить без записи в Brain
```bash
cd /Users/kimbubnov/.openclaw/workspace/scripts/telemost-fetcher && \
YANDEX_APP_PASSWORD='ibxuekfqozmyezse' python3 fetcher.py --fetch --dry-run
```

### Файлы конспектов
```
/Users/kimbubnov/.openclaw/workspace/scripts/telemost-fetcher/notes/
```
Формат имён: `DD-MM-YYYY_meetingid.txt`

### Поиск конспекта по дате
```bash
ls /Users/kimbubnov/.openclaw/workspace/scripts/telemost-fetcher/notes/ | grep "02-04-2026"
```

### Чтение конспекта
```bash
cat /Users/kimbubnov/.openclaw/workspace/scripts/telemost-fetcher/notes/02-04-2026_unknown.txt
```

## Формат протокола для отправки Киму

При отправке конспекта Киму используй этот формат:

```
📋 Конспект встречи
📅 Дата: DD.MM.YYYY
📎 Файл: [имя файла]

[Краткое содержание — 3-5 ключевых пунктов]

Полный текст: [кол-во символов] символов, сохранён в notes/
```

**НЕ отправляй полный текст** конспекта в чат — он может быть 100+ КБ.
Отправляй краткое содержание (summary) + ссылку на файл.

## Shared Brain
Конспекты автоматически записываются в Shared Brain с тегами:
- `telemost`, `meeting`, `transcript`, `YYYY-MM-DD`

Поиск по Brain:
```bash
curl -s "http://localhost:8084/memory/search?q=конспект+встречи+телемост&limit=5" \
  -H "X-Api-Key: 25b56119a78fe9200ad91f2a70a32239"
```

## Источник данных
- **Почта:** kimbubnov@rizz.market (Яндекс)
- **Отправитель:** keeper@telemost.yandex.ru
- **Тема:** "Конспект встречи от DD.MM.YYYY"
- **Вложение:** .txt файл с расшифровкой

## Cron
Автоматическая проверка каждые 2 часа (cron на Гефесте).
Новые конспекты забираются и записываются в Brain автоматически.

## Пример использования

### Ким: "Что было на встрече сегодня?"
1. Запусти `fetcher.py --all` чтобы забрать свежие
2. Найди файлы за сегодня в `notes/`
3. Прочитай файл, сделай summary
4. Отправь Киму в формате протокола

### Ким: "Покажи конспект за 30 марта"
1. Найди файл: `ls notes/ | grep "30-03-2026"`
2. Прочитай, сделай summary
3. Отправь
