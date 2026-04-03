#!/usr/bin/env python3
"""
Telemost Meeting Notes Fetcher
Забирает расшифровки встреч из Яндекс.Почты (Телемост) → Shared Brain + Ирида.

Почта: kimbubnov@rizz.market
Отправитель: keeper@telemost.yandex.ru
Тема: "Конспект встречи ..."
Вложение: .txt

Авторизация: Yandex OAuth2 device code flow (QR) или пароль приложения.
"""

import imaplib
import email
import email.header
import base64
import json
import os
import sys
import time
import re
import hashlib
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.header import decode_header

# === CONFIG ===
MAIL_USER = "kimbubnov@rizz.market"
IMAP_HOST = "imap.yandex.ru"
IMAP_PORT = 993
SENDER_FILTER = "keeper@telemost.yandex.ru"
SUBJECT_PREFIX = "Конспект встречи"

SCRIPT_DIR = Path(__file__).parent
TOKEN_FILE = SCRIPT_DIR / "tokens.json"
STATE_FILE = SCRIPT_DIR / "state.json"
NOTES_DIR = SCRIPT_DIR / "notes"

BRAIN_URL = "http://localhost:8084"
BRAIN_API_KEY = os.environ.get("BRAIN_API_KEY", "25b56119a78fe9200ad91f2a70a32239")

# Yandex OAuth
OAUTH_CLIENT_ID = os.environ.get("YANDEX_OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("YANDEX_OAUTH_CLIENT_SECRET", "")

# Fallback: app password
APP_PASSWORD = os.environ.get("YANDEX_APP_PASSWORD", "")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# === OAUTH DEVICE CODE FLOW ===

def oauth_device_code_flow():
    """Yandex OAuth2 device code flow — показывает QR код для авторизации."""
    import urllib.request
    import urllib.parse

    if not OAUTH_CLIENT_ID:
        print("ERROR: YANDEX_OAUTH_CLIENT_ID не задан.")
        print("Зарегистрируй приложение: https://oauth.yandex.ru/client/new")
        print("Права: mail:imap_full")
        print("Тип: Устройство (device)")
        sys.exit(1)

    # Step 1: получить device_code
    data = urllib.parse.urlencode({
        "client_id": OAUTH_CLIENT_ID,
    }).encode()
    req = urllib.request.Request("https://oauth.yandex.ru/device/code", data=data)
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())

    device_code = result["device_code"]
    user_code = result["user_code"]
    verification_url = result["verification_url"]
    interval = result.get("interval", 5)
    expires_in = result.get("expires_in", 300)

    full_url = f"{verification_url}?code={user_code}"

    print()
    print("=" * 50)
    print("  АВТОРИЗАЦИЯ ЯНДЕКС ПОЧТЫ")
    print("=" * 50)
    print()
    print(f"  1. Открой ссылку или отсканируй QR:")
    print(f"     {full_url}")
    print()
    print(f"  2. Код: {user_code}")
    print()

    # Попробовать сгенерировать QR в терминале
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(full_url)
        qr.make()
        qr.print_ascii(invert=True)
    except ImportError:
        try:
            # fallback: qrencode CLI
            subprocess.run(
                ["qrencode", "-t", "UTF8", full_url],
                check=True, capture_output=False
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("  (pip install qrcode для QR в терминале)")

    print()
    print("  Жду авторизации...")
    print()

    # Step 2: поллим токен
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        try:
            data = urllib.parse.urlencode({
                "grant_type": "device_code",
                "code": device_code,
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
            }).encode()
            req = urllib.request.Request("https://oauth.yandex.ru/token", data=data)
            resp = urllib.request.urlopen(req)
            tokens = json.loads(resp.read())

            if "access_token" in tokens:
                tokens["obtained_at"] = time.time()
                TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
                log("✅ OAuth авторизация успешна! Токены сохранены.")
                return tokens["access_token"]
        except urllib.error.HTTPError as e:
            body = json.loads(e.read())
            if body.get("error") == "authorization_pending":
                continue
            elif body.get("error") == "slow_down":
                interval += 1
                continue
            else:
                print(f"ERROR: {body}")
                sys.exit(1)

    print("ERROR: Timeout — авторизация не пройдена за отведённое время.")
    sys.exit(1)


def refresh_oauth_token():
    """Обновить access_token через refresh_token."""
    import urllib.request
    import urllib.parse

    if not TOKEN_FILE.exists():
        return None

    tokens = json.loads(TOKEN_FILE.read_text())
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None

    try:
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
        }).encode()
        req = urllib.request.Request("https://oauth.yandex.ru/token", data=data)
        resp = urllib.request.urlopen(req)
        new_tokens = json.loads(resp.read())

        if "access_token" in new_tokens:
            new_tokens["obtained_at"] = time.time()
            TOKEN_FILE.write_text(json.dumps(new_tokens, indent=2))
            log("Токен обновлён через refresh_token.")
            return new_tokens["access_token"]
    except Exception as e:
        log(f"Ошибка refresh: {e}")

    return None


