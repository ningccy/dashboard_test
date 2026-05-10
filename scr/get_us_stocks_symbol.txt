import pandas as pd

# 資料來源
nasdaq_url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"
other_url  = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"

# 拿掉最後一行 資料筆數統計
df_nasdaq= pd.read_csv(nasdaq_url, sep="|").iloc[:-1]
df_other  = pd.read_csv(other_url, sep="|").iloc[:-1]


# 更改欄位名曾
df_nasdaq= df_nasdaq.rename(columns={"Symbol" : "stock_symbol",
                                        "Security Name" : "stock_security_name",
                                        "ETF" : "is_ETF"})
df_other = df_other.rename(columns= {"ACT Symbol" : "stock_symbol",
                                     "Security Name" : "stock_security_name",
                                     "ETF" : "is_ETF"})

#格式轉換
df_nasdaq.columns = df_nasdaq.columns.str.strip()
df_other.columns  = df_other.columns.str.strip()

df_nasdaq= df_nasdaq[["stock_symbol","stock_security_name","is_ETF"]]
df_other = df_other[["stock_symbol","stock_security_name","is_ETF"]]


# 資料合併
us_stock_df = pd.concat([df_nasdaq, df_other],ignore_index=True)


us_stock_df["stock_symbol"] = us_stock_df["stock_symbol"].astype(str).str.strip()
us_stock_df["stock_symbol"].replace({"": "N/A"}, inplace=True)

us_stock_df.to_csv("us_stock_symbol.csv", index=False)
print(f"已完成存檔：us_stock_symbol {len(us_stock_df)} 支股票")
