#!/usr/bin/env python3
"""
Bitrix24 Integration Client
Отправка сообщений в чат, создание задач, получение данных.
Используется через webhook bot1@semily.ru.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List


# === CONFIG ===

WEBHOOK_BASE = os.environ.get(
    "BITRIX_WEBHOOK_BASE",
    ""
)


def _call(method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Вызов Bitrix24 REST API через webhook."""
    url = f"{WEBHOOK_BASE.rstrip('/')}/{method}"
    
    if params:
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
    else:
        req = urllib.request.Request(url)
    
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body[:500]}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"Error calling {method}: {e}", file=sys.stderr)
        raise


# === CHAT ===

def get_dialog(dialog_id: str) -> Dict:
    """Получить информацию о диалоге/чате."""
    return _call("im.dialog.get", {"DIALOG_ID": dialog_id})


def send_message(dialog_id: str, message: str) -> Dict:
    """Отправить сообщение в чат.
    
    dialog_id: 
        - "chatNNN" для групповых чатов
        - "NNN" (user_id) для личных сообщений
    """
    return _call("im.message.add", {
        "DIALOG_ID": dialog_id,
        "MESSAGE": message,
    })


def list_chats(limit: int = 50) -> List[Dict]:
    """Список доступных чатов."""
    result = _call("im.recent.list", {"LIMIT": limit})
    return result.get("result", {}).get("items", [])


# === TASKS ===

def create_task(
    title: str,
    description: str = "",
    responsible_id: int = 0,
    deadline: Optional[str] = None,
    priority: int = 1,
    group_id: int = 0,
    tags: Optional[List[str]] = None,
) -> Dict:
    """Создать задачу в Bitrix24.
    
    priority: 0=low, 1=normal, 2=high
    deadline: ISO format or "YYYY-MM-DD"
    """
    fields = {
        "TITLE": title,
        "DESCRIPTION": description,
        "PRIORITY": str(priority),
    }
    
    if responsible_id:
        fields["RESPONSIBLE_ID"] = str(responsible_id)
    if deadline:
        fields["DEADLINE"] = deadline
    if group_id:
        fields["GROUP_ID"] = str(group_id)
    if tags:
        fields["TAGS"] = tags
    
    return _call("tasks.task.add", {"fields": fields})


def get_task(task_id: int) -> Dict:
    """Получить задачу по ID."""
    return _call("tasks.task.get", {"taskId": task_id})


def list_tasks(
    filter: Optional[Dict] = None,
    limit: int = 50,
) -> Dict:
    """Список задач с фильтром."""
    params = {"limit": limit}
    if filter:
        params["filter"] = filter
    return _call("tasks.task.list", params)


def complete_task(task_id: int) -> Dict:
    """Завершить задачу."""
    return _call("tasks.task.complete", {"taskId": task_id})


# === USERS ===

def get_user(user_id: int) -> Dict:
    """Получить пользователя по ID."""
    return _call("user.get", {"ID": user_id})


def search_users(query: str) -> Dict:
    """Поиск пользователей."""
    return _call("user.search", {"FIND": query})


# === MEETING NOTES INTEGRATION ===

def send_meeting_summary(
    dialog_id: str,
    meeting_date: str,
    summary: str,
    full_text_path: Optional[str] = None,
) -> Dict:
    """Отправить саммари встречи в Bitrix-чат."""
    message = f"📋 **Конспект встречи {meeting_date}**\n\n{summary}"
    
    if full_text_path:
        message += f"\n\n📎 Полный текст: {full_text_path}"
    
    return send_message(dialog_id, message)


def create_meeting_tasks(
    meeting_date: str,
    tasks: List[Dict],
    group_id: int = 0,
) -> List[Dict]:
    """Создать задачи из протокола встречи.
    
    tasks: [{"title": "...", "responsible_id": NNN, "deadline": "..."}, ...]
    """
    results = []
    for t in tasks:
        deadline = t.get("deadline")
        if not deadline:
            # Default: 3 business days
            deadline = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        result = create_task(
            title=f"[Встреча {meeting_date}] {t['title']}",
            description=t.get("description", ""),
            responsible_id=t.get("responsible_id", 0),
            deadline=deadline,
            group_id=group_id,
            tags=["meeting", meeting_date],
        )
        results.append(result)
    
    return results


# === CLI ===

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bitrix24 Integration")
    sub = parser.add_subparsers(dest="cmd")
    
    # Chat
    chat_send = sub.add_parser("chat-send", help="Send message to chat")
    chat_send.add_argument("dialog_id")
    chat_send.add_argument("message")
    
    chat_list = sub.add_parser("chat-list", help="List recent chats")
    
    # Tasks
    task_create = sub.add_parser("task-create", help="Create task")
    task_create.add_argument("title")
    task_create.add_argument("--desc", default="")
    task_create.add_argument("--responsible", type=int, default=0)
    task_create.add_argument("--deadline", default="")
    task_create.add_argument("--group", type=int, default=0)
    
    task_list = sub.add_parser("task-list", help="List tasks")
    task_list.add_argument("--status", default="")
    
    # Meeting
    meeting = sub.add_parser("meeting-send", help="Send meeting summary to chat")
    meeting.add_argument("dialog_id")
    meeting.add_argument("date")
    meeting.add_argument("summary")
    
    args = parser.parse_args()
    
    if args.cmd == "chat-send":
        r = send_message(args.dialog_id, args.message)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    
    elif args.cmd == "chat-list":
        chats = list_chats()
        for c in chats:
            ctype = c.get("type", "?")
            title = c.get("title", "?")
            cid = c.get("id", "?")
            print(f"  [{ctype}] {title} (id={cid})")
    
    elif args.cmd == "task-create":
        r = create_task(args.title, args.desc, args.responsible, args.deadline or None, group_id=args.group)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    
    elif args.cmd == "task-list":
        f = {}
        if args.status:
            f["STATUS"] = args.status
        r = list_tasks(f)
        tasks = r.get("result", {}).get("tasks", [])
        for t in tasks[:20]:
            print(f"  #{t.get('id')} [{t.get('status')}] {t.get('title')}")
    
    elif args.cmd == "meeting-send":
        r = send_meeting_summary(args.dialog_id, args.date, args.summary)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