def get_access_token():
    """Получить актуальный access_token."""
    if TOKEN_FILE.exists():
        tokens = json.loads(TOKEN_FILE.read_text())
        expires_in = tokens.get("expires_in", 3600)
        obtained_at = tokens.get("obtained_at", 0)
        # Обновляем за 5 минут до истечения
        if time.time() < obtained_at + expires_in - 300:
            return tokens["access_token"]
        # Попробовать refresh
        token = refresh_oauth_token()
        if token:
            return token

    # Нужна свежая авторизация
    return oauth_device_code_flow()


# === IMAP ===

def imap_connect_oauth(access_token):
    """Подключение к IMAP через XOAUTH2."""
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    auth_string = f"user={MAIL_USER}\x01auth=Bearer {access_token}\x01\x01"
    mail.authenticate("XOAUTH2", lambda x: auth_string.encode())
    return mail


def imap_connect_password():
    """Подключение к IMAP через пароль приложения."""
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(MAIL_USER, APP_PASSWORD)
    return mail


def imap_connect():
    """Подключиться к IMAP — OAuth или пароль."""
    if APP_PASSWORD:
        log("Подключение через пароль приложения...")
        return imap_connect_password()
    else:
        token = get_access_token()
        log("Подключение через OAuth...")
        return imap_connect_oauth(token)


