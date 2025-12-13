import json
import os
import sys
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

def main():
    gemini_api_key = os.environ["OPENAI_API_KEY"]  # set this in your env
    telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    state = load_state()
    history = state.get("history", [])

    client = genai.Client(api_key=gemini_api_key)

    prompt = (
        "Give me:\n"
        "1) One short daily quote (max 140 chars)\n"
        "2) One-sentence meaning\n"
        "3) One small action for today\n"
        "Keep it fresh and non-repetitive."
    )

    # Gemini: we keep continuity by sending prior turns back in `contents`
    contents = history + [prompt]

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
    except Exception as e:
        print(f"Gemini API error: {e}", file=sys.stderr)
        raise

    message = (response.text or "").strip()
    if not message:
        print("No text output found.", file=sys.stderr)
        sys.exit(1)

    send_telegram(telegram_bot_token, telegram_chat_id, message)

    # Save a short rolling history to reduce repetition without growing forever
    history = (history + [prompt, message])[-20:]  # keep last 20 items
    state["history"] = history
    save_state(state)

if __name__ == "__main__":
    main()
