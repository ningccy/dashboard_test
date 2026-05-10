import time
import yfinance as yf
import pandas as pd
from curl_cffi import requests

session = requests.Session(impersonate="chrome")

def fetch_single_stock(stock_symbol, period="10y"):
    #【函式 1】專門負責抓取單一標的，適合 Streamlit 即時顯示
    try:
        ticker = yf.Ticker(stock_symbol, session=session)
        df = ticker.history(period=period)

        if df.empty:
            return None

        df = df.reset_index()
        df["symbol"] = stock_symbol
        df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.date
        df = df[["symbol", "Date", "Open", "High", "Low", "Close", "Volume"]]
        return df
    except Exception as e:
        print(f"Error fetching {stock_symbol}: {e}")
        return None

def batch_update_stocks(symbol_csv, output_prefix="us_stock_pricing_part"):
    #【函式 2】就是你原本的批次邏輯，適合放在背景跑更新
    symbol_df = pd.read_csv(symbol_csv)
    symbols = symbol_df["stock_symbol"].unique().tolist()
    
    data_list = []
    file_index = 1
    
    for i, stock_symbol in enumerate(symbols, start=1):
        df = fetch_single_stock(stock_symbol) # 呼叫上面的函式 1
        if df is not None:
            data_list.append(df)
            print(f"{i} {stock_symbol} OK")

    except Exception as e:
        print(f"{i} {stock_symbol} ERROR:{e}")

    if i % 1000 == 0:
        result_df = pd.concat(data_list,ignore_index=True)
        output_file = f"{output_prefix}_{file_index}.csv"
        result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"Saved {output_file}, rows={len(result_df)}")

        file_index += 1
        data_list = []

        print("time sleep 30 seconds")
        time.sleep(batch_1000_sleep_time)


    elif i % 100 == 0:
        print("time sleep 5 seconds")
        time.sleep(batch_100_sleep_time)



if data_list:
    result_df = pd.concat(data_list, ignore_index=True)
    output_file = f"{output_prefix}_{file_index}.csv"
    result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Saved final {output_file}, rows={len(result_df)}")
