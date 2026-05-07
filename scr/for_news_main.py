import feedparser
from newspaper import Article, Config
from textblob import TextBlob
from datetime import datetime
import time
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
import torch
from transformers import pipeline, BertTokenizer, BertForSequenceClassification

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
    pool_size = 5,
    pool_pre_ping = True,
    max_overflow = 10,
    pool_recycle = 3600,
    connect_args = {"ssl": {"fake_flag_to_enable_tls": True}}
)

SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine)
Base = declarative_base()

model_name = "yiyanghkust/finbert-tone"
tokenizer = BertTokenizer.from_pretrained(model_name)
model = BertForSequenceClassification.from_pretrained(model_name)
device = 0 if torch.cuda.is_available() else -1

finbert = pipeline(
    "sentiment-analysis", 
    model = model, 
    tokenizer = tokenizer, 
    device = device)

class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key = True, index = True)
    title = Column(String(255))
    link = Column(String(1000), unique = True)
    source = Column(String(50))
    content = Column(Text)
    sentiment_score = Column(Float)      
    sentiment_textblob = Column(Float)
    importance_score = Column(Float)
    published = Column(String(100))
    created_at = Column(DateTime, default = datetime.now)

RSS_FEEDS = {
    "CNN_Business": "http://rss.cnn.com/rss/money_latest.rss",
    "BBC_Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex"
}

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

def calculate_importance(content, sentiment_score):
    if not content: content = ""
    sentiment_intensity = abs(sentiment_score - 0.5) * 2 #情緒強度（偏離中立點的距離）
    keywords = ['fed','surge','rally','ATH','outperform','plunge','plummet','sell-out','slide','dip','guidance','bullish','bearish','blue-chip','ipo','hawkish','dovish','fomc','YTD','YoY','QoQ','inflation','rate cut','earnings','nasdaq','s&p 500','DJIA','QQQ','apple','meta','google','nvidia']
    hit_count = sum(1 for word in keywords if word in content.lower())
    kw_score = min(hit_count / 3, 1.0)
    total_score = (0.4 * sentiment_intensity) + (0.4 * kw_score) + (0.2 * min(len(content)/800, 1.0)) 
    return round(total_score, 3)

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ###### 設置 newspaper 的下載超時 ######
    config = Config()
    config.browser_user_agent = 'Mozilla/5.0'
    config.request_timeout = 10
    count = 0
     
    for name, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            if db.query(NewsArticle).filter(NewsArticle.link == entry.link).first():
                continue
                
            try:
                article = Article(entry.link,language='en')
                article.download()
                article.parse()

                fb_score, tb_score = get_sentiment(entry.title)
                imp_score = calculate_importance(article.text, fb_score)

                new_post = NewsArticle(
                        title = entry.title[:250],
                        link = entry.link,
                        source = name,
                        content = article.text[:1000],
                        sentiment_score = fb_score,
                        sentiment_textblob = tb_score,
                        importance_score = imp_score,
                        published = entry.get('published', '')
                    )
                db.add(new_post)
                db.commit()
                print(f"✅ {entry.title[:30]}")
            except Exception as e:
                db.rollback()
                print(f"❌ 失敗: {e}")
    db.close()
if __name__ == "__main__":
    main()
