#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from crawler_logger import get_logger
from faq_db import insert_if_new

logger = get_logger()

client = MongoClient("mongodb://10.0.7.119:27017/")
db = client["crawler"]
faq_collection = db["faqs"]

url = "http://43.203.233.157/faqs"

try:
    response = requests.get(url, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for faq in soup.select("div.faq-list article.faq-item"):
            insert_if_new(faq_collection, {
                    "faq_id": faq.get("data-faq-id"),
                    "brand": faq.select_one('[data-field="brand"]').get_text(strip=True),
                    "category": faq.get("data-category"),
                    "question": faq.select_one('[data-field="question"]').get_text(strip=True),
                    "answer": faq.select_one('[data-field="answer"]').get_text(strip=True),
                    "source_url": faq.get("data-source-url"),
                    "reviewed_at": faq.get("data-reviewed-at")
                })

except requests.exceptions.RequestException as e:
    logger.error(f"FAQ URL: {url} | Error: {e}")
