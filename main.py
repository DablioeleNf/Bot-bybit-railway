import requests
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import time

# Configurações do Telegram
TELEGRAM_TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
TELEGRAM_CHAT_ID = "719387436"

# Timeframe e parâmetros
INTERVAL = "5m"
LIMIT = 150
SLEEP_INTERVAL = 1200  # 20 minutos

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem}
        requests.post(url, data=data)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def buscar_pares_usdt():
    try:
        url = "https://api.binance.com/api/v3/exchangeInfo"
        r = requests.get(url, timeout=10).json()

        if "symbols" not in r:
            enviar_telegram(f"⚠️ Erro: resposta inesperada da Binance: {r}")
            return []

        usdt_pairs = [s["symbol"] for s in r["symbols"] if s["symbol"].endswith("USDT") and s["status"] == "TRADING"]
        return usdt_pairs

    except Exception as e:
        enviar_telegram(f"❌ Erro ao buscar pares: {str(e)}")
        return []

def buscar_candles(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={INTERVAL}&limit={LIMIT}"
    r = requests.get(url).json()
    if not r or "code" in r:
        return None
    df = pd.DataFrame(r, columns=[
        'time','open','high','low','close','volume','c_close','c_volume','x','q','y','z'
    ])
    df['close'] = pd.to_numeric(df['close'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    return df

def analisar_par(symbol):
    df = buscar_candles(symbol)
    if df is None or len(df) < 50:
        return None

    try:
        ema20 = EMAIndicator(df['close'], window=20).ema_indicator()
        ema50 = EMAIndicator(df['close'], window=50).ema_indicator()
        rsi = RSIIndicator(df['close'], window=14).rsi()
    except:
        return None

    close = df['close'].iloc[-1]
    sup = df['low'].rolling(20).min().iloc[-1]
    res = df['high'].rolling(20).max().iloc[-1]

    score = 0
    sinal = None
    entrada = None
    stop = None
    tps = []

    if ema20.iloc[-1] > ema50.iloc[-1] and rsi.iloc[-1] > 50 and close > ema20.iloc[-1]:
        score += 3
        sinal = "COMPRA"
        entrada = close
        stop = sup
        tps = [round(entrada * 1.005, 4), round(entrada * 1.01, 4), round(entrada * 1.02, 4)]

    elif ema20.iloc[-1] < ema50.iloc[-1] and rsi.iloc[-1] < 50 and close < ema20.iloc[-1]:
        score += 3
        sinal = "VENDA"
        entrada = close
        stop = res
        tps = [round(entrada * 0.995, 4), round(entrada * 0.99, 4), round(entrada * 0.98, 4)]

    if score >= 3:
        return {
            "symbol": symbol,
            "sinal": sinal,
            "entrada": round(entrada, 4),
            "tp": tps,
            "stop": round(stop, 4),
            "score": score
        }
    return None

def executar_bot():
    enviar_telegram("🤖 Bot iniciado com sucesso!")
    while True:
        try:
            pares = buscar_pares_usdt()
            melhores = []

            for symbol in pares:
                resultado = analisar_par(symbol)
                if resultado:
                    melhores.append(resultado)

            if melhores:
                melhor = max(melhores, key=lambda x: x["score"])
                msg = f"""
📊 SINAL FORTE DETECTADO
Ativo: {melhor['symbol']}
Tipo: {melhor['sinal']}
Entrada: {melhor['entrada']}
🎯 TP1: {melhor['tp'][0]}
🎯 TP2: {melhor['tp'][1]}
🎯 TP3: {melhor['tp'][2]}
🛑 Stop: {melhor['stop']}
⏰ {pd.Timestamp.now(tz='UTC').strftime('%H:%M %d/%m')} UTC
                """
                enviar_telegram(msg.strip())
            else:
                enviar_telegram("⛔ Nenhum sinal forte encontrado nesta análise.")

        except Exception as e:
            enviar_telegram(f"⚠️ Erro no bot: {str(e)}")

        time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    executar_bot()
