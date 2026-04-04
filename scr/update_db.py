import yfinance as yf
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

USERNAME = "4RyYfQMvnH9DmYu.root",
PASSWORD = "XD2WuF9AcDymVeCt",
HOST = "gateway01.ap-northeast-1.prod.aws.tidbcloud.com",
PORT = "4000",
DATABASE = "macro_monitor_1"

DATABASE_URL = f"mysql+pymysql://{4RyYfQMvnH9DmYu.root}:{XD2WuF9AcDymVeCt}@{gateway01.ap-northeast-1.prod.aws.tidbcloud.com}:{4000}/{macro_monitor_1}?ssl_ca=/etc/ssl/cert.pem"

def fetch_and_sync_stock(symbol):
    print(f"--- 正在同步：{symbol} ---")
    try:
        df = yf.download(
            symbol,
            start="2005-01-01",
            end="2026-03-01",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df.empty:
            print(f"[{symbol}] 抓取不到數據")
            return

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 資料清洗與格式轉換
        import_data = df.copy()
        import_data.index = import_data.index.tz_localize(None)
        
        # 強制轉為單一欄位，避免抓取到多餘資訊
        close_price = import_data['Adj Close']
        ma200 = close_price.rolling(window=200).mean()
        
        import_data['symbol'] = symbol
        # 轉為字串日期，確保 SQL 寫入穩定
        import_data['score_date'] = import_data.index.strftime('%Y-%m-%d')
        
        # 評分邏輯
        import_data['total_score'] = np.where(close_price > ma200, 80.0, 60.0)
        # 處理歷史初期不足 200 天的數據
        import_data.loc[ma200.isna(), 'total_score'] = 70.0 
        
        import_data['signal_light'] = import_data['total_score'].apply(
            lambda x: 'green' if x >= 80 else 'yellow'
        )

        rename_map = {
            'Open': 'open', 'High': 'high', 'Low': 'low', 
            'Close': 'close', 'Adj Close': 'adj_close', 'Volume': 'volume'
        }
        import_data.rename(columns=rename_map, inplace=True)

        # 處理空值與欄位篩選
        import_data = import_data.replace({np.nan: None})
        final_cols = ['symbol', 'score_date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'total_score', 'signal_light']
        
        # 排除 DataFrame 中不屬於上述的欄位（例如 yf 可能多出的 Ticker 欄位）
        data_to_save = import_data[final_cols].to_dict(orient='records')

        with engine.connect() as conn: # 改用 connect 配合 commit
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
            conn.execute(query, data_to_save)
            conn.commit()        
        print(f"同步完成！{symbol} 資料已正式寫入")

    except Exception as e:
        print(f"同步 {symbol} 時發生錯誤：{e}")

if __name__ == "__main__":
    target_stocks = ["IWM", "^DJI"]
    for stock in target_stocks:
        fetch_and_sync_stock(stock)