def decode_subject(raw_subject):
    """Декодировать тему письма."""
    parts = decode_header(raw_subject)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def load_state():
    """Загрузить state (обработанные UID)."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed_uids": [], "last_run": None}


def save_state(state):
    """Сохранить state."""
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


# === FETCH & PROCESS ===

def fetch_new_meetings():
    """Основной цикл: забрать новые расшифровки."""
    state = load_state()
    processed = set(state.get("processed_uids", []))
    NOTES_DIR.mkdir(exist_ok=True)

    mail = imap_connect()
    mail.select("INBOX")

    # Ищем письма от keeper@telemost.yandex.ru
    # Яндекс IMAP не поддерживает UTF-8 в SEARCH, используем charset
    log(f"Поиск: FROM={SENDER_FILTER}")

    # Яндекс IMAP: ищем по FROM части адреса (домен)
    status, data = mail.search(None, 'FROM', '"telemost.yandex.ru"')
    if status != "OK":
        log(f"Ошибка поиска: {status}")
        mail.logout()
        return []

    msg_ids = data[0].split()
    log(f"Найдено писем: {len(msg_ids)}")

    new_notes = []

    for msg_id in msg_ids:
        uid_resp = mail.fetch(msg_id, "(UID)")
        uid_match = re.search(rb"UID (\d+)", uid_resp[1][0])
        uid = uid_match.group(1).decode() if uid_match else msg_id.decode()

        if uid in processed:
            continue

        log(f"Обработка UID {uid}...")

        status, msg_data = mail.fetch(msg_id, "(RFC822)")
        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_subject(msg.get("Subject", ""))
        date_str = msg.get("Date", "")
        log(f"  Тема: {subject}")
        log(f"  Дата: {date_str}")

        # Извлечь номер встречи из темы
        meeting_match = re.search(r"№?(\d{5,})", subject)
        meeting_id = meeting_match.group(1) if meeting_match else "unknown"

        # Извлечь дату из темы или заголовка
        date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", subject)
        if date_match:
            meeting_date = date_match.group(1)
        else:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                meeting_date = dt.strftime("%Y-%m-%d")
            except Exception:
                meeting_date = datetime.now().strftime("%Y-%m-%d")

        # Ищем .txt вложение
        txt_content = None
        txt_filename = None

        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    # Декодировать имя файла
                    decoded_parts = decode_header(filename)
                    fname = ""
                    for fp, fc in decoded_parts:
                        if isinstance(fp, bytes):
                            fname += fp.decode(fc or "utf-8", errors="replace")
                        else:
                            fname += fp
                    filename = fname

                if filename and filename.lower().endswith(".txt"):
                    txt_content = part.get_payload(decode=True)
                    txt_filename = filename
                    log(f"  Вложение: {filename}")
                    break

        if not txt_content:
            log(f"  ⚠️ Нет .txt вложения, пропускаю.")
            processed.add(uid)
            continue

        # Декодируем текст
        try:
            text = txt_content.decode("utf-8")
        except UnicodeDecodeError:
            text = txt_content.decode("cp1251", errors="replace")

        # Сохраняем локально
        safe_date = meeting_date.replace(".", "-")
        note_path = NOTES_DIR / f"{safe_date}_{meeting_id}.txt"
        note_path.write_text(text, encoding="utf-8")
        log(f"  Сохранено: {note_path}")

        new_notes.append({
            "uid": uid,
            "subject": subject,
            "meeting_id": meeting_id,
            "meeting_date": meeting_date,
            "filename": txt_filename,
            "text": text,
            "path": str(note_path),
        })

        processed.add(uid)

    state["processed_uids"] = list(processed)
    save_state(state)
    mail.logout()

    log(f"Новых расшифровок: {len(new_notes)}")
    return new_notes


# === SHARED BRAIN ===

def write_to_brain(note):
    """Записать расшифровку в Shared Brain."""
    import urllib.request

    # Формируем краткое описание для brain
    text_preview = note["text"][:500].replace("\n", " ")
    content = (
        f"Конспект встречи Телемост #{note['meeting_id']} от {note['meeting_date']}. "
        f"Начало расшифровки: {text_preview}..."
    )

    payload = json.dumps({
        "content": content,
        "type": "event",
        "source_agent": "hephaestus",
        "tags": ["telemost", "meeting", "transcript", note["meeting_date"]],
    }).encode()

    req = urllib.request.Request(
        f"{BRAIN_URL}/memory",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": BRAIN_API_KEY,
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        log(f"  Brain: записано (id={result.get('id', '?')})")
        return True
    except Exception as e:
        log(f"  Brain: ошибка — {e}")
        return False


# === IRIS NOTIFICATION ===

def format_protocol(note):
    """Форматировать протокол встречи для отправки через Ириду."""
    text = note["text"]

    # Базовая структура протокола
    lines = text.strip().split("\n")

    # Пытаемся извлечь участников и ключевые моменты
    protocol = f"📋 **Конспект встречи** #{note['meeting_id']}\n"
    protocol += f"📅 Дата: {note['meeting_date']}\n"
    protocol += f"📎 Тема: {note['subject']}\n\n"

    # Берём первые ~3000 символов текста (TG лимит ~4096)
    max_len = 3000
    if len(text) > max_len:
        protocol += text[:max_len] + "\n\n... (полный текст сохранён)"
    else:
        protocol += text

    return protocol


def notify_iris(note):
    """Отправить протокол через Ириду Киму."""
    protocol = format_protocol(note)

    # Через openclaw sessions_send к Ириде — или через TG напрямую
    # Используем файл-маркер для cron pickup
    marker_dir = SCRIPT_DIR / "pending_iris"
    marker_dir.mkdir(exist_ok=True)

    marker = marker_dir / f"{note['meeting_id']}.json"
    marker.write_text(json.dumps({
        "meeting_id": note["meeting_id"],
        "meeting_date": note["meeting_date"],
        "subject": note["subject"],
        "protocol": protocol,
        "note_path": note["path"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2))

    log(f"  Iris marker: {marker}")
    return True


# === MAIN ===

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Telemost Meeting Notes Fetcher")
    parser.add_argument("--auth", action="store_true", help="Только авторизация (QR)")
    parser.add_argument("--fetch", action="store_true", help="Забрать новые расшифровки")
    parser.add_argument("--all", action="store_true", help="Fetch + Brain + Iris")
    parser.add_argument("--dry-run", action="store_true", help="Без записи в Brain/Iris")
    args = parser.parse_args()

    if args.auth:
        if APP_PASSWORD:
            log("Используется пароль приложения, OAuth не нужен.")
            return
        get_access_token()
        return

    if args.fetch or args.all or (not args.auth):
        notes = fetch_new_meetings()

        if not notes:
            log("Нет новых расшифровок.")
            return

        for note in notes:
            log(f"\nОбработка: {note['subject']}")

            if not args.dry_run:
                # Brain
                write_to_brain(note)

                # Iris notification
                notify_iris(note)

            log(f"  ✅ Готово: {note['meeting_date']} #{note['meeting_id']}")

        log(f"\nИтого обработано: {len(notes)} расшифровок.")


if __name__ == "__main__":
    main()
