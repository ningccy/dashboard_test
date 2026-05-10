from transformers import BertTokenizer, BertForSequenceClassification 
from transformers import pipeline
import torch

model_name = "yiyanghkust/finbert-tone" 
tokenizer = BertTokenizer.from_pretrained(model_name) 
model = BertForSequenceClassification.from_pretrained(model_name) 
nlp = pipeline("sentiment-analysis", model = model, tokenizer = tokenizer) 

def get_finbert_sentiment(text):
    if not text or len(text) < 5:
        return 0
    truncated_text = text[:500] 
    results = nlp(truncated_text)
    
    label = results[0]['label']
    score = results[0]['score']
    
    if label == 'Positive':
        return score
    elif label == 'Negative':
        return -score
    else:
        return 0
