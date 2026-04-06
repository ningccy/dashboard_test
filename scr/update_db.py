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
#########################################################
ssl_args = {"ssl_ca": "/etc/ssl/cert.pem"}
if not os.path.exists("/etc/ssl/cert.pem"):
    ssl_args = {}
#########################################################
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
        # 邏輯：利用 20 日價格變動率來模擬經濟通膨/生產熱度
        roc20 = close_price.pct_change(periods=20) * 100
        
        # 模擬 CPI 分數：波動在合理範圍給高分，過度波動(通膨/通縮)分數降低
        import_data['cpi_score'] = 80 - (roc20.abs() * 2) 
        import_data['cpi_score'] = import_data['cpi_score'].clip(60, 95) # 限制區間

        # 模擬 PPI 分數：稍微跟隨 CPI 但權重不同
        import_data['ppi_score'] = 75 - (roc20.abs() * 1.5)
        import_data['ppi_score'] = import_data['ppi_score'].clip(60, 95)

        # 模擬 FX 分數：這裡設定為一個相對穩定的基準值
        import_data['fx_score'] = 70.0
###        
        import_data['total_score'] = np.where(close_price > ma200, 80.0, 60.0)
        import_data.loc[ma200.isna(), 'total_score'] = 70.0 
        
        import_data['signal_light'] = import_data['total_score'].apply(
            lambda x: 'green' if x >= 80 else 'yellow'
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
                    symbol, score_date, open, high, low, close, adj_close, volume, total_score, signal_light
                )
                VALUES (
                    :symbol, :score_date, :open, :high, :low, :close, :adj_close, :volume, :total_score, :signal_light
                )
                ON DUPLICATE KEY UPDATE 
                    open = VALUES(open),
                    high = VALUES(high),
                    low = VALUES(low),
                    close = VALUES(close),
                    adj_close = VALUES(adj_close),
                    volume = VALUES(volume),
                    total_score = VALUES(total_score), 
                    signal_light = VALUES(signal_light)
            """)
            result = conn.execute(query, data_to_save)
            conn.commit()
            print(f"✅ {symbol} 同步完成，共寫入 {len(data_to_save)} 筆資料")

    except Exception as e:
        print(f"❌ 同步 {symbol} 時發生錯誤：{e}")

if __name__ == "__main__":
    init_db()
    target_stocks = ["IWM", "^DJI"]
    for stock in target_stocks:
        fetch_and_sync_stock(stock)
        time.sleep(2)
