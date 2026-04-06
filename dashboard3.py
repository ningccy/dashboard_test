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
        # 連線資訊作為後備
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
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        connect_args={"ssl": {"fake_flag_to_enable_tls": True}}
    )
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    with engine.connect() as conn:
        conn.execute(text("SELECT 1;"))
        st.sidebar.success(f"✅ 雲端資料庫連線成功！")
        
except Exception as e:
    st.error(f"❌ 資料庫連線失敗：{e}")
    st.stop()


class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    link = Column(String(500), unique=True)
    source = Column(String(50))
    content = Column(Text)
    sentiment_score = Column(Float)
    importance_score = Column(Float)
    published = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)

class EconomicScore(Base):
    __tablename__ = "economic_score"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20))
    score_date = Column(Date)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    adj_close = Column(Float)
    volume = Column(Integer)
    total_score = Column(Float)
    signal_light = Column(String(20))
#########################################
# NewsArticle.__table__.drop(engine, checkfirst=True)
try:
    Base.metadata.create_all(bind=engine)
    st.sidebar.info("📌 資料庫結構已完成同步")
except Exception as schema_e:
    st.sidebar.error(f"結構同步失敗：{schema_e}")

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "scr")) 

st.sidebar.title("管理員工具")
if st.sidebar.button("🚀 立即更新大盤數據"):
    with st.spinner("正在同步 yfinance 數據..."):
        try:
            import update_db
            # 強制重新建立表以確保欄位正確
            update_db.init_db() 
            for stock in ["IWM", "^DJI"]:
                update_db.fetch_and_sync_stock(stock)
            st.sidebar.success("大盤數據同步完成！")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"同步大盤失敗：{e}")

if st.sidebar.button("🔄 立即抓取最新新聞"):
    with st.spinner("正在分析財經新聞中..."):
        try:
            import for_news_main 
            for_news_main.main()
            st.sidebar.success("新聞更新完成！")
            st.rerun() 
        except Exception as e:
            st.sidebar.error(f"抓取新聞失敗：{e}")

#########################################
# API 邏輯
@st.cache_data(ttl=600)
def fetch_stock_price_internal(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1mo")
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

st.subheader("🔥 熱門標的即時監控")
target_stocks = ["NVDA", "TSLA", "COST", "BA"] 
stock_cols = st.columns(len(target_stocks))

for i, symbol in enumerate(target_stocks):
    with stock_cols[i]:
        s_data = fetch_stock_price_internal(symbol)
        if s_data:
            st.metric(
                label=s_data["symbol"], 
                value=f"${s_data['current_price']}", 
                delta=f"{s_data['change']}"
            )
        else:
            st.info(f"等待 {symbol}...")

st.divider()
##________________________________________________________________
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
##________________________________________________________
def show_economic_dashboard():
    st.title("📊 經濟健康燈號 🚥")
    db = SessionLocal()
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
                col1.metric("綜合評分", f"{data.total_score:.1f}")
                with col2:
                    sig = data.signal_light.upper()
                    if "RED" in sig:
                        st.error("🔴 高風險紅燈")
                    elif "YELLOW" in sig:
                        st.warning("🟡 警示黃燈")
                    else:
                        st.success("🟢 穩健綠燈")
                
                with st.expander("查看詳細組成分數"):
                    cpi = getattr(data, 'cpi_score', "無資料")
                    ppi = getattr(data, 'ppi_score', "無資料")
                    fx = getattr(data, 'fx_score', "無資料")
                    
                    st.write(f"CPI 分數: {cpi}")
                    st.write(f"PPI 分數: {ppi}")
                    st.write(f"匯率分數: {fx}")
    finally:
        db.close()
############################################################
def show_news_dashboard():
    st.title("📰 美股精選新聞 💰")

    days = st.sidebar.slider("幾天內新聞？", 1, 30, 7)
    limit = st.sidebar.number_input("顯示數量", 5, 50, 10)
    
    if st.sidebar.button("🔄 立即抓取最新新聞"):
        with st.spinner("正在分析財經新聞中..."):
            try:
                from scr import for_news_main 
                num_imported = for_news_main.main() 
                
                if num_imported and num_imported > 0:
                    st.sidebar.success(f"✅ 新聞更新完成！共抓取 {num_imported} 則")
                    st.rerun() 
                else:
                    st.sidebar.warning("⚠️ 抓取結束，但沒有新增新聞（可能皆為重複）。")
            except Exception as e:
                st.sidebar.error(f"❌ 抓取失敗：{e}")

    db = SessionLocal()
    try:
        now_local = datetime.now()
        time_threshold = now_local - timedelta(days=days)
        
        top_news = db.query(NewsArticle) \
            .filter(NewsArticle.created_at >= time_threshold) \
            .order_by(desc(NewsArticle.importance_score)) \
            .limit(limit).all()
    
        if not top_news:
            st.warning("所選範圍內尚無新聞資料，請點擊左側「立即抓取」按鈕。")
        else:
            for news in top_news:
                with st.container():
                    col_s, col_c = st.columns([1, 6])
                    col_s.metric("重要性", f"{news.importance_score:.2f}")
                    with col_c:
                        st.subheader(f"[{news.title}]({news.link})")
                        st.caption(f"來源: {news.source} | 情緒: {news.sentiment_score:.2f}")
                        with st.expander("內容摘要"):
                            st.write(news.content)
                    st.divider() 
    except Exception as e:
        st.error(f"讀取新聞失敗：{e}")
    finally:
        db.close()
    
pg = st.navigation([
    st.Page(show_economic_dashboard, title="經濟指標", icon="📈"),
    st.Page(show_main_charts, title="大盤指數圖", icon="⚖️"),
    st.Page(show_news_dashboard, title="美股新聞", icon="📰"),
])
st.sidebar.markdown("---")
pg.run()
