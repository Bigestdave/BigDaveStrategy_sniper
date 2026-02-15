import pandas as pd
import numpy as np
import yfinance as yf
import requests
import time
from datetime import datetime

# ============================================================
# 🔑 THE SNIPER MASTER CONFIG
# ============================================================
TOKEN = "8400929450:AAGt6tfY3cBT18pSTOkBLGViTL4aQpZWm5c"
CHAT_ID = "5408858173" 
SYMBOL = "GC=F" # Gold Futures

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_signals():
    # 1. FETCH DATA (15 days ensures indicators are ready)
    df_15m = yf.download(SYMBOL, period="15d", interval="15m", progress=False)
    if isinstance(df_15m.columns, pd.MultiIndex):
        df_15m.columns = df_15m.columns.get_level_values(0)

    # 2. CALCULATE INDICATORS (Identical logic to Audit)
    # SMA 800
    df_15m['sma'] = df_15m['Close'].rolling(800).mean()
    
    # ADX 14 (Vectorized for speed, identical math)
    h, l, c = df_15m['High'].values, df_15m['Low'].values, df_15m['Close'].values
    up = np.zeros_like(h); down = np.zeros_like(l)
    up[1:] = h[1:] - h[:-1]; down[1:] = l[:-1] - l[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    tr = np.insert(tr, 0, h[0]-l[0])
    tr_s = pd.Series(tr).rolling(14).mean().values
    p_di = 100 * (pd.Series(plus_dm).rolling(14).mean().values / (tr_s + 0.001))
    m_di = 100 * (pd.Series(minus_dm).rolling(14).mean().values / (tr_s + 0.001))
    dx = (abs(p_di - m_di) / (p_di + m_di + 0.001)) * 100
    df_15m['adx'] = pd.Series(dx).rolling(14).mean().values

    # 3. DAILY CONTEXT (Quiet Day + Bullish Bias)
    df_d = df_15m.resample('D').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    rng = (df_d['High'] - df_d['Low']).values
    df_d['vol_exp'] = rng > pd.Series(rng).rolling(5).mean().shift(1).values
    df_d['bias_bull'] = df_d['Close'] > df_d['High'].shift(1)
    ctx = {d.date(): {'vol': row['vol_exp'], 'bias': row['bias_bull']} for d, row in df_d.iterrows()}
    
    # 4. TRAP GEOMETRY
    df_15m['bear_fvg'] = df_15m['Low'].shift(2) > df_15m['High']
    df_15m['swing_high'] = (df_15m['High'].shift(1) > df_15m['High'].shift(2)) & (df_15m['High'].shift(1) > df_15m['High'])
    
    return df_15m, ctx

def monitor():
    print(f"🛰️ BigDave Sniper Scanner Online...")
    
    # --- STARTUP CHECK ---
    send_telegram_msg("🚀 *BigDave Sniper Online*\n\nLogic: Elite Trap (RF 13.7)\nAsset: Gold (GC=F)\nFilters: SMA + ADX + Bias + QuietDay\n\n*Status:* Monitoring 24/7...")
    
    last_alert_bar = None
    last_heartbeat_day = -1 
    
    while True:
        try:
            now = datetime.now()
            
            # --- DAILY HEARTBEAT ---
            if now.day != last_heartbeat_day:
                send_telegram_msg("❤️ *Heartbeat:* System is active and hunting.")
                last_heartbeat_day = now.day

            df, ctx = get_signals()
            last_bar = df.iloc[-1]
            current_time = df.index[-1]
            
            # THE PILLARS OF THE EDGE
            # 1. Regime & Momentum
            if last_bar['Close'] > last_bar['sma'] and last_bar['adx'] > 25:
                
                # 2. Daily Context
                today_ctx = ctx.get(current_time.date())
                if today_ctx and today_ctx['bias'] and not today_ctx['vol']:
                    
                    # 3. Structural Setup (FVG in last 3 bars)
                    if df.iloc[-4:-1]['bear_fvg'].any():
                        
                        # 4. Trigger (Break of 12-candle Swing High)
                        swing_high = df['High'].iloc[-13:-1].max()
                        
                        if last_bar['Close'] > swing_high:
                            if last_alert_bar != current_time:
                                # Trade Calculation
                                fvg_low = df['Low'].iloc[-2] # Low of the FVG candle
                                risk = last_bar['Close'] - fvg_low
                                
                                if risk > 0:
                                    tp = last_bar['Close'] + (risk * 4.0)
                                    lots = round(100.0 / (risk * 100), 2)
                                    
                                    msg = (f"🚨 *ELITE GOLD TRAP DETECTED!*\n\n"
                                           f"*Type:* BUY MARKET (Gold)\n"
                                           f"*Position:* {lots} Lots\n"
                                           f"*Entry Around:* {last_bar['Close']:.2f}\n"
                                           f"*Stop Loss:* {fvg_low:.2f}\n"
                                           f"*Take Profit:* {tp:.2f}\n\n"
                                           f"🛡️ *Rule:* At {last_bar['Close'] + (risk*1.5):.2f}, move SL to {last_bar['Close'] - (risk*0.75):.2f}")
                                    
                                    send_telegram_msg(msg)
                                    last_alert_bar = current_time
                                    print(f"🔔 ALERT SENT: {current_time}")
                                
        except Exception as e:
            print(f"Error: {e}")
            
        time.sleep(60) # Re-check every 60 seconds

if __name__ == "__main__":
    monitor()
