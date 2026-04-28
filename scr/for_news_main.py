import feedparser
from newspaper import Article
from textblob import TextBlob
from datetime import datetime
import time
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
import torch
from transformers import pipeline

device = 0 if torch.cuda.is_available() else -1
finbert = pipeline("sentiment-analysis", model="yiyanghkust/finbert-tone", device=device)

DB_USER = "4RyYfQMvnH9DmYu.root"
DB_PASSWORD = "XD2WuF9AcDymVeCt"
DB_HOST = "gateway01.ap-northeast-1.prod.aws.tidbcloud.com"
DB_PORT = "4000"
DB_NAME = "macro_monitor_1"

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@"
    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?ssl_verify_cert=true&ssl_verify_identity=true"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    pool_pre_ping=True,
    max_overflow=10,
    pool_recycle=3600,
    connect_args={"ssl": {"fake_flag_to_enable_tls": True}}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

device = 0 if torch.cuda.is_available() else -1
finbert = pipeline("sentiment-analysis", model="yiyanghkust/finbert-tone", device=device)

class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    link = Column(String(500), unique=True)
    source = Column(String(50))
    content = Column(Text)
    sentiment_score = Column(Float)      
    sentiment_textblob = Column(Float)
    importance_score = Column(Float)
    published = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)

RSS_FEEDS = {
    "CNN_Business": "http://rss.cnn.com/rss/money_latest.rss",
    "BBC_Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    'Yahoo Finance': 'https://finance.yahoo.com/news/rssindex'
}
##################################################################
def get_sentiment(text):
    if not text:
        return 0.5, 0.5
    blob_polarity = TextBlob(text).sentiment.polarity
    tb_score = (blob_polarity + 1) / 2

    try:
        res = finbert(text[:512])[0] #  上限 512 tokens
        label_map = {'Positive': 1, 'Negative': 0, 'Neutral': 0.5}
        fb_score = label_map.get(res['label'], 0.5)
    except Exception as e:
        fb_score = tb_score # Fallback 備援
    return float(fb_score), float(tb_score)
###################################################################
def calculate_importance(content, sentiment_score):
    if not content:
        content = ""
    keywords = ['fed','surge','rally','ATH','outperform','plunge','plummet','sell-out','slide','dip','guidance','bullish','bearish','blue-chip','ipo','hawkish','dovish','fomc','YTD','YoY','QoQ','inflation','rate cut','earnings','nasdaq','s&p 500','DJIA','QQQ','apple','meta','google','nvidia']
    hit_count = sum(1 for word in keywords if word in content.lower())
    kw_score = min(hit_count / 3, 1.0)
    total_score = (0.4 * sentiment_score) + (0.4 * kw_score) + (0.2 * min(len(content)/800, 1.0))
    return round(total_score, 3)

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    count = 0
    
    print("--- 開始抓取新聞 ---")
    try:
        for name, url in RSS_FEEDS.items():
            print(f"正在掃描 {name}...")
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:10]:
                link = entry.link
                
                existing = db.query(NewsArticle).filter(NewsArticle.link == link).first()
                if existing:
                    print(f"跳過重複: {link[:30]}...")
                    continue 

                try:
                    article = Article(link,language='en')
                    article.download()
                    article.parse()

                    title = entry.get('title', 'No Title')
                    raw_content = article.text if article.text else ""
                    clean_content = article.text.strip()[:500]
                    fb_score, tb_score = get_sentiment(title)
                    imp_score = calculate_importance(clean_content, fb_score)
                    content = article.text


                    new_news = NewsArticle(
                        title = title[:250],
                        link  =link,
                        source = name,
                        content = clean_content,
                        sentiment_score = fb_score,     
                        sentiment_textblob = tb_score,
                        importance_score = imp_score,
                        published = entry.get('published', ''),
                        created_at = datetime.now()
                    )                    
                    db.add(new_news)
                    db.commit()
                    
                    print(f"✅ 已匯入: {title[:30]}...")
                    count += 1
                    time.sleep(1)

                except Exception as e:
                    db.rollback()
                    print(f"❌ 單篇解析失敗: {e}")
                    continue
                    
    except Exception as big_e:
        print(f"💥 程式執行中斷: {big_e}")        
    finally:
        db.close()
        print(f"--- 任務結束，共抓取 {count} 則新聞 ---")
    
    return count
if __name__ == "__main__":
    main()
