import streamlit as st
from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, Text, desc, text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import sys
import os

st.set_page_config(page_title="經濟健康度儀表板", layout="wide")
Base = declarative_base()

try:
    if "mysql" in st.secrets:
        db_config = st.secrets["mysql"]
    else:
        db_config = {
            "user": "4RyYfQMvnH9DmYu.root",
            "password": "XD2WuF9AcDymVeCt",
            "host": "gateway01.ap-northeast-1.prod.aws.tidbcloud.com",
            "port": "4000",
            "database": "macro_monitor_1"
        }
    DATABASE_URL = (
        f"mysql+pymysql://{db_config['user']}:{db_config['password']}@"
        f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        f"?ssl_verify_cert=true&ssl_verify_identity=true"
    )
    engine = create_engine(
 
        DATABASE_URL,
        pool_size = 10,
        max_overflow = 20,
        pool_recycle = 3600,
        connect_args = {"ssl": {"fake_flag_to_enable_tls": True}}
    )
    
    SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine)
    Base = declarative_base()

    with engine.connect() as conn:
        conn.execute(text("SELECT 1;"))
        st.sidebar.success(f"✅ 雲端資料庫連線成功！")
        
except Exception as e:
    st.error(f"❌ 資料庫連線失敗：{e}")
    st.stop()

class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key = True, index = True)
    title = Column(String(255))
    link = Column(String(500), unique=True)
    source = Column(String(50))
    content = Column(Text)
    sentiment_score = Column(Float)
    sentiment_textblob = Column(Float)
    importance_score = Column(Float)
    published = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)

class EconomicScore(Base):
    __tablename__ = "economic_score"
    id = Column(Integer, primary_key = True)
    symbol = Column(String(20))
    score_date = Column(Date)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    adj_close = Column(Float)
    volume = Column(Integer)
    cpi_score = Column(Float)
    ppi_score = Column(Float)
    fx_score = Column(Float)
    total_score = Column(Float)
    signal_light = Column(String(20))

try:
    Base.metadata.create_all(bind = engine)
    st.sidebar.info("📌 資料庫結構已完成同步")
except Exception as schema_e:
    st.sidebar.error(f"結構同步失敗：{schema_e}")

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "scr")) 
##--------------------側邊按鈕------------------------
st.sidebar.title("- 跟上世界的按鈕 -")
if st.sidebar.button("🚀 立即更新大盤數據"):
    with st.spinner("正在同步 yfinance 數據..."):
        try:
            import update_db
            update_db.init_db() 
            for stock in ["IWM", "^DJI"]:
                update_db.fetch_and_sync_stock(stock)
            st.sidebar.success("大盤數據同步完成！")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"同步大盤失敗：{e}")
###            
if st.sidebar.button("💱 立即同步匯率數據"):
    with st.spinner("正在獲取 USD/TWD 匯率..."):
        try:
            import yfinance as yf
            fx_data = yf.download("TWD = X", start = "2015-01-01")
            
            if not fx_data.empty:
                fx_df = fx_data[['Close']].reset_index()
                fx_df.columns = ['date', 'close_price']
                fx_df['ticker'] = "TWD = X"
                
                fx_df.to_sql('exchange_rates', con = engine, if_exists = 'replace', index = False)
                
                st.sidebar.success("匯率同步完成！")
                st.rerun()
            else:
                st.sidebar.warning("Yahoo Finance 未回傳匯率資料")
        except Exception as e:
            st.sidebar.error(f"同步匯率失敗：{e}")
###
if st.sidebar.button("💡 立即抓取最新新聞"):
    with st.spinner("FinBERT 正在深度分析中..."):
        try:
            from scr import for_news_main 
            num_imported = for_news_main.main() 
            if num_imported and num_imported > 0:
                st.sidebar.success(f"新聞更新完成！共抓取 {num_imported} 則")
                st.rerun() 
            else:
                st.sidebar.warning("無新增新聞（可能皆為重複）。")
        except Exception as e:
            st.sidebar.error(f"❌ 抓取失敗：{e}")
