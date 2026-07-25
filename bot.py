import os
import sys
import asyncio
import threading
import logging
import html as _html

from flask import Flask, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ----------------------------- Logging -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("userbot")

# --------------------------- Config (env) --------------------------
try:
    API_ID = int(os.environ["API_ID"])
    API_HASH = os.environ["API_HASH"]
except KeyError as e:
    log.error("Falta variable de entorno obligatoria: %s", e)
    sys.exit(1)

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
PORT = int(os.environ.get("PORT", 10000))

# ------------------------- Flask (el "cebo") -----------------------
app = Flask(__name__)


@app.route("/")
def health():
    return "🟢 User-bot vivo", 200


@app.route("/status")
def status():
    return jsonify({"status": "ok", "service": "userbot"}), 200


def run_flask():
    log.info("Flask escuchando en 0.0.0.0:%s", PORT)
    app.run(host="0.0.0.0", port=PORT, use_reloader=False, debug=False)


# --------------------------- Telethon ------------------------------
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


@client.on(events.NewMessage(pattern=r"(?i)^/ping$"))
async def ping(event):
    await event.reply("🏓 Pong!")


@client.on(events.NewMessage(pattern=r"(?i)^/info$"))
async def info(event):
    chat = event.chat
    title = getattr(chat, "title", None) or getattr(chat, "first_name", "chat privado")
    await event.reply(
        f"📌 Chat: {title}\n"
        f"🆔 Chat ID: {event.chat_id}\n"
        f"👤 Tu ID: {event.sender_id}"
    )


@client.on(events.NewMessage(pattern=r"(?i)^/start$"))
async def start(event):
    await event.reply("⚙️ User-bot corriendo. Comandos: /ping /info /start")


# ===================== BIENVENIDA A NUEVOS MIEMBROS =====================
WELCOME_CHAT_ID = -1001862654376   # ID de tu grupo (ya puesto)


@client.on(events.ChatAction)
async def bienvenida(event):
    log.info(
        "🔔 ChatAction | chat_id=%s | joined=%s | added=%s",
        event.chat_id, event.user_joined, event.user_added,
    )
    if event.chat_id != WELCOME_CHAT_ID:
        log.info("   ↳ ignorado: no es mi grupo (%s)", WELCOME_CHAT_ID)
        return
    if not (event.user_joined or event.user_added):
        log.info("   ↳ ignorado: no es un ingreso")
        return
    try:
        users = await event.get_users()
    except Exception as e:
        log.warning("   ⚠️ No pude resolver los usuarios nuevos: %r", e)
        return
    log.info("   ✅ Ingreso detectado. Nuevos: %s", [(u.id, u.first_name) for u in users])
    for user in users:
        nombre = _html.escape(user.first_name or "amigo")
        mencion = f'<a href="tg://user?id={user.id}">{nombre}</a>'
        texto = (
            f"Hola {mencion}, bienvenido al grupo, "
            f'si quieres una cuenta gratis le puedes escribir a '
            f'<a href="https://t.me/Akiubame">@Akiubame</a> 👋'
        )
        try:
            await client.send_message(event.chat_id, texto, parse_mode="html")
            log.info("   📨 Bienvenida ENVIADA a user_id=%s", user.id)
        except Exception as e:
            log.warning("   ❌ FALLO al enviar bienvenida: %r", e)
# ========================================================================


# =================== 🩺 DIAGNÓSTICO TEMPORAL ============================
# 1) /probe : lo escribís VOS en el grupo. Confirma que el bot VE el grupo,
#    que PUEDE escribir ahí, y te muestra el chat_id REAL (re-chequea el ID).
@client.on(events.NewMessage(pattern=r"(?i)^/probe$", outgoing=True))
async def probe(event):
    log.info("🧪 /probe recibido | chat_id=%s | chat=%s", event.chat_id, getattr(event.chat, "title", "?"))
    try:
        await event.reply(f"✅ probe ok — chat_id={event.chat_id}")
        log.info("🧪 /probe: respuesta ENVIADA")
    except Exception as e:
        log.warning("🧪 /probe: FALLO al responder (¿permiso de escritura?): %r", e)


# 2) Logger de mensajes de texto del grupo (solo entrantes de OTRAS cuentas).
#    Si otra cuenta escribe algo en el grupo, acá debe aparecer 📩.
@client.on(events.NewMessage(chats=WELCOME_CHAT_ID))
async def diag_grupo(event):
    if event.out:
        return  # tus propios mensajes no, para no duplicar con /probe
    txt = (event.text or "")[:40].replace("\n", " ")
    log.info("📩 MSG en grupo | sender=%s | text=%r", event.sender_id, txt)
# ========================================================================


# ----------------------------- Main --------------------------------
async def main():
    if not SESSION_STRING:
        log.error("SESSION_STRING está vacía.")
        sys.exit(1)
    try:
        await client.connect()
    except Exception as e:
        log.error("No se pudo conectar a Telegram: %s", e)
        sys.exit(1)
    if not await client.is_user_authorized():
        log.error("Sesión inválida o expirada.")
        sys.exit(1)
    me = await client.get_me()
    log.info("✅ User-bot conectado como @%s (ID %s)", me.username, me.id)
    await client.run_until_disconnected()


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Apagando...")
