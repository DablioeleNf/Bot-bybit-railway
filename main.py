import pandas as pd
import requests
import time
import ta
import numpy as np
from datetime import datetime

TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
CHAT_ID = "719387436"
CSV_FILE = "sinais_registrados.csv"

def enviar_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

def buscar_pares_usdt():
    try:
        url = "https://api.binance.com/api/v3/exchangeInfo"
        r = requests.get(url, timeout=10).json()
        return [s["symbol"] for s in r["symbols"] if s["symbol"].endswith("USDT") and s["status"] == "TRADING"]
    except:
        return []

def obter_dados(par, intervalo="1h", limite=200):
    url = f"https://api.binance.com/api/v3/klines?symbol={par}&interval={intervalo}&limit={limite}"
    r = requests.get(url).json()
    if isinstance(r, list):
        df = pd.DataFrame(r, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["close"] = df["close"].astype(float)
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df
    return None

def detectar_formacoes(df):
    ult = df.iloc[-1]
    corpo = abs(float(ult["open"]) - float(ult["close"]))
    sombra_inf = float(ult["low"]) - min(float(ult["open"]), float(ult["close"]))
    if corpo < sombra_inf and sombra_inf > corpo * 2:
        return True
    return False

def calcular_score(df1h, df5m):
    score = 0
    sinais = []

    rsi = ta.momentum.RSIIndicator(df1h["close"]).rsi().iloc[-1]
    if rsi < 30:
        score += 1
        sinais.append("RSI sobrevendido")
    elif rsi > 70:
        score += 1
        sinais.append("RSI sobrecomprado")

    ema = ta.trend.EMAIndicator(df1h["close"], window=21).ema_indicator().iloc[-1]
    if df1h["close"].iloc[-1] > ema:
        score += 1
        sinais.append("EMA tendência de alta")
    else:
        sinais.append("EMA tendência de baixa")

    bb = ta.volatility.BollingerBands(df1h["close"])
    if df1h["close"].iloc[-1] < bb.bollinger_lband().iloc[-1]:
        score += 1
        sinais.append("Bollinger abaixo da banda inferior")
    elif df1h["close"].iloc[-1] > bb.bollinger_hband().iloc[-1]:
        score += 1
        sinais.append("Bollinger acima da banda superior")

    suporte = min(df1h["close"].tail(20))
    resistencia = max(df1h["close"].tail(20))
    preco = df1h["close"].iloc[-1]
    if abs(preco - suporte)/preco < 0.01:
        score += 1
        sinais.append("Suporte próximo")
    elif abs(preco - resistencia)/preco < 0.01:
        score += 1
        sinais.append("Resistência próxima")

    if detectar_formacoes(df5m):
        score += 1
        sinais.append("Formação gráfica de reversão")

    vol_atual = df1h["volume"].iloc[-1]
    vol_medio = df1h["volume"].rolling(20).mean().iloc[-1]
    if vol_atual > vol_medio * 1.5:
        score += 1
        sinais.append("Volume elevado (potencial explosão)")

    return score, sinais

def registrar_sinal(par, score, sinais, confiavel):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{'|'.join(sinais)},{'Sim' if confiavel else 'Não'}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

def analisar():
    pares = buscar_pares_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares na Binance.")
        return

    melhor_par = None
    melhor_score = 0
    melhor_sinais = []

    for par in pares:
        df1h = obter_dados(par, "1h", 200)
        df5m = obter_dados(par, "5m", 200)
        if df1h is None or df5m is None:
            continue

        score, sinais = calcular_score(df1h, df5m)
        registrar_sinal(par, score, sinais, confiavel=score >= 4)

        if score > melhor_score:
            melhor_score = score
            melhor_par = par
            melhor_sinais = sinais

    if melhor_score >= 4:
        preco = df1h["close"].iloc[-1]
        entrada = preco
        tp1 = round(entrada * 1.01, 4)
        tp2 = round(entrada * 1.02, 4)
        tp3 = round(entrada * 1.03, 4)
        alvo = round(entrada * 1.04, 4)
        sl = round(entrada * 0.985, 4)
        hora = datetime.now().strftime("%H:%M:%S")

        msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
📊 Par: {melhor_par}
📈 Score: {melhor_score}/6
💵 Entrada: {entrada}
🎯 TP1: {tp1}
🎯 TP2: {tp2}
🎯 TP3: {tp3}
🏁 Alvo final: {alvo}
❌ Stop Loss: {sl}
🧠 Critérios:"""

        for s in melhor_sinais:
            msg += f"\n• {s}"

        enviar_telegram(msg)
    else:
        enviar_telegram("⚠️ Nenhum sinal forte encontrado nesta análise.")

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot com Binance iniciado com sucesso!")
while True:
    analisar()
    time.sleep(1800)  # 30 minutos
