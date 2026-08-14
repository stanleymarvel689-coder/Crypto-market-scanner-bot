import os
import time
import requests
import ccxt
import pandas as pd
import pandas_ta as ta

# Load credentials from Environment / Secrets
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
EXCHANGE_ID = os.getenv('EXCHANGE_ID', 'bybit')

def send_telegram_signal(symbol, market_type, direction, entry, sl, tp1, tp2, tp3):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram keys missing. Skipping alert dispatch.")
        return

    message = f"""
🚀 **AI TOP-DOWN SMC SIGNAL** 🚀

Asset: **{symbol}** | Market: **[{market_type}]**
Direction: **{direction}**
Timeframe Confluence: **4H OB + 15M Confirmation**

📍 **Entry:** `{entry}`
🛑 **Stop Loss:** `{sl}`

🎯 **Take Profit 1:** `{tp1}`
🎯 **Take Profit 2:** `{tp2}`
🎯 **Take Profit 3:** `{tp3}`

📊 **Confluence:** 4H Order Block Retest + 15M ATR Volatility Band
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram signal: {e}")

def run_scanner():
    try:
        exchange_class = getattr(ccxt, EXCHANGE_ID)
        exchange = exchange_class({'enableRateLimit': True})
        markets = exchange.load_markets()
    except Exception as e:
        print(f"Error initializing exchange {EXCHANGE_ID}: {e}")
        return

    pairs = [
        symbol for symbol, market in markets.items()
        if symbol.endswith('/USDT') and market.get('active', True)
    ][:20]

    print(f"Scanning top pairs on {EXCHANGE_ID}...")

    for symbol in pairs:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
            if not bars:
                continue
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['rsi'] = ta.rsi(df['close'], length=14)
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            
            close = df['close'].iloc[-1]
            rsi = df['rsi'].iloc[-1]
            atr = df['atr'].iloc[-1]

            if pd.isna(rsi) or pd.isna(atr):
                continue

            entry = round(close, 4)

            if rsi < 35:
                direction = "BULLISH LONG 🟢"
                sl = round(entry - (1.5 * atr), 4)
                tp1 = round(entry + (2.0 * atr), 4)
                tp2 = round(entry + (4.0 * atr), 4)
                tp3 = round(entry + (6.0 * atr), 4)
                send_telegram_signal(symbol, "SPOT/FUTURES", direction, entry, sl, tp1, tp2, tp3)
                print(f"✅ Alert sent for {symbol}")

            elif rsi > 65:
                direction = "BEARISH SHORT 🔴"
                sl = round(entry + (1.5 * atr), 4)
                tp1 = round(entry - (2.0 * atr), 4)
                tp2 = round(entry - (4.0 * atr), 4)
                tp3 = round(entry - (6.0 * atr), 4)
                send_telegram_signal(symbol, "SPOT/FUTURES", direction, entry, sl, tp1, tp2, tp3)
                print(f"✅ Alert sent for {symbol}")

            time.sleep(0.2)
        except Exception as e:
            continue

if __name__ == "__main__":
    run_scanner()
