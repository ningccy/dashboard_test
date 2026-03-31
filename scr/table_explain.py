import pandas as pd

tables = {
"stocks": [
["id", "integer", "股票流水編號", "PK"],
["stock_symbol", "varchar", "股票代號（如 AAPL、TSLA）", ""],
["stock_name", "varchar", "股票全名", ""],
["is_ETF", "bool", "是否為 ETF", ""],
["created_at", "timestamp", "資料建立時間", ""],
["updated_at", "timestamp", "資料最後更新時間", ""],
],
"stock_price": [
["id", "integer", "每筆價格資料流水編號", "PK"],
["stock_id", "integer", "對應 stocks.id", "FK → stocks.id"],
["date", "timestamp", "日期", ""],
["open", "float", "開盤價", ""],
["high", "float", "最高價", ""],
["low", "float", "最低價", ""],
["close", "float", "收盤價", ""],
["adj_close", "float", "調整後收盤價（考慮除權息）", ""],
["volume", "int", "成交量", ""],
["created_at", "timestamp", "資料建立時間", ""],
["updated_at", "timestamp", "資料最後更新時間", ""],
],
"company_info": [
["id", "integer", "流水編號", "PK"],
["stock_id", "integer", "對應 stocks.id", "FK → stocks.id"],
["created_at", "timestamp", "資料建立時間", ""],
["updated_at", "timestamp", "資料最後更新時間", ""],
],
"macro_indicators": [
["id", "integer", "指標流水編號", "PK"],
["code", "varchar", "指標代碼（如 CPI、GDP）", ""],
["name", "varchar", "指標名稱", ""],
["created_at", "timestamp", "資料建立時間", ""],
["updated_at", "timestamp", "資料最後更新時間", ""],
],
"macro_data": [
["id", "integer", "流水編號", "PK"],
["indicator_id", "integer", "對應 macro_indicators.id", "FK → macro_indicators.id"],
["date", "timestamp", "資料日期（年/季/月）", ""],
["value", "float", "指標數值", ""],
["frequency", "varchar(1)", "資料頻率，Y=年, Q=季, M=月", ""],
["created_at", "timestamp", "資料建立時間", ""],
["updated_at", "timestamp", "資料最後更新時間", ""],
],
"currencies": [
["id", "integer", "幣別流水編號", "PK"],
["currency_code", "varchar", "幣別代碼（如 USD、TWD、EUR）", ""],
["created_at", "timestamp", "資料建立時間", ""],
["updated_at", "timestamp", "資料最後更新時間", ""],
],
"exchange_rate": [
["id", "integer", "流水編號", "PK"],
["currency_id", "integer", "對應 currencies.id", "FK → currencies.id"],
["date", "timestamp", "匯率日期", ""],
["open", "float", "開盤匯率", ""],
["close", "float", "收盤匯率", ""],
["adj_close", "float", "調整後收盤匯率", ""],
["created_at", "timestamp", "資料建立時間", ""],
["updated_at", "timestamp", "資料最後更新時間", ""],
],
}
with pd.ExcelWriter("database_schema.xlsx") as writer:
    for table_name, columns in tables.items():
        df = pd.DataFrame(columns, columns=["欄位名", "型別", "說明", "PK/FK"])
        df.to_excel(writer, sheet_name=table_name, index=False)

print("Excel 已生成: database_schema.xlsx")