##---------------------------API 邏輯------------------------------------
@st.cache_data(ttl = 600)
def fetch_stock_price_internal(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period = "1mo")
        if hist.empty:
            return None
        latest_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        return {
            "symbol": symbol.upper(),
            "current_price": round(latest_price, 2),
            "change": round(latest_price - prev_price, 2)
        }
    except:
        return None
#----------------------------熱門標的即時監控---------------------------------修改
st.subheader("🔥 熱門標的即時監控")
target_stocks = ["NVDA", "TSLA", "COST", "BA"] 
stock_cols = st.columns(len(target_stocks))

for i, symbol in enumerate(target_stocks):
    with stock_cols[i]:
        s_data = fetch_stock_price_internal(symbol)
        if s_data:
            st.metric(
                label = s_data["symbol"], 
                value = f"${s_data['current_price']}", 
                delta = f"{s_data['change']}"
            )
        else:
            st.info(f"等待 {symbol}...")
st.divider()
###-----------------------------------------------------------------------
def get_fx_data():
    query = "SELECT date, close_price FROM exchange_rates ORDER BY date ASC"
    df = pd.read_sql(query, engine)
    df['date'] = pd.to_datetime(df['date'])
    return df
st.title("美元:新台幣 (USD/TWD) 走勢圖")

fx_df = get_fx_data()

if not fx_df.empty:
    st.line_chart(fx_df.set_index('date')['close_price'])
else:
    st.warning("目前資料庫中沒有匯率數據，請執行爬蟲程式。")
##----------------------------大盤指數圖--------------------------------------
def show_main_charts():
    st.title("⚖️ 大盤指數圖 🔍")

    query = """
    SELECT 
        `score_date`,
        MAX(CASE WHEN `symbol` = '^DJI' THEN `adj_close` END) AS dow_jones,
        MAX(CASE WHEN `symbol` = 'IWM' THEN `adj_close` END) AS russell_2000,
        AVG(`total_score`) AS avg_score
    FROM `economic_score` 
    GROUP BY `score_date`
    ORDER BY `score_date` ASC
    """
    
    try:
        df = pd.read_sql(query, engine)
        
        if df.empty:
            st.warning("資料庫中目前沒有數據，請執行 update_db.py 進行同步。")
            return

        df['score_date'] = pd.to_datetime(df['score_date'])
        df = df.set_index('score_date')

        st.subheader("📊 大盤指數走勢")
        tab1, tab2 = st.tabs(["絕對數值", "漲跌幅對比 (%)"]) 
        with tab1:
            st.line_chart(df[['dow_jones', 'russell_2000']])          
        with tab2:
            norm_df = df[['dow_jones', 'russell_2000']].copy()
            norm_df = (norm_df / norm_df.iloc[0] - 1) * 100
            st.line_chart(norm_df)

        st.divider()
        latest = df.iloc[-1]
        c1, c2 = st.columns(2)
        c1.metric("道瓊指數", f"{latest['dow_jones']:,.2f}")
        c2.metric("羅素 2000 (IWM)", f"{latest['russell_2000']:,.2f}")

    except Exception as e:
        st.error(f"繪圖發生錯誤：{e}")
