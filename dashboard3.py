import streamlit as st
from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, Text, desc,text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import requests

#API_BASE = "http://8.229.26.9:8000"
#DB_USER = os.getenv("DB_USER")
#DB_PASSWORD = os.getenv("DB_PASSWORD")
#DB_HOST = os.getenv("DB_HOST")
#DB_NAME = os.getenv("DB_NAME")

st.set_page_config(page_title="經濟健康度儀表板", layout="wide")
Base = declarative_base()

try:
    db_config = st.secrets["mysql"]
    DATABASE_URL = (
        f"mysql+pymysql://{db_config[]}:{db_config['password']}@"
        f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        f"?ssl_verify_cert=true&ssl_verify_identity=true"
    )

    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800
    )
    
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    # 測試連線
    with engine.connect() as conn:
        result = conn.execute(text("SELECT NOW();"))
        # 使用 st.write 讓你在網頁上也能看到測試結果
        st.sidebar.success(f"✅ 資料庫連線成功！")
        
except Exception as e:
    st.error(f"❌ 資料庫連線失敗：{e}")

API_BASE = f"http://127.0.0.1:8000"  
DATABASE_URL = "mysql+pymysql://root:yarrow1016@127.0.0.1:3306/macro_monitor_1"
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle= 1800
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT NOW();"))
        print("✅ 連線成功！資料庫時間：", result.fetchone())
except Exception as e:
    print("❌ 連線失敗：", e)



#(保留) 從 API 獲取即時個股價格
@st.cache_data(ttl=300)
def fetch_stock_price(symbol):
    try:
       res = requests.get(f"{API_BASE}/stock_price", params={"symbol": symbol}, timeout=5)
       return res.json() if res.status_code == 200 else None
    except:
       return None

class EconomicScore(Base):
    __tablename__ = "economic_score"
    id = Column(Integer, primary_key=True)
    score_date = Column(Date)
    total_score = Column(Float)
    signal_light = Column(String(10))

class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    link = Column(String(500))
    source = Column(String(50))
    content = Column(Text)
    sentiment_score = Column(Float)
    importance_score = Column(Float)
    created_at = Column(DateTime)

st.subheader("🔥 熱門標的即時監控(來源:API)")
target_stocks = ["NVDA", "TSLA", "COST", "BA"] 
stock_cols = st.columns(len(target_stocks))

for i, symbol in enumerate(target_stocks):
    with stock_cols[i]:
        s_data = fetch_stock_price(symbol)
        if s_data and "current_price" in s_data:
            st.metric(
                label=s_data["symbol"], 
                value=f"${s_data['current_price']}", 
                delta=f"{s_data['change']}"
            )
        else:
            st.info(f"等待 {symbol}...")

st.divider()


def show_economic_dashboard():
    st.title("📊 經濟健康traffic light 🚥")

    db = SessionLocal()
    try: 
        dates = db.query(EconomicScore.score_date).distinct().order_by(EconomicScore.score_date.desc()).all()
        available_dates = [str(d.score_date) for d in dates]

        selected_date = st.sidebar.selectbox("選擇查詢月份", options=available_dates)

        if selected_date:
            data = db.query(EconomicScore).filter(EconomicScore.score_date == selected_date).first()

            col1, col2 = st.columns(2)
            col1.metric("綜合評分", f"{data.total_score:.1f}")
            with col2:
                sig = data.signal_light.upper()
                if sig == "RED":
                    st.error("🔴 高風險紅燈")
                elif sig == "YELLOW":
                    st.warning("🟡 警示黃燈")
                else:
                    st.success("🟢 穩健綠燈")
    finally:
        db.close()


def show_news_dashboard():
    st.title("📰 美股精選新聞 💰")

    days = st.sidebar.slider("幾天內新聞？", 1, 7, 3)
    limit = st.sidebar.number_input("顯示數量", 5, 50, 10)

    db = SessionLocal()
    try:
        time_threshold = datetime.now() - timedelta(days=days)
        top_news = db.query(NewsArticle) \
            .filter(NewsArticle.created_at >= time_threshold) \
            .order_by(desc(NewsArticle.importance_score)) \
            .limit(limit).all()

        if not top_news:
            st.warning("資料庫中尚無資料，請先執行爬蟲。")
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
    finally:
        db.close()



pg = st.navigation([
    st.Page(show_economic_dashboard, title="經濟指標", icon="📈"),
    st.Page(show_news_dashboard, title="美股新聞", icon="📰"),
])
st.sidebar.title("金融監控中心")
st.sidebar.markdown("---")
pg.run()
