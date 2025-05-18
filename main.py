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
    except Exception as e:
        print(f"Erro ao enviar mensagem Telegram: {e}")

def buscar_pares_usdt():
    try:
        url = "https://api.bybit.com/v5/market/instruments-info?category=spot"
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            print(f"Erro HTTP: {response.status_code}")
            return []
        data = response.json()
        if not data.get("result") or not data["result"].get("list"):
            print("Resposta inesperada da API da Bybit")
            return []
        usdt_pairs = [item["symbol"] for item in data["result"]["list"] if item["symbol"].endswith("USDT")]
        if not usdt_pairs:
            print("Nenhum par USDT encontrado.")
        return usdt_pairs
    except Exception as e:
        print(f"Erro ao buscar pares USDT: {e}")
        return []

def obter_dados(par, intervalo="1h", limite=200):
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={par}&interval={intervalo}&limit={limite}"
        r = requests.get(url).json()
        if "result" in r and "list" in r["result"]:
            df = pd.DataFrame(r["result"]["list"], columns=[
                "timestamp", "open", "high", "low", "close", "volume", "turnover"])
            df["close"] = df["close"].astype(float)
            return df
        return None
    except:
        return None

def detectar_formacoes(df):
    # Exemplo básico de formação gráfica de candle de reversão (martelo)
    ult = df.iloc[-1]
    corpo = abs(float(ult["open"]) - float(ult["close"]))
    sombra_inf = float(ult["low"]) - min(float(ult["open"]), float(ult["close"]))
    if corpo < sombra_inf and sombra_inf > corpo * 2:
        return True
    return False

def calcular_score(df1h, df5m):
    score = 0
    sinais = []

    # RSI
    rsi = ta.momentum.RSIIndicator(df1h["close"]).rsi().iloc[-1]
    if rsi < 30:
        score += 1
        sinais.append("RSI sobrevendido")
    elif rsi > 70:
        score += 1
        sinais.append("RSI sobrecomprado")

    # EMA
    ema = ta.trend.EMAIndicator(df1h["close"], window=21).ema_indicator().iloc[-1]
    if df1h["close"].iloc[-1] > ema:
        score += 1
        sinais.append("EMA tendência alta")
    else:
        sinais.append("EMA tendência baixa")

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df1h["close"])
    if df1h["close"].iloc[-1] < bb.bollinger_lband().iloc[-1]:
        score += 1
        sinais.append("Bollinger abaixo da banda inferior")
    elif df1h["close"].iloc[-1] > bb.bollinger_hband().iloc[-1]:
        score += 1
        sinais.append("Bollinger acima da banda superior")

    # Suporte e resistência
    suporte = min(df1h["close"].tail(20))
    resistencia = max(df1h["close"].tail(20))
    preco = df1h["close"].iloc[-1]
    if abs(preco - suporte)/preco < 0.01:
        score += 1
        sinais.append("Suporte próximo")
    elif abs(preco - resistencia)/preco < 0.01:
        score += 1
        sinais.append("Resistência próxima")

    # Formações gráficas
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
        enviar_telegram("❌ Erro ao buscar pares na Bybit.")
        return

    melhor_par = None
    melhor_score = 0
    melhor_sinais = []

    for par in pares:
        df1h = obter_dados(par, "60", 200)
        df5m = obter_dados(par, "5", 200)
        if df1h is None or df5m is None:
            continue

        score, sinais = calcular_score(df1h, df5m)
        registrar_sinal(par, score, sinais, confiavel=score >= 4)

        if score > melhor_score:
            melhor_score = score
            melhor_par = par
            melhor_sinais = sinais

    if melhor_score >= 4:
        msg = f"✅ Sinal forte detectado!\n\n📊 Par: {melhor_par}\n📈 Score: {melhor_score}/5\n🧠 Critérios:\n"
        for s in melhor_sinais:
            msg += f"• {s}\n"
        enviar_telegram(msg)
    else:
        enviar_telegram("⚠️ Nenhum sinal forte encontrado nesta análise.")

# === EXECUÇÃO INICIAL ===
enviar_telegram("🤖 Bot com Bybit iniciado com sucesso!")
while True:
    analisar()
    time.sleep(1800)  # Executa a cada 30 minutos
