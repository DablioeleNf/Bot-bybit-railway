import pandas as pd
import requests
import time
import ta
from datetime import datetime
import logging

# Configurações iniciais
TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
CHAT_ID = "719387436"
CSV_FILE = "sinais_registrados.csv"

# Configuração de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Função para enviar mensagens no Telegram
def enviar_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem no Telegram: {e}")

# Função para buscar os pares USDT
def buscar_pares_usdt():
    try:
        url = "https://api.binance.com/api/v3/exchangeInfo"
        r = requests.get(url, timeout=10)
        
        if r.status_code != 200:
            raise ValueError(f"Erro na resposta da API: {r.status_code}")
        
        data = r.json()
        
        if "symbols" not in data:
            raise KeyError("A chave 'symbols' não foi encontrada na resposta da API.")
        
        pares = [
            s["symbol"] for s in data["symbols"] 
            if s["symbol"].endswith("USDT") and s.get("status") == "TRADING"
        ]
        return pares
    except requests.exceptions.RequestException as e:
        enviar_telegram(f"❌ Erro ao conectar à API Binance: {e}")
        logging.error(f"Erro ao conectar à API Binance: {e}")
        return []
    except KeyError as e:
        enviar_telegram(f"❌ Erro ao processar pares: {e}")
        logging.error(f"Erro ao processar pares: {e}")
        return []
    except Exception as e:
        enviar_telegram(f"❌ Erro desconhecido ao buscar pares: {e}")
        logging.error(f"Erro desconhecido ao buscar pares: {e}")
        return []

# Função para obter os dados de mercado
def obter_dados(par, intervalo="1h", limite=200):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={par}&interval={intervalo}&limit={limite}"
        r = requests.get(url).json()
        if not isinstance(r, list):
            return None
        df = pd.DataFrame(r, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base_vol", "taker_buy_quote_vol", "ignore"
        ])
        df["close"] = df["close"].astype(float)
        df["open"] = df["open"].astype(float)
        df["low"] = df["low"].astype(float)
        df["high"] = df["high"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df
    except Exception as e:
        logging.error(f"Erro ao obter dados de {par}: {e}")
        return None

# Função para detectar formações de reversão
def detectar_formacoes(df):
    try:
        ult = df.iloc[-1]
        corpo = abs(ult["open"] - ult["close"])
        sombra_inf = ult["low"] - min(ult["open"], ult["close"])
        return corpo < sombra_inf and sombra_inf > corpo * 2
    except:
        return False

# Função para calcular score
def calcular_score(df1h, df5m):
    score = 0
    sinais = []
    votos = []

    preco = df1h["close"].iloc[-1]

    # RSI
    rsi = ta.momentum.RSIIndicator(df1h["close"]).rsi().iloc[-1]
    if rsi < 30:
        score += 1
        sinais.append("RSI sobrevendido")
        votos.append("compra")
    elif rsi > 70:
        score += 1
        sinais.append("RSI sobrecomprado")
        votos.append("venda")

    # EMA
    ema = ta.trend.EMAIndicator(df1h["close"], window=21).ema_indicator().iloc[-1]
    if preco > ema:
        score += 1
        sinais.append("EMA tendência de alta")
        votos.append("compra")
    else:
        sinais.append("EMA tendência de baixa")
        votos.append("venda")

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df1h["close"])
    if preco < bb.bollinger_lband().iloc[-1]:
        score += 1
        sinais.append("Bollinger abaixo da banda")
        votos.append("compra")
    elif preco > bb.bollinger_hband().iloc[-1]:
        score += 1
        sinais.append("Bollinger acima da banda")
        votos.append("venda")

    # Suporte e resistência
    suporte = min(df1h["close"].tail(20))
    resistencia = max(df1h["close"].tail(20))
    if abs(preco - suporte)/preco < 0.01:
        score += 1
        sinais.append("Suporte próximo")
        votos.append("compra")
    elif abs(preco - resistencia)/preco < 0.01:
        score += 1
        sinais.append("Resistência próxima")
        votos.append("venda")

    # Formação de reversão
    if detectar_formacoes(df5m):
        score += 1
        sinais.append("Formação de reversão")
        votos.append("compra")

    direcao = "compra" if votos.count("compra") > votos.count("venda") else "venda"

    return score, sinais, direcao, preco

# Função para registrar sinais no CSV
def registrar_sinal(par, score, sinais, direcao):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{direcao},{'|'.join(sinais)},Sim\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

# Função principal de análise
def analisar():
    pares = buscar_pares_usdt()
    if not pares:
        return

    melhor = None
    melhor_score = 0

    for par in pares:
        df1h = obter_dados(par, "1h")
        df5m = obter_dados(par, "5m")
        if df1h is None or df5m is None:
            continue

        score, sinais, direcao, preco = calcular_score(df1h, df5m)
        if score > melhor_score:
            melhor_score = score
            melhor = {
                "par": par,
                "score": score,
                "sinais": sinais,
                "direcao": direcao,
                "preco": preco
            }

    if melhor and melhor["score"] >= 4:
        entrada = melhor["preco"]
        tp1 = round(entrada * (1.01 if melhor["direcao"] == "compra" else 0.99), 4)
        tp2 = round(entrada * (1.02 if melhor["direcao"] == "compra" else 0.98), 4)
        tp3 = round(entrada * (1.03 if melhor["direcao"] == "compra" else 0.97), 4)
        sl = round(entrada * (0.985 if melhor["direcao"] == "compra" else 1.015), 4)
        agora = datetime.utcnow().strftime("%H:%M:%S")

        msg = f"""✅ Sinal forte detectado!
🕒 Hora: {agora} UTC
📊 Par: {melhor["par"]}
📈 Score: {melhor["score"]}/6
📌 Direção: {melhor["direcao"].capitalize()}
💵 Entrada: {entrada}
🎯 TP1: {tp1}
🎯 TP2: {tp2}
🎯 TP3: {tp3}
🛑 Stop Loss: {sl}
🧠 Critérios:"""

        for s in melhor["sinais"]:
            msg += f"\n• {s}"

        enviar_telegram(msg)
        registrar_sinal(melhor["par"], melhor["score"], melhor["sinais"], melhor["direcao"])
    else:
        enviar_telegram("⚠️ Nenhum sinal forte encontrado nesta análise.")

# Execução contínua a cada 20 minutos
enviar_telegram("🤖 Bot com Binance iniciado!")
while True:
    analisar()
    time.sleep(1200)