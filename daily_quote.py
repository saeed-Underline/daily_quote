import json
import os
import sys
import requests
from openai import OpenAI

STATE_PATH = "state.json"

def load_state():
    if not os.path.exists(STATE_PATH):
        return {"previous_response_id": None}
    with open(STATE_PATH,"r", encoding="utf-8") as f:
        return json.load(f)
    
def save_state(state):
    with open(STATE_PATH,"w", encoding="utf-8") as f:
        json.dump(state, f,ensure_ascii=False, indent=2)
        
def send_telegram(bot_token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=30)
    r.raise_for_status()

def main():
    openai_api_key = os.environ["OPENAI_API_KEY"]
    telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    state = load_state()
    prev_id = state.get("previous_response_id")

    client = OpenAI(api_key=openai_api_key)

    # Your “specific matters” go here:
    prompt = (
        "Give me:\n"
        "1) One short daily quote (max 140 chars)\n"
        "2) One-sentence meaning\n"
        "3) One small action for today\n"
        "Keep it fresh and non-repetitive."
    )

    kwargs = {
        "model": "gpt-4.1-mini",  # pick your preferred model
        "input": prompt,
    }

    # Keep the same chat history across days:
    if prev_id:
        kwargs["previous_response_id"] = prev_id

    resp = client.responses.create(**kwargs)

    # Extract text output (SDK provides helpers; this is robust enough for most cases)
    text_parts = []
    for item in resp.output:
        if item.type == "message":
            for c in item.content:
                if c.type == "output_text":
                    text_parts.append(c.text)

    message = "\n".join(text_parts).strip()
    if not message:
        print("No text output found.", file=sys.stderr)
        sys.exit(1)

    send_telegram(telegram_bot_token, telegram_chat_id, message)

    # Save the response id so tomorrow continues this same “chat”
    state["previous_response_id"] = resp.id
    save_state(state)

if __name__ == "__main__":

    main()
