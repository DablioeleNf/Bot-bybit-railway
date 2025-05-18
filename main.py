
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
        return [s["symbol"] for s in r["symbols"] if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"]
    except:
        return []

def obter_dados(par, intervalo="1h", limite=200):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={par}&interval={intervalo}&limit={limite}"
        r = requests.get(url).json()
        df = pd.DataFrame(r, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "_", "_", "_", "_", "_", "_"
        ])
        df["close"] = df["close"].astype(float)
        return df
    except:
        return None

def detectar_formacoes(df):
    ult = df.iloc[-1]
    corpo = abs(float(ult["open"]) - float(ult["close"]))
    sombra_inf = float(ult["low"]) - min(float(ult["open"]), float(ult["close"]))
    return corpo < sombra_inf and sombra_inf > corpo * 2

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
        sinais.append("EMA tendência alta")
    else:
        sinais.append("EMA tendência baixa")

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
        sinais.append("Formação gráfica detectada")

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
    preco_entrada = 0

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
            preco_entrada = df1h["close"].iloc[-1]

    if melhor_score >= 4:
        tp1 = round(preco_entrada * 1.01, 6)
        tp2 = round(preco_entrada * 1.015, 6)
        tp3 = round(preco_entrada * 1.02, 6)
        alvo = round(preco_entrada * 1.025, 6)
        sl = round(preco_entrada * 0.98, 6)
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"✅ Sinal forte detectado!

🕒 Hora: {agora}
📊 Par: {melhor_par}
📈 Score: {melhor_score}/5
📥 Entrada: {preco_entrada}
🎯 Alvo final: {alvo}
💰 TPs: {tp1}, {tp2}, {tp3}
🛑 Stop Loss: {sl}

🧠 Critérios:
"
        for s in melhor_sinais:
            msg += f"• {s}\n"
        enviar_telegram(msg)
    else:
        enviar_telegram("⚠️ Nenhum sinal forte encontrado nesta análise.")

enviar_telegram("🤖 Bot Binance iniciado com sucesso!")
while True:
    analisar()
    time.sleep(1800)
upgrade: entrada, TPs, SL, hora adicionados ao sinal
