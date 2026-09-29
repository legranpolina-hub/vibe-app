"""VIBE-бот: отвечает на /start приветствием и кнопкой Mini App.

Работает через long polling (getUpdates), поэтому ему не нужен свой сервер:
его запускает GitHub Actions (.github/workflows/bot.yml). Токен берётся
из секрета репозитория BOT_TOKEN.

Подарочная ссылка: t.me/vibe_places_bot?start=<код>. Если sha256(код) есть
в data.json → app.giftCodes, бот присылает кнопку, открывающую VIBE+,
и делает подарочной кнопку меню этого пользователя.
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

TOKEN = os.environ["BOT_TOKEN"]
API = "https://api.telegram.org/bot" + TOKEN + "/"
APP_URL = "https://legranpolina-hub.github.io/vibe-app/"
RUN_SECONDS = int(os.environ.get("RUN_SECONDS", str(5 * 3600 + 40 * 60)))

WELCOME = (
    "Привет! Это VIBE ✨\n"
    "Найдём, куда сходить сегодня рядом с тобой: одно место под настроение "
    "или целый маршрут на вечер.\n\n"
    "Жми кнопку ниже или «Открыть VIBE» слева от поля ввода."
)
GIFT = (
    "Привет! Тебе подарили VIBE+ ✦\n"
    "Безлимитные «Удиви меня» и маршруты на весь вечер уже открыты.\n\n"
    "Жми кнопку ниже, чтобы начать."
)
OTHER = "Открой VIBE кнопкой ниже, всё самое интересное там ✨"


def call(method, payload=None, timeout=70):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(API + method, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def gift_hashes():
    # подарочные коды хранятся в data.json приложения, как и для самого Mini App
    try:
        with urllib.request.urlopen(APP_URL + "data.json?v=" + str(int(time.time())), timeout=20) as r:
            return set(json.load(r).get("app", {}).get("giftCodes", []))
    except Exception as e:
        print("data.json error:", e)
        return set()


def button(text, url):
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": url}}]]}


def handle(msg, hashes):
    chat = msg.get("chat", {})
    if chat.get("type") != "private":
        return
    chat_id, text = chat["id"], (msg.get("text") or "").strip()
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        if code and hashlib.sha256(code.encode()).hexdigest() in hashes:
            url = APP_URL + "?gift=" + urllib.parse.quote(code)
            call("sendMessage", {"chat_id": chat_id, "text": GIFT, "reply_markup": button("Открыть VIBE+", url)})
            # кнопка меню у этого человека тоже будет открывать подарочную версию
            call("setChatMenuButton", {"chat_id": chat_id, "menu_button": {"type": "web_app", "text": "Открыть VIBE", "web_app": {"url": url}}})
            print("gift start", chat_id)
            return
        call("sendMessage", {"chat_id": chat_id, "text": WELCOME, "reply_markup": button("Открыть VIBE", APP_URL)})
        print("start", chat_id)
        return
    call("sendMessage", {"chat_id": chat_id, "text": OTHER, "reply_markup": button("Открыть VIBE", APP_URL)})


def main():
    call("deleteWebhook", {"drop_pending_updates": False})
    hashes, hashes_at = gift_hashes(), time.time()
    offset, stop_at = None, time.time() + RUN_SECONDS
    print("bot started")
    while time.time() < stop_at:
        if time.time() - hashes_at > 600:
            hashes, hashes_at = gift_hashes() or hashes, time.time()
        try:
            params = {"timeout": 50, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset
            res = call("getUpdates", params)
        except Exception as e:
            print("poll error:", e)
            time.sleep(5)
            continue
        for u in res.get("result", []):
            offset = u["update_id"] + 1
            if "message" in u:
                try:
                    handle(u["message"], hashes)
                except Exception as e:
                    print("handle error:", e)
    # подтверждаем обработанные обновления, чтобы следующий запуск их не повторил
    if offset:
        try:
            call("getUpdates", {"offset": offset, "timeout": 0})
        except Exception:
            pass
    print("bot finished")


if __name__ == "__main__":
    main()