##--------------------------------經濟健康燈號---------------------------------------
def show_economic_dashboard():
    st.title("📊 經濟健康燈號 🚥")
    db = SessionLocal()

    def safe_float(value):
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    try: 
        dates = db.query(EconomicScore.score_date).distinct().order_by(EconomicScore.score_date.desc()).all()
        available_dates = [str(d.score_date) for d in dates]

        if not available_dates:
            st.warning("資料庫中尚無評分數據。")
            return

        selected_date = st.sidebar.selectbox("選擇查詢月份", options=available_dates)

        if selected_date:
            data = db.query(EconomicScore).filter(EconomicScore.score_date == selected_date).first()

            if data:
                col1, col2 = st.columns(2)
                total_val = safe_float(getattr(data, 'total_score', 0))
                col1.metric("綜合評分", f"{total_val:.1f}")
                with col2:
                    sig = data.signal_light.upper()
                    if "RED" in sig:
                        st.error("🔴 高風險紅燈")
                    elif "YELLOW" in sig:
                        st.warning("🟡 警示黃燈")
                    else:
                        st.success("🟢 穩健綠燈")
                
                st.divider()
                st.subheader("指標組成細項...")
                c1, c2, c3 = st.columns(3)

                cpi_val = float(getattr(data, 'cpi_score', 0) or 0)
                ppi_val = float(getattr(data, 'ppi_score', 0) or 0)
                fx_val = float(getattr(data, 'fx_score', 0) or 0)
                
                c1.metric("CPI 分數", f"{cpi_val:.1f}")
                c2.metric("PPI 分數", f"{ppi_val:.1f}")
                c3.metric("匯率分數", f"{fx_val:.1f}")
                
                with st.expander("指標說明:"):
                    st.write("CPI 分數：反映消費者物價與市場通膨壓力 🛒")
                    st.write("PPI 分數：反映生產者成本與工業熱度 🏭")
                    st.write("匯率分數：反映當前匯率對市場的影響 💸")
                    
    except Exception as e:
        st.error(f"載入數據時發生錯誤: {e}")
    finally:
        db.close()
##----------------------------------精選新聞----------------------------------------
def show_news_dashboard():
    st.title("📰 美股精選新聞 💰")
    with st.sidebar:
        days = st.sidebar.slider("幾天內新聞？", 1, 30, 7)
        limit = st.sidebar.number_input("顯示數量", 5, 50, 10)
        if st.button("💡 立即抓取"):
                with st.spinner("抓取中..."):
                    count = main() 
                    st.session_state['last_count'] = count
                st.rerun()
        if 'last_count' in st.session_state:
                st.info(f"上次抓取新增：{st.session_state['last_count']} 筆")
        
    db = SessionLocal()
    try:
        now_local = datetime.now()
        time_threshold = now_local - timedelta(days=days)
        
        top_news = db.query(NewsArticle) \
            .filter(NewsArticle.created_at >= time_threshold) \
            .order_by(desc(NewsArticle.importance_score)) \
            .limit(limit).all()
    
        if not top_news:
            st.warning("尚無新聞資料，請點擊左側「💡立即抓取」按鈕。")
        else:
            for news in top_news:
                with st.container():
                    col_score, col_main = st.columns([1.5, 6])
                    
                    with col_score:
                        imp = news.importance_score if news.importance_score is not None else 0.0
                        fb = news.sentiment_score if news.sentiment_score is not None else 0.5
                        tb = getattr(news, 'sentiment_textblob', 0.5) or 0.5
                        
                        st.metric("重要性", f"{imp:.2f}")
                        st.write(f"📖 **Fin:** `{fb:.2f}`")
                        st.write(f"📝 **Blob:** `{tb:.2f}`")

                    with col_main:
                        st.subheader(f"[{news.title}]({news.link})")
                        st.caption(f"來源: {news.source} | 抓取時間: {news.created_at.strftime('%m/%d %H:%M')}")
                        
                        with st.expander("🔍 內容摘要"):
                            st.write(news.content)
                            if fb > 0.6: st.success("市場情緒: Bullish")
                            elif fb < 0.4: st.error("市場情緒: Bearish")
                            else: st.info("市場情緒: Neutral")
                    st.divider() 
    except Exception as e:
        st.error(f"讀取失敗：{e}")
    finally:
        db.close()
##--------------------------------------------------------------------------------------------    
pg = st.navigation([
    st.Page(show_economic_dashboard, title="經濟指標", icon="📈"),
    st.Page(show_main_charts, title="大盤指數圖", icon="⚖️"),
    st.Page(show_news_dashboard, title="美股新聞", icon="📰"),
])
st.sidebar.markdown("---")
pg.run()
