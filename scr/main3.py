from fastapi import FastAPI, Query, HTTPException  # 增加 Query 用於參數處理，HTTP能準確回報錯誤給streamlit
from sqlalchemy import create_engine, Column, Integer, Float, String, Date
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Optional
from sqlalchemy import Column, Integer, Float, String, Date, DateTime, Text
from sqlalchemy.orm import Session
from fastapi import Depends
import yfinance as yf
import pandas as pd

app = FastAPI()

DATABASE_URL = "mysql+pymysql://root:yarrow1016@localhost/macro_monitor_1"
engine = create_engine(
    DATABASE_URL, 
    pool_size=10, 
    max_overflow=20,
    pool_recycle=3600
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    link = Column(String(500))
    source = Column(String(50))
    content = Column(Text)
    sentiment_score = Column(Float)
    importance_score = Column(Float)
    published = Column(String(100))
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

@app.get("/stock_price")
def get_stock_price(symbol: str = "AAPL"):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1mo") # 取近一個月數據
        if hist.empty:
            return {"error": f"找不到標的 {symbol}"}
        
        latest_price = hist['Close'].iloc[-1] # 轉成dict格式回傳streamlit
        prev_price = hist['Close'].iloc[-2]
        return {
            "symbol": symbol.upper(),
            "current_price": round(latest_price, 2),
            "change": round(latest_price - prev_price, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/available_dates")
def get_available_dates():
    db = SessionLocal()
    try:
        results = db.query(EconomicScore.score_date)\
                   .distinct()\
                   .order_by(EconomicScore.score_date.desc())\
                   .all()
        return [str(r.score_date) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail="無法獲取日期清單")
    finally:
        db.close()

# 獲取評分與燈號
@app.get("/signal")
def get_signal(target_date: Optional[str] = None):
    db = SessionLocal()
    try:
        query = db.query(EconomicScore)
        if target_date:
            result = query.filter(EconomicScore.score_date == target_date).first()
        else:
            result = query.order_by(EconomicScore.score_date.desc()).first()

        if result is None:
            return {"message": "no data found"}

        return {
            "date": str(result.score_date),
            "cpi_score": result.cpi_score,
            "ppi_score": result.ppi_score,
            "fx_score": result.fx_score,
            "total_score": result.total_score,
            "signal": result.signal_light
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="資料庫查詢失敗")
    finally:
        db.close()

@app.get("/news")
def get_news(db: Session = Depends(get_db)):
    articles = db.query(NewsArticle).order_by(NewsArticle.created_at.desc()).limit(10).all()
    return articles

@app.get("/")
def root():
    return {"status": "success", "message": "Economic Dashboard API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
