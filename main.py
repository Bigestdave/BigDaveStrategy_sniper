import pandas as pd
import numpy as np
import yfinance as yf
import requests
import time
from datetime import datetime

# ============================================================
# 🔑 CREDENTIALS & CONFIG
# ============================================================
TOKEN = "8400929450:AAGt6tfY3cBT18pSTOkBLGViTL4aQpZWm5c"
CHAT_ID = "5408858173"
SYMBOL = "GC=F" # Gold Futures

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram Error: {e}")
        return False

def get_signals():
    # Fetch 15 days to ensure SMA 800 is fully calculated
    df_15m = yf.download(SYMBOL, period="15d", interval="15m", progress=False)
    
    if isinstance(df_15m.columns, pd.MultiIndex):
        df_15m.columns = df_15m.columns.get_level_values(0)

    # 1. Regime (800 SMA on 15m)
    df_15m['sma'] = df_15m['Close'].rolling(800).mean()

    # 2. ADX 25 (Trend Strength)
    h, l, c = df_15m['High'], df_15m['Low'], df_15m['Close']
    plus_dm = h.diff().clip(lower=0)
    minus_dm = abs(l.diff().clip(upper=0))
    tr = pd.concat([h-l, abs(h-c.shift(1)), abs(l-c.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    p_di = 100 * (plus_dm.rolling(14).mean() / atr)
    m_di = 100 * (minus_dm.rolling(14).mean() / atr)
    df_15m['adx'] = ((abs(p_di - m_di) / (p_di + m_di + 0.1)) * 100).rolling(14).mean()

    # 3. Daily Context
    df_d = df_15m.resample('D').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    df_d['range'] = df_d['High'] - df_d['Low']
    df_d['vol_exp'] = df_d['range'] > df_d['range'].rolling(5).mean().shift(1)
    df_d['bias_bull'] = df_d['Close'] > df_d['High'].shift(1)
    ctx = {d.date(): {'vol': row['vol_exp'], 'bias': row['bias_bull']} for d, row in df_d.iterrows()}
    
    # 4. Strategy Geometry
    df_15m['bear_fvg'] = df_15m['Low'].shift(2) > df_15m['High']
    df_15m['swing_high'] = (df_15m['High'].shift(1) > df_15m['High'].shift(2)) & (df_15m['High'].shift(1) > df_15m['High'])
    
    return df_15m, ctx

def monitor():
    print(f"🛰️ Sniper Scanner Live... Waiting for Elite Traps on {SYMBOL}")
    send_telegram_msg("✅ *BigDave Sniper Scanner Online* \nMonitoring Gold (GC=F) for Elite 13.7 RF Setups.")
    
    last_alert_bar = None
    
    while True:
        try:
            df, ctx = get_signals()
            last_bar = df.iloc[-1]
            current_time = df.index[-1]
            
            # --- THE ELITE FILTERS ---
            # 1. Intraday: Price > SMA800 and ADX > 25
            if last_bar['Close'] > last_bar['sma'] and last_bar['adx'] > 25:
                
                # 2. Daily: Quiet Day + Bullish Bias
                today_ctx = ctx.get(current_time.date())
                if today_ctx and today_ctx['bias'] and not today_ctx['vol']:
                    
                    # 3. Setup: Bearish FVG in last 3 candles
                    fvg_zone = df.iloc[-4:-1]
                    if fvg_zone['bear_fvg'].any():
                        
                        # 4. Trigger: Price breaks recent Swing High
                        swing_high = df['High'].iloc[-12:-1].max()
                        
                        if last_bar['Close'] > swing_high:
                            if last_alert_bar != current_time:
                                # Entry Details
                                sl = df['Low'].iloc[-2] # Low of FVG candle
                                risk = last_bar['Close'] - sl
                                if risk <= 0: continue
                                
                                tp = last_bar['Close'] + (risk * 4.0)
                                # OFP $50k Account Math ($100 Risk)
                                # Gold: 1.0 lot = $100 profit per $1 move
                                lots = round(100.0 / (risk * 100), 2)
                                
                                msg = (f"🚨 *ELITE GOLD TRAP DETECTED!*\n\n"
                                       f"*Action:* BUY MARKET (Gold)\n"
                                       f"*Entry:* {last_bar['Close']:.2f}\n"
                                       f"*Stop Loss:* {sl:.2f}\n"
                                       f"*Take Profit:* {tp:.2f}\n"
                                       f"*Risk:* $100.00\n"
                                       f"*Position Size:* {lots} Lots\n\n"
                                       f"🛡️ *Rule:* If price hits {last_bar['Close'] + (risk*1.5):.2f}, move SL to {last_bar['Close'] - (risk*0.75):.2f}")
                                
                                if send_telegram_msg(msg):
                                    last_alert_bar = current_time
                                    print(f"🔔 Alert Sent: {current_time}")
                                
        except Exception as e:
            print(f"Error: {e}")
            
        time.sleep(60) # Scan every minute

if __name__ == "__main__":
    monitor()
