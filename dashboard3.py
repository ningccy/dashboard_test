import streamlit as st
from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, Text, desc, text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

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

Base.metadata.create_all(bind=engine)

# API 邏輯
@st.cache_data(ttl=600)
def fetch_stock_price_internal(symbol):
# 直接執行 yfinance 
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
def get_db_engine():
    db_info = {
        "user": "4RyYfQMvnH9DmYu.root",
        "pw": "XD2WuF9AcDymVeCt",
        "host": "gateway01.ap-northeast-1.prod.aws.tidbcloud.com",
        "port": 4000,
        "db": "macro_monitor_1"
    }
    url = "mysql+pymysql://4RyYfQMvnH9DmYu.root:XD2WuF9AcDymVeCt@gateway01.ap-northeast-1.prod.aws.tidbcloud.com:4000/macro_monitor_1?ssl_ca=/etc/ssl/cert.pem"
    return create_engine(url)

engine = get_db_engine()

st.title("⚖️ 大盤指數圖 🔍")
query = "SELECT symbol, score_date, total_score FROM economic_score ORDER BY score_date ASC"

try:
    df_scores = pd.read_sql(query, engine)
    df_scores['score_date'] = pd.to_datetime(df_scores['score_date'])

    st.subheader("指數趨勢 (IWM & DJI)")
    
    # 使用 pivot 讓資料適合畫圖：Index 為日期，Columns 為 symbol
    plot_data = df_scores.pivot(index='score_date', columns='symbol', values='total_score')
    
    # 在 Streamlit 顯示折線圖
    st.line_chart(plot_data)

    # 也可以用分欄顯示最新的分數
    cols = st.columns(len(plot_data.columns))
    for i, symbol in enumerate(plot_data.columns):
        latest_score = plot_data[symbol].iloc[-1]
        cols[i].metric(label=f"{symbol} 最新評分", value=f"{latest_score:.1f}")

except Exception as e:
    st.error(f"無法讀取資料庫：{e}")
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
                    st.write(f"CPI 分數: {data.cpi_score}")
                    st.write(f"PPI 分數: {data.ppi_score}")
                    st.write(f"匯率分數: {data.fx_score}")
    finally:
        db.close()

def show_news_dashboard():
    st.title("📰 美股精選新聞 💰")

    days = st.sidebar.slider("幾天內新聞？", 1, 30, 7)
    limit = st.sidebar.number_input("顯示數量", 5, 50, 10)
############################################################
    db = SessionLocal()
    try:
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
    
pg = st.navigation([
    st.Page(show_economic_dashboard, title="經濟指標", icon="📈"),
    st.Page(show_news_dashboard, title="美股新聞", icon="📰"),
])
st.sidebar.title("金融監控中心")
st.sidebar.markdown("---")
pg.run()
