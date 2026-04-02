import streamlit as st
from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, Text, desc, text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="經濟健康度儀表板", layout="wide")
Base = declarative_base()

# --- 2. 資料庫連線設定 (整合 TiDB Cloud 資訊) ---
try:
    # 優先從 Streamlit Secrets 讀取，若無則使用寫死的資訊（建議在 Secrets 填寫）
    if "mysql" in st.secrets:
        db_config = st.secrets["mysql"]
    else:
        # 這裡保留你 main3.py 中的連線資訊作為後備
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
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        conn.execute(text("SELECT 1;"))
        st.sidebar.success(f"✅ 雲端資料庫連線成功！")
        
except Exception as e:
    st.error(f"❌ 資料庫連線失敗：{e}")
    st.stop()

# --- 3. 資料模型定義 (結合 main3.py 與原本的定義) ---
class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    link = Column(String(500))
    source = Column(String(50))
    content = Column(Text)
    sentiment_score = Column(Float)
    importance_score = Column(Float)
    created_at = Column(DateTime)

class EconomicScore(Base):
    __tablename__ = "economic_score"
    id = Column(Integer, primary_key=True, index=True)
    score_date = Column(Date)
    cpi_score = Column(Float)
    ppi_score = Column(Float)
    fx_score = Column(Float)
    total_score = Column(Float)
    signal_light = Column(String(10))

# --- 4. 功能函數整合 (原本 main3.py 的 API 邏輯) ---

@st.cache_data(ttl=600)
def fetch_stock_price_internal(symbol):
# 取代原本 requests.get 的 API 呼叫，直接執行 yfinance 邏輯
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

# --- 5. UI 呈現：即時股價監控 ---
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

# --- 6. 分頁內容：經濟指標 ---
def show_economic_dashboard():
    st.title("📊 經濟健康燈號 🚥")
    db = SessionLocal()
    try: 
        # 獲取日期清單 (對應原本 API 的 /available_dates)
        dates = db.query(EconomicScore.score_date).distinct().order_by(EconomicScore.score_date.desc()).all()
        available_dates = [str(d.score_date) for d in dates]

        if not available_dates:
            st.warning("資料庫中尚無評分數據。")
            return

        selected_date = st.sidebar.selectbox("選擇查詢月份", options=available_dates)

        if selected_date:
            # 獲取評分資料 (對應原本 API 的 /signal)
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
                
                # 額外顯示詳細細項 (原本 main3.py 有但原本 dashboard 沒顯示的)
                with st.expander("查看詳細組成分數"):
                    st.write(f"CPI 分數: {data.cpi_score}")
                    st.write(f"PPI 分數: {data.ppi_score}")
                    st.write(f"匯率分數: {data.fx_score}")
    finally:
        db.close()

# --- 7. 分頁內容：美股新聞 ---
def show_news_dashboard():
    st.title("📰 美股精選新聞 💰")

    days = st.sidebar.slider("幾天內新聞？", 1, 30, 7)
    limit = st.sidebar.number_input("顯示數量", 5, 50, 10)

    db = SessionLocal()
    try:
        # 對應原本 API 的 /news 邏輯
        time_threshold = datetime.now() - timedelta(days=days)
        top_news = db.query(NewsArticle) \
            .filter(NewsArticle.created_at >= time_threshold) \
            .order_by(desc(NewsArticle.importance_score)) \
            .limit(limit).all()

        if not top_news:
            st.warning("所選範圍內尚無新聞資料。")
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

# --- 8. 導航與側邊欄控制 ---
pg = st.navigation([
    st.Page(show_economic_dashboard, title="經濟指標", icon="📈"),
    st.Page(show_news_dashboard, title="美股新聞", icon="📰"),
])
st.sidebar.title("金融監控中心")
st.sidebar.markdown("---")
pg.run()
