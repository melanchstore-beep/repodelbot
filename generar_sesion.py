"""
Uso local:
    pip install telethon
    python generar_sesion.py
Te pedirá API_ID, API_HASH y teléfono. Te dará el string para la env var.
"""
from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def main():
    api_id = int(input("API_ID: ").strip())
    api_hash = input("API_HASH: ").strip()
    phone = input("Teléfono con código de país (ej. +5491112345678): ").strip()

    # StringSession() vacía -> fuerza login interactivo en consola
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        client.start(phone=phone)  # pide código (y 2FA si tenés) por consola

        session_string = client.session.save()

        print("\n" + "=" * 64)
        print("✅ Listo. Copiá TODO el string de abajo y pegalo en la")
        print("   variable de entorno SESSION_STRING de Render:")
        print("=" * 64)
        print(session_string)
        print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
