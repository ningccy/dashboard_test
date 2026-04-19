from transformers import BertTokenizer, BertForSequenceClassification 
from transformers import pipeline
import torch

# 1. 載入模型與分詞器 (初次執行會下載，約 400MB)
model_name = "yiyanghkust/finbert-tone" 
tokenizer = BertTokenizer.from_pretrained(model_name)
model = BertForSequenceClassification.from_pretrained(model_name)

# 2. 建立 Pipeline (這是 HuggingFace 最簡單的使用方式)
nlp = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)

def get_finbert_sentiment(text):
    if not text or len(text) < 5:
        return 0

    truncated_text = text[:500] 
    
    results = nlp(truncated_text)
    
    # 轉換結果為數值 (-1 到 1)
    # yiyanghkust/finbert-tone 輸出標籤為 Neutral, Positive, Negative
    label = results[0]['label']
    score = results[0]['score']
    
    if label == 'Positive':
        return score
    elif label == 'Negative':
        return -score
    else:
        return 0
