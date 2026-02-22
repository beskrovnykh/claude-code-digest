#!/usr/bin/env python3
"""Publish a post from drafts/ to Telegram channel."""

import sys
import os
import re
import shutil
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
import json

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@claudecode_digest")
DRAFTS = Path(__file__).parent / "posts" / "drafts"
PUBLISHED = Path(__file__).parent / "posts" / "published"


def md_to_telegram(text: str) -> str:
    """Convert markdown draft to Telegram-friendly text.

    Strips the H1 title line and converts markdown formatting
    to Telegram MarkdownV2 compatible format.
    """
    lines = text.strip().splitlines()

    # Skip H1 title (e.g. "# Пост 1: Вступительный")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]

    text = "\n".join(lines).strip()

    # **bold** -> Telegram bold (keep as is, works in MarkdownV2)
    # — dashes are fine
    # #hashtags at end — keep as is

    return text


def escape_md2(text: str) -> str:
    """Escape special chars for MarkdownV2, preserving **bold** and formatting."""
    # First, extract bold sections
    parts = re.split(r'(\*\*.*?\*\*)', text)
    result = []
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            inner = part[2:-2]
            inner = re.sub(r'([_\[\]()~`>#+\-=|{}.!])', r'\\\1', inner)
            result.append(f'*{inner}*')
        else:
            part = re.sub(r'([_\[\]()~`>#+\-=|{}.!])', r'\\\1', part)
            result.append(part)
    return ''.join(result)


def send_message(text: str) -> dict:
    """Send message to Telegram channel."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }).encode()

    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urlopen(req)
    return json.loads(resp.read())


def list_drafts() -> list[Path]:
    """List available drafts."""
    return sorted(DRAFTS.glob("*.md"))


def publish(draft_path: Path, dry_run: bool = False) -> None:
    """Publish a draft to Telegram and move to published/."""
    raw = draft_path.read_text()
    text = md_to_telegram(raw)
    escaped = escape_md2(text)

    if dry_run:
        print("=== DRY RUN ===")
        print(escaped)
        print(f"\n=== Length: {len(text)} chars ===")
        return

    result = send_message(escaped)

    if result.get("ok"):
        dest = PUBLISHED / draft_path.name
        shutil.move(str(draft_path), str(dest))
        print(f"Published: {draft_path.name}")
        print(f"Moved to: {dest}")
        msg_id = result["result"]["message_id"]
        print(f"Message ID: {msg_id}")
    else:
        print(f"Error: {result}")
        sys.exit(1)


def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set. Check .env")
        sys.exit(1)

    drafts = list_drafts()

    if not drafts:
        print("No drafts found in posts/drafts/")
        sys.exit(0)

    # Parse args
    dry_run = "--dry" in sys.argv
    file_arg = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            file_arg = arg
            break

    if file_arg:
        path = DRAFTS / file_arg if not file_arg.startswith("/") else Path(file_arg)
        if not path.exists():
            print(f"File not found: {path}")
            sys.exit(1)
    else:
        print("Available drafts:")
        for i, d in enumerate(drafts, 1):
            preview = d.read_text().splitlines()[0][:60]
            print(f"  {i}. {d.name} — {preview}")

        choice = input("\nPublish which? (number or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            return
        idx = int(choice) - 1
        path = drafts[idx]

    print(f"\nFile: {path.name}")
    print(f"Channel: {CHANNEL}")
    print(f"Mode: {'DRY RUN' if dry_run else 'PUBLISH'}")

    if not dry_run:
        confirm = input("Send? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

    publish(path, dry_run=dry_run)


if __name__ == "__main__":
    main()
