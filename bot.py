import os
import sys
import asyncio
import threading
import logging
import html as _html
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, ChatAdminRequiredError, UserNotParticipantError

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


# --------------------------- Telethon ----------------==============
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


# ============== BIENVENIDA "POR PRIMER MENSAJE" (sin ser admin) ============
# (Opcional: si querés SOLO el cartel rotativo, borrá este bloque entero.)
WELCOME_CHAT_ID = -1001862654376   # tu grupo (confirmado ✅)
NUEVO_MINUTOS = 10
MODO = "auto"                      # "auto" = conservador | "loose" = agresivo

_SALUDADOS = set()
_NO_NUEVOS = {}
_TTL_NO_NUEVO = 1800


def _es_reciente(date):
    try:
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - date) <= timedelta(minutes=NUEVO_MINUTOS)
    except Exception:
        return False


async def _enviar_bienvenida(chat_id, user):
    nombre = _html.escape(user.first_name or "amigo")
    mencion = f'<a href="tg://user?id={user.id}">{nombre}</a>'
    texto = (
        f"Hola {mencion}, bienvenido al grupo, "
        f'si quieres una cuenta gratis le puedes escribir a '
        f'<a href="https://t.me/Akiubame">@Akiubame</a> 👋'
    )
    try:
        await client.send_message(chat_id, texto, parse_mode="html")
        log.info("📨 Bienvenida ENVIADA a user_id=%s", user.id)
    except FloodWaitError as fw:
        await asyncio.sleep(fw.seconds + 1)
        try:
            await client.send_message(chat_id, texto, parse_mode="html")
        except Exception as e2:
            log.warning("❌ FALLO tras flood: %r", e2)
    except Exception as e:
        log.warning("❌ FALLO al enviar bienvenida: %r", e)


@client.on(events.NewMessage(chats=WELCOME_CHAT_ID))
async def bienvenida_por_mensaje(event):
    if event.out:
        return
    sender = event.sender
    if sender is None or getattr(sender, "bot", False):
        return
    uid = event.sender_id
    if uid in _SALUDADOS:
        return
    t = _NO_NUEVOS.get(uid)
    if t and (time.time() - t) < _TTL_NO_NUEVO:
        return
    es_nuevo = None
    try:
        p = await client.get_participant(event.chat_id, uid)
        part = getattr(p, "participant", p)
        date = getattr(part, "date", None)
        es_nuevo = _es_reciente(date) if date is not None else None
        log.info("🔎 get_participant | uid=%s | es_nuevo=%s", uid, es_nuevo)
    except FloodWaitError as fw:
        await asyncio.sleep(min(fw.seconds, 30)); return
    except (ChatAdminRequiredError, UserNotParticipantError) as e:
        log.info("🔒 get_participant sin permiso (%r) -> MODO=%s", e, MODO); es_nuevo = None
    except Exception as e:
        log.warning("⚠️ get_participant falló: %r", e); es_nuevo = None
    if es_nuevo is True:
        _SALUDADOS.add(uid); await _enviar_bienvenida(event.chat_id, sender)
    elif es_nuevo is False:
        _NO_NUEVOS[uid] = time.time()
    elif MODO == "loose":
        _SALUDADOS.add(uid); await _enviar_bienvenida(event.chat_id, sender)
    else:
        _NO_NUEVOS[uid] = time.time()
# ===========================================================================


# ============== 📢 CARTEL ROTATIVO CADA X MIN (sin ser admin) ==============
CARTEL_CHAT_ID = WELCOME_CHAT_ID      # mismo grupo
INTERVALO_MIN = 15                    # cada cuántos minutos renueva el cartel

# Editá libremente los CUERPOS (no uses < > & sueltos; son HTML).
# El llamado a @Akiubame va como link clicable, inyectado abajo.
CARTEL_CUERPOS = [
    "👋 ¡Bienvenidos al grupo! Si necesitas ayuda:",
    "🎉 ¿Nuevo por aquí? Bienvenido/a, para obtener una cuenta:",
    "📢 ¿Buscas una cuenta gratis?",
]
CARTEL_CTA = 'Escríbele a <a href="https://t.me/Akiubame">@Akiubame</a> 👈'

_cartel_idx = 0
_ultimo_cartel_id = None              # id del cartel vigente (para borrarlo)


async def bucle_cartel():
    """Manda un cartel y, al siguiente ciclo, borra el anterior."""
    global _cartel_idx, _ultimo_cartel_id
    await asyncio.sleep(8)            # espera a que el cliente termine de arrancar
    while True:
        cuerpo = CARTEL_CUERPOS[_cartel_idx % len(CARTEL_CUERPOS)]
        _cartel_idx += 1
        texto = f"{_html.escape(cuerpo)}\n{CARTEL_CTA}"
        try:
            msg = await client.send_message(CARTEL_CHAT_ID, texto, parse_mode="html")
            nuevo_id = msg.id
            log.info("📢 Cartel ENVIADO id=%s", nuevo_id)
            if _ultimo_cartel_id is not None:
                try:
                    await client.delete_messages(CARTEL_CHAT_ID, [_ultimo_cartel_id])
                    log.info("🗑️ Cartel anterior borrado id=%s", _ultimo_cartel_id)
                except Exception as e:
                    log.warning("⚠️ No pude borrar cartel anterior: %r", e)
            _ultimo_cartel_id = nuevo_id
        except FloodWaitError as fw:
            log.warning("⏳ FloodWait %ss en cartel; espero", fw.seconds)
            await asyncio.sleep(fw.seconds + 5)
            continue                  # reintenta sin esperar el intervalo
        except Exception as e:
            log.warning("❌ FALLO cartel: %r", e)
        await asyncio.sleep(INTERVALO_MIN * 60)
# ===========================================================================


# ============== 🩺 /probe (termómetro, opcional) ===========================
@client.on(events.NewMessage(pattern=r"(?i)^/probe$", outgoing=True))
async def probe(event):
    log.info("🧪 /probe | chat_id=%s", event.chat_id)
    try:
        await event.reply(f"✅ probe ok — chat_id={event.chat_id}")
    except Exception as e:
        log.warning("🧪 /probe FALLO: %r", e)
# ===========================================================================


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

    # Lanza el cartel rotativo en paralelo (mismo loop que Telethon)
    asyncio.create_task(bucle_cartel())

    await client.run_until_disconnected()


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Apagando...")
