import yfinance as yf
import pandas as pd
import numpy as np
import time
import os 
from sqlalchemy import create_engine, text

USERNAME = "4RyYfQMvnH9DmYu.root"
PASSWORD = "XD2WuF9AcDymVeCt"
HOST = "gateway01.ap-northeast-1.prod.aws.tidbcloud.com"
PORT = "4000"
DATABASE = "macro_monitor_1"
###
ssl_args = {"ssl_ca": "/etc/ssl/cert.pem"}
if not os.path.exists("/etc/ssl/cert.pem"):
    ssl_args = {}
###
DATABASE_URL = f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}?ssl_ca=/etc/ssl/cert.pem"
engine = create_engine(
    DATABASE_URL,
    connect_args={"ssl": {"fake_flag_to_enable_tls": True}}
)

def init_db():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS economic_score (
                id INT AUTO_INCREMENT PRIMARY KEY,
                symbol VARCHAR(20),
                score_date DATE,
                open FLOAT,
                high FLOAT,
                low FLOAT,
                close FLOAT,
                adj_close FLOAT,
                volume BIGINT,
                cpi_score FLOAT,
                ppi_score FLOAT,
                fx_score FLOAT,
                total_score FLOAT,
                signal_light VARCHAR(20),
                UNIQUE KEY `idx_symbol_date` (`symbol`, `score_date`)
            )
        """))
        conn.commit()
        print("✅ 資料庫結構檢查完成")

def fetch_and_sync_stock(symbol):
    print(f"--- 正在同步：{symbol} ---")
    try:
        df = yf.download(
            symbol,
            start="2005-01-01",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df.empty:
            print(f"[{symbol}] 抓取不到數據")
            return

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        import_data = df.copy()
        import_data.index = import_data.index.tz_localize(None)
        
        close_price = import_data['Adj Close']
        ma200 = close_price.rolling(window=200).mean()
        
        import_data['symbol'] = symbol
        import_data['score_date'] = import_data.index.strftime('%Y-%m-%d')
###        
        close_price = import_data['Adj Close']
        ma200 = close_price.rolling(window=200).mean()
        # 20日變動率 (百分比)
        roc20 = close_price.pct_change(periods=20) * 100
        # 計算波動率 (20日標準差)，反映市場不安定感
        volatility = roc20.rolling(window=20).std()

        # --- 1. CPI 分數邏輯 (穩定性優先) ---
        # 基礎分 80，當波動率增加時扣分，最高 95，最低 60
        import_data['cpi_score'] = (80 - volatility * 2).clip(60, 95)

        # --- 2. PPI 分數邏輯 (與大盤趨勢掛鉤) ---
        # 若股價在均線之上，基數較高；反之較低
        ppi_base = np.where(close_price > ma200, 85, 70)
        import_data['ppi_score'] = (ppi_base - roc20.abs()).clip(60, 95)

        # --- 3. FX 分數邏輯 (匯率乖離率) ---
        # 如果 symbol 是匯率 TWD=X，計算偏離年線的程度
        # 假設美元太強 (偏離 MA200 > 5%) 對經濟體系是壓力，扣分
        bias_200 = ((close_price - ma200) / ma200) * 100
        import_data['fx_score'] = (85 - bias_200.abs() * 3).fillna(75.0).clip(60, 95)

        # --- 4. Total Score 綜合評分 ---
        # 給予不同權重：例如 CPI(40%) + PPI(30%) + FX(30%)
        import_data['total_score'] = (
            import_data['cpi_score'] * 0.4 + 
            import_data['ppi_score'] * 0.3 + 
            import_data['fx_score'] * 0.3
        )
        
        rename_map = {
            'Open': 'open', 'High': 'high', 'Low': 'low', 
            'Close': 'close', 'Adj Close': 'adj_close', 'Volume': 'volume'
        }
        import_data.rename(columns=rename_map, inplace=True)
###
        import_data = import_data.replace({np.nan: None})
        final_cols = ['symbol', 'score_date', 'open', 'high', 'low', 'close', 'adj_close', 
            'volume', 'cpi_score', 'ppi_score', 'fx_score', 'total_score', 'signal_light']
###        
        data_to_save = import_data[final_cols].to_dict(orient='records')

        with engine.connect() as conn:
            query = text("""
                INSERT INTO economic_score (
                    symbol, score_date, open, high, low, close, adj_close, volume, cpi_score, ppi_score, fx_score, total_score, signal_light
                )
                VALUES (
                    :symbol, :score_date, :open, :high, :low, :close, :adj_close, :volume, :cpi_score, :ppi_score, :fx_score, :total_score, :signal_light
                )
                ON DUPLICATE KEY UPDATE 
                    open = VALUES(open),
                    high = VALUES(high),
                    low = VALUES(low),
                    close = VALUES(close),
                    adj_close = VALUES(adj_close),
                    volume = VALUES(volume),
                    cpi_score = VALUES(cpi_score),
                    ppi_score = VALUES(ppi_score),
                    fx_score = VALUES(fx_score),
                    total_score = VALUES(total_score), 
                    signal_light = VALUES(signal_light)
            """)
            if len(data_to_save) > 0:
                print("🚨 檢查點 - 準備寫入資料庫的第一筆數據內容：")
                print(data_to_save[0])
            result = conn.execute(query, data_to_save)
            conn.commit()
            print(f"✅ {symbol} 同步完成，共寫入 {len(data_to_save)} 筆資料")

    except Exception as e:
        print(f"❌ 同步 {symbol} 時發生錯誤：{e}")
        
def get_signal(score):
            if score >= 85: return 'green'  # 極佳
            elif score >= 75: return 'blue' # 穩定
            elif score >= 65: return 'yellow' # 警告
            else: return 'red' # 危險

        import_data['signal_light'] = import_data['total_score'].apply(get_signal)

if __name__ == "__main__":
    init_db()
    target_stocks = ["IWM", "^DJI"]
    for stock in target_stocks:
        fetch_and_sync_stock(stock)
        time.sleep(2)
