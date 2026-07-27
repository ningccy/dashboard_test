import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine
import time
import streamlit as st

db_config = st.secrets["mysql"]
DATABASE_URL = (
    f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
    f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
    f"?ssl_verify_cert=true&ssl_verify_identity=true"
)

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
    
    try:
        df.to_sql('exchange_rates', con=engine, if_exists='append', index=False)
        print(f" {len(df)} 筆匯率資料")
    except Exception as e:
        print(f"部分資料已存在或寫入失敗: {e}")

if __name__ == "__main__":
    sync_exchange_rates()
