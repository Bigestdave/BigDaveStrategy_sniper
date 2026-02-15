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

# Assets with natural Bullish Bias
SYMBOLS = {
    'GC=F': 'GOLD',
    'ES=F': 'S&P 500',
    'SI=F': 'SILVER'
}

CONFIG = {
    'rr': 4.0,
    'trailing_trigger': 1.5,
    'trailing_stop_level': -0.75,
    'min_adx': 25,
    'killzone_hours': [14, 15],
    'risk_per_trade': 100.0 # Fixed $100 risk for your OFP account
}

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_data_and_context(symbol):
    df_15m = yf.download(symbol, period="15d", interval="15m", progress=False)
    if df_15m.empty: return None, None
    if isinstance(df_15m.columns, pd.MultiIndex):
        df_15m.columns = df_15m.columns.get_level_values(0)

    # SMA 800 & ADX
    df_15m['sma'] = df_15m['Close'].rolling(800).mean()
    h, l, c = df_15m['High'].values, df_15m['Low'].values, df_15m['Close'].values
    up = np.zeros_like(h); down = np.zeros_like(l)
    up[1:] = h[1:] - h[:-1]; down[1:] = l[:-1] - l[1:]
    p_dm = np.where((up > down) & (up > 0), up, 0); m_dm = np.where((down > up) & (down > 0), down, 0)
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    tr = np.insert(tr, 0, h[0]-l[0])
    tr_s = pd.Series(tr).rolling(14).mean().values
    p_di = 100 * (pd.Series(p_dm).rolling(14).mean().values / (tr_s + 0.001))
    m_di = 100 * (pd.Series(m_dm).rolling(14).mean().values / (tr_s + 0.001))
    df_15m['adx'] = pd.Series((abs(p_di - m_di) / (p_di + m_di + 0.001)) * 100).rolling(14).mean().values

    # Daily Context
    df_d = df_15m.resample('D').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    rng = (df_d['High'] - df_d['Low']).values
    df_d['vol_exp'] = rng > pd.Series(rng).rolling(5).mean().shift(1).values
    df_d['bias_bull'] = df_d['Close'] > df_d['High'].shift(1)
    ctx = {d.date(): {'vol': row['vol_exp'], 'bias': row['bias_bull']} for d, row in df_d.iterrows()}
    
    # Structure
    df_15m['bear_fvg'] = df_15m['Low'].shift(2) > df_15m['High']
    df_15m['swing_high'] = (df_15m['High'].shift(1) > df_15m['High'].shift(2)) & (df_15m['High'].shift(1) > df_15m['High'])
    
    return df_15m, ctx

def monitor():
    print(f"🛰️ BigDave Multi-Asset Scanner Live...")
    send_telegram_msg("🚀 *BigDave Sniper Online*\nMonitoring: Gold, S&P 500, Silver\nMode: Elite Sniper (Buy Only)\n*Status:* Hunting Traps...")
    
    last_alerts = {s: None for s in SYMBOLS.keys()}
    last_heartbeat_day = -1 
    
    while True:
        try:
            if datetime.now().day != last_heartbeat_day:
                send_telegram_msg("❤️ *Daily Heartbeat:* System is healthy.")
                last_heartbeat_day = datetime.now().day

            for sym, name in SYMBOLS.items():
                df, ctx = get_data_and_context(sym)
                if df is None: continue
                
                last_bar = df.iloc[-1]
                t = df.index[-1]
                
                if t.hour in CONFIG['killzone_hours']: continue
                
                # PILLARS
                if last_bar['Close'] > last_bar['sma'] and last_bar['adx'] > 25:
                    today_ctx = ctx.get(t.date())
                    if today_ctx and today_ctx['bias'] and not today_ctx['vol']:
                        if df.iloc[-4:-1]['bear_fvg'].any():
                            swing_high = df['High'].iloc[-13:-1].max()
                            
                            if last_bar['Close'] > swing_high:
                                if last_alerts[sym] != t:
                                    sl = df['Low'].iloc[-2]
                                    risk = last_bar['Close'] - sl
                                    if risk <= 0: continue
                                    
                                    tp = last_bar['Close'] + (risk * 4.0)
                                    # Lot calculation based on Asset type
                                    # (This is an approximation, always verify in your app)
                                    lots = round(100.0 / (risk * 100), 2) if 'F' in sym else 1.0
                                    
                                    msg = (f"🚨 *ELITE {name} TRAP DETECTED!*\n\n"
                                           f"*Entry Around:* {last_bar['Close']:.2f}\n"
                                           f"*Stop Loss:* {sl:.2f}\n"
                                           f"*Take Profit:* {tp:.2f}\n"
                                           f"*Position:* {lots} Lots ($100 Risk)\n\n"
                                           f"🛡️ *Rule:* At {last_bar['Close'] + (risk*1.5):.2f}, move SL to {last_bar['Close'] - (risk*0.75):.2f}")
                                    
                                    send_telegram_msg(msg)
                                    last_alerts[sym] = t
                                    
        except Exception as e:
            print(f"Error: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    monitor()
