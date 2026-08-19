"""
Registra la URL del webhook de Telegram — correr una sola vez (o de nuevo si cambia la URL de
Railway o el secret). Lee TELEGRAM_BOT_TOKEN y TELEGRAM_WEBHOOK_SECRET de las variables de
entorno del proceso (no de api/.env — este script corre desde la terminal de quien configura el
bot, no desde el servidor).

Uso:
    TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=... python scripts/telegram_set_webhook.py https://criza-production.up.railway.app
"""

import os
import sys

import requests

if len(sys.argv) != 2:
    print("Uso: python scripts/telegram_set_webhook.py <url base de la API>")
    sys.exit(1)

base_url = sys.argv[1].rstrip("/")
token = os.environ["TELEGRAM_BOT_TOKEN"]
secret = os.environ["TELEGRAM_WEBHOOK_SECRET"]

resp = requests.post(
    f"https://api.telegram.org/bot{token}/setWebhook",
    json={"url": f"{base_url}/telegram/webhook", "secret_token": secret},
    timeout=15,
)
print(resp.status_code, resp.json())
