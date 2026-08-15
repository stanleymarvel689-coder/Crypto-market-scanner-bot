import os
import time
import requests
import ccxt
import pandas as pd
import numpy as np

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
EXCHANGE_ID = os.getenv('EXCHANGE_ID', 'okx')

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def send_telegram_signal(symbol, market_type, direction, entry, sl, tp1, tp2, tp3):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram secrets missing!")
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
        print(f"Telegram dispatch failed for {symbol}: {e}")

def run_scanner():
    try:
        exchange_class = getattr(ccxt, EXCHANGE_ID)
        exchange = exchange_class({'enableRateLimit': True})
        
        print("Loading market pairs...")
        markets = exchange.load_markets()
        
        print("Fetching 24h market tickers...")
        tickers = exchange.fetch_tickers()
    except Exception as e:
        print(f"Exchange connection error: {e}")
        return

    # Filter for active USDT spot pairs
    usdt_pairs = []
    for symbol, ticker in tickers.items():
        if symbol in markets and symbol.endswith('/USDT'):
            market = markets[symbol]
            if market.get('active', True) and market.get('spot', True):
                vol = ticker.get('quoteVolume') or ticker.get('baseVolume') or 0
                usdt_pairs.append({'symbol': symbol, 'volume': vol})

    # Sort descending by 24h volume and select top 100
    usdt_pairs.sort(key=lambda x: x['volume'], reverse=True)
    top_100_pairs = [p['symbol'] for p in usdt_pairs[:100]]

    print(f"Successfully loaded Top {len(top_100_pairs)} volume pairs on {EXCHANGE_ID.upper()}. Starting scanner...")

    for symbol in top_100_pairs:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
            if not bars or len(bars) < 20:
                continue

            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['rsi'] = calculate_rsi(df['close'], period=14)
            df['atr'] = calculate_atr(df, period=14)

            close = float(df['close'].iloc[-1])
            rsi = float(df['rsi'].iloc[-1])
            atr = float(df['atr'].iloc[-1])

            if pd.isna(rsi) or pd.isna(atr) or atr == 0:
                continue

            entry = round(close, 4)

            # Signal conditions (< 40 Bullish Long, > 60 Bearish Short)
            if rsi < 40:
                direction = "BULLISH LONG 🟢"
                sl = round(entry - (1.5 * atr), 4)
                tp1 = round(entry + (2.0 * atr), 4)
                tp2 = round(entry + (4.0 * atr), 4)
                tp3 = round(entry + (6.0 * atr), 4)
                send_telegram_signal(symbol, "SPOT/FUTURES", direction, entry, sl, tp1, tp2, tp3)
                print(f"✅ Alert sent for {symbol} (RSI: {round(rsi, 2)})")

            elif rsi > 60:
                direction = "BEARISH SHORT 🔴"
                sl = round(entry + (1.5 * atr), 4)
                tp1 = round(entry - (2.0 * atr), 4)
                tp2 = round(entry - (4.0 * atr), 4)
                tp3 = round(entry - (6.0 * atr), 4)
                send_telegram_signal(symbol, "SPOT/FUTURES", direction, entry, sl, tp1, tp2, tp3)
                print(f"✅ Alert sent for {symbol} (RSI: {round(rsi, 2)})")

            time.sleep(0.1)  # Prevent rate limit throttling
        except Exception as e:
            print(f"Skipping {symbol}: {e}")
            continue

    print("Scan complete!")

if __name__ == "__main__":
    run_scanner()
        
