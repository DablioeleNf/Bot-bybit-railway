import requests
import time

# Telegram
TELEGRAM_TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
TELEGRAM_CHAT_ID = "719387436"

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
    try:
        r = requests.post(url, data=data)
        if r.status_code != 200:
            print(f"Erro ao enviar Telegram: {r.text}")
    except Exception as e:
        print(f"Erro no envio: {str(e)}")

if __name__ == "__main__":
    enviar_telegram("✈️ Bot com Bybit iniciado com sucesso!")
    while True:
        print("Bot está rodando...")
        time.sleep(600)
