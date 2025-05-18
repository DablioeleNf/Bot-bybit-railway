import pandas as pd
import requests
import time
import ta
import numpy as np
from datetime import datetime

# === Configurações ===
TOKEN = "SEU_TOKEN_DO_TELEGRAM"
CHAT_ID = "SEU_CHAT_ID"
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
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base_vol", "taker_buy_quote_vol", "ignore"
        ])
        df["close"] = df["close"].astype(float)
        return df
    except:
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
    direcao = None

    preco = df1h["close"].iloc[-1]

    # RSI
    rsi = ta.momentum.RSIIndicator(df1h["close"]).rsi().iloc[-1]
    if rsi < 30:
        score += 1
        sinais.append("RSI sobrevendido")
        direcao = "Compra"
    elif rsi > 70:
        score += 1
        sinais.append("RSI sobrecomprado")
        direcao = "Venda"

    # EMA
    ema = ta.trend.EMAIndicator(df1h["close"], window=21).ema_indicator().iloc[-1]
    if preco > ema:
        score += 1
        sinais.append("EMA tendência alta")
        direcao = "Compra" if not direcao else direcao
    else:
        sinais.append("EMA tendência baixa")
        direcao = "Venda" if not direcao else direcao

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df1h["close"])
    if preco < bb.bollinger_lband().iloc[-1]:
        score += 1
        sinais.append("Bollinger abaixo da banda inferior")
        direcao = "Compra"
    elif preco > bb.bollinger_hband().iloc[-1]:
        score += 1
        sinais.append("Bollinger acima da banda superior")
        direcao = "Venda"

    # Suporte e resistência
    suporte = min(df1h["close"].tail(20))
    resistencia = max(df1h["close"].tail(20))
    if abs(preco - suporte)/preco < 0.01:
        score += 1
        sinais.append("Suporte próximo")
        direcao = "Compra"
    elif abs(preco - resistencia)/preco < 0.01:
        score += 1
        sinais.append("Resistência próxima")
        direcao = "Venda"

    # Formações gráficas
    if detectar_formacoes(df5m):
        score += 1
        sinais.append("Formação gráfica detectada")
        direcao = "Compra" if not direcao else direcao

    return score, sinais, direcao or "Indefinida"

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
    melhor_direcao = ""
    melhor_preco = 0

    for par in pares:
        df1h = obter_dados(par, "1h", 200)
        df5m = obter_dados(par, "5m", 200)
        if df1h is None or df5m is None:
            continue

        score, sinais, direcao = calcular_score(df1h, df5m)
        preco = df1h["close"].iloc[-1]
        registrar_sinal(par, score, sinais, confiavel=score >= 4)

        if score > melhor_score:
            melhor_score = score
            melhor_par = par
            melhor_sinais = sinais
            melhor_direcao = direcao
            melhor_preco = preco

    if melhor_score >= 4:
        tp1 = round(melhor_preco * (1.01 if melhor_direcao == "Compra" else 0.99), 4)
        tp2 = round(melhor_preco * (1.02 if melhor_direcao == "Compra" else 0.98), 4)
        tp3 = round(melhor_preco * (1.03 if melhor_direcao == "Compra" else 0.97), 4)
        stop = round(melhor_preco * (0.99 if melhor_direcao == "Compra" else 1.01), 4)
        agora = datetime.now().strftime("%H:%M")

        msg = f"""✅ Sinal forte detectado!

📊 Par: {melhor_par}
📈 Score: {melhor_score}/5
📅 Hora: {agora}
📌 Tipo de sinal: {melhor_direcao}
💰 Entrada: {melhor_preco}
🎯 TP1: {tp1}
🎯 TP2: {tp2}
🎯 TP3: {tp3}
🛑 Stop: {stop}
🧠 Critérios:"""
        for s in melhor_sinais:
            msg += f"\n• {s}"
        enviar_telegram(msg)
    else:
        enviar_telegram("⚠️ Nenhum sinal forte encontrado nesta análise.")

# === EXECUÇÃO ===
enviar_telegram("🤖 Bot com Binance iniciado com sucesso!")
while True:
    analisar()
    time.sleep(1800)  # a cada 30 minutos
