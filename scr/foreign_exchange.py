import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine
import time

DB_USER = "4RyYfQMvnH9DmYu.root"
DB_PASSWORD = "XD2WuF9AcDymVeCt"
DB_HOST = "gateway01.ap-northeast-1.prod.aws.tidbcloud.com"
DB_PORT = "4000"
DB_NAME = "macro_monitor_1"

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?ssl_verify_cert=true&ssl_verify_identity=true"
engine = create_engine(DATABASE_URL, connect_args={"ssl": {"fake_flag_to_enable_tls": True}})

def sync_exchange_rates():
    print("--- 開始同步匯率資料 ---")
    df = yf.download("TWD=X", start="2015-01-01", end="2026-12-31")
    
    if df.empty:
        print("未抓取到資料")
        return

    df = df[['Close']].reset_index()
    df.columns = ['date', 'close_price']
    df['ticker'] = "TWD=X"
    
    # 寫入資料庫 (if_exists='append' 表示附加，搭配 UNIQUE 索引可防止重複)
    # 註：這裡使用 to_sql 是最快的方式
    try:
        df.to_sql('exchange_rates', con=engine, if_exists='append', index=False)
        print(f" {len(df)} 筆匯率資料")
    except Exception as e:
        print(f"部分資料已存在或寫入失敗: {e}")

if __name__ == "__main__":
    sync_exchange_rates()
