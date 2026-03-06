#!/usr/bin/env python3
"""
send_telegram.py

Reads the formatted meal plan message and sends it to a Telegram chat.
"""

import os
import sys

import requests


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> dict:
    """Send a message via the Telegram Bot API.

    Splits into multiple messages if text exceeds Telegram's 4096 char limit.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # Telegram max message length is 4096 characters
    MAX_LEN = 4000  # Leave some margin

    chunks = []
    if len(text) <= MAX_LEN:
        chunks = [text]
    else:
        # Split on double newlines to keep sections together
        sections = text.split("\n\n")
        current_chunk = ""
        for section in sections:
            if len(current_chunk) + len(section) + 2 > MAX_LEN:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = section
            else:
                current_chunk += "\n\n" + section if current_chunk else section
        if current_chunk:
            chunks.append(current_chunk.strip())

    last_response = None
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        last_response = resp.json()

        if not last_response.get("ok"):
            # If Markdown parsing fails, retry without it
            payload["parse_mode"] = None
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            last_response = resp.json()

    return last_response


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        sys.exit(1)

    msg_file = "telegram_message.txt"
    if not os.path.exists(msg_file):
        print(f"ERROR: {msg_file} not found. Run generate_meal_plan.py first.")
        sys.exit(1)

    with open(msg_file, "r") as f:
        message = f.read()

    print(f"Sending message ({len(message)} chars) to chat {chat_id}...")
    result = send_telegram_message(bot_token, chat_id, message)
    print(f"Sent! Message ID: {result.get('result', {}).get('message_id')}")


if __name__ == "__main__":
    main()
