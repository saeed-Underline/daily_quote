import json
import os
import sys
import re
import requests

from google import genai  # pip install google-genai  (Python 3.9+)

STATE_PATH = "state.json"


def load_state():
    if not os.path.exists(STATE_PATH):
        return {"history": []}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram(bot_token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    r.raise_for_status()


def split_answers(text: str, expected: int = 4) -> list[str]:
    """
    Try to split model output into answers for 1..expected.
    Supports formats like:
      1- ...
      1. ...
      1) ...
    Falls back to non-empty lines if numbering isn't found.
    """
    text = (text or "").strip()
    if not text:
        return []

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split by numbered headings (keeps content between them)
    # Finds "1-", "1.", "1)", etc. at line starts
    pattern = re.compile(r"(?m)^\s*(\d+)\s*[-\.\)]\s+")
    matches = list(pattern.finditer(text))

    if matches:
        parts = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            num = int(m.group(1))
            chunk = text[start:end].strip()
            if chunk:
                parts.append((num, chunk))

        # Order by number and take up to expected
        parts.sort(key=lambda x: x[0])
        answers = [chunk for _, chunk in parts[:expected]]

        # If fewer than expected, don't crash—just return what we have
        return answers

    # Fallback: split by non-empty lines
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return lines[:expected]


def main():
    # NOTE: your variable name is gemini_api_key but you're reading OPENAI_API_KEY.
    # Keep as-is if that's how you set it, but typically you'd use GEMINI_API_KEY.
    gemini_api_key = os.environ["OPENAI_API_KEY"]
    telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    state = load_state()
    history = state.get("history", [])

    client = genai.Client(api_key=gemini_api_key)

    prompt = (
        "Tell me the answer for four questions, each on a separate numbered line:\n"
        "1- Tell me something interesting that is not possible, but people often think is easy.\n"
        "2- Give me a useful psychological insight.\n"
        "3- Give me a famous Persian poem (short) and the poet's name.\n"
        "4- Give me the quote of the day.\n"
        "Keep it fresh and non-repetitive."
    )

    contents = history + [prompt]

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
    except Exception as e:
        print(f"Gemini API error: {e}", file=sys.stderr)
        raise

    full_text = (response.text or "").strip()
    if not full_text:
        print("No text output found.", file=sys.stderr)
        sys.exit(1)

    answers = split_answers(full_text, expected=4)
    if not answers:
        print("Could not split answers.", file=sys.stderr)
        sys.exit(1)

    # Send each answer as a separate Telegram message
    for i, ans in enumerate(answers, start=1):
        send_telegram(telegram_bot_token, telegram_chat_id, f"{i}) {ans}")

    # Save history (store the whole combined response, not each Telegram message)
    history = (history + [prompt, full_text])[-20:]
    state["history"] = history
    save_state(state)


if __name__ == "__main__":
    main()