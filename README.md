# Telegram User-Bot (Render free + keep-alive)

User-bot de Telegram con Telethon, hosteado gratis en Render y mantenido
despierto con un ping externo (UptimeRobot / cron-job.org).

## 1. Conseguir credenciales
1. Entrá a https://my.telegram.org → API development tools.
2. Anotá `api_id` y `api_hash`.

## 2. Generar la sesión (una sola vez, en tu PC)
```bash
pip install telethon
python generar_sesion.py
```
Copiá el string que imprime.

## 3. Deploy en Render
- New → **Web Service** → conectá este repo.
- Runtime: **Docker**
- Plan: **Free**
- Port: `10000`
- Environment Variables:
  - `API_ID` = tu api id
  - `API_HASH` = tu api hash
  - `SESSION_STRING` = el string del paso 2

## 4. Keep-alive
Creá un monitor en https://uptimerobot.com (o cron-job.org) que haga
GET a `https://TU-SERVICIO.onrender.com/` cada **5 minutos**.

## Comandos del bot
- `/ping` → responde Pong
- `/info` → info del chat
- `/start` → estado
