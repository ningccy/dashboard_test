import yfinance as yf
import time
import random

tickers = ["TWD=X"] # 美元對新台幣匯率 (2005~2014抓第一批，2015~2024抓第二批)
start_year = 2015
end_year = 2025

for year in range(start_year, end_year + 1):
    print(f"正在抓取 {year} 年資料...")
    try:
        data = yf.download("TWD=X", start=f"{year}-01-01", end=f"{year}-12-31")
        data.to_csv(f"USD_TWD_{year}.csv")

        # 關鍵：隨機休息 5~15 秒，模擬真人的行為
        wait_time = random.uniform(5, 15)
        print(f"成功，休息 {wait_time:.1f} 秒...")
        time.sleep(wait_time)

    except Exception as e:
        print(f"{year} 年抓取出錯: {e}")
        break # 如果被封鎖就停止，避免被永久封鎖
