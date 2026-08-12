#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from crawler_logger import get_logger
import API

logger = get_logger()

client = MongoClient("mongodb://10.0.7.119:27017/")
db = client["crawler"]

faq_collection = db["faqs"]
car_collection = db["cars"]


# API 차량 데이터 적재
try:
    API.save_cars(car_collection)

except requests.exceptions.RequestException as e:
    logger.error(f"Cars API Error: {e}")


# FAQ HTML 크롤링
url = "http://192.168.0.51:4000/faqs"

try:
    response = requests.get(url, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for faq in soup.select("div.faq-list article.faq-item"):
        faq_collection.insert_one({
            "question": faq.select_one('[data-field="question"]').get_text(strip=True),
            "answer": faq.select_one('[data-field="answer"]').get_text(strip=True),
            "brand": faq.select_one('[data-field="brand"]').get_text(strip=True),
            "category": faq.get("data-category"),
            "faq_id": faq.get("data-faq-id"),
            "source_url": faq.get("data-source-url"),
            "reviewed_at": faq.get("data-reviewed-at")
        })

except requests.exceptions.RequestException as e:
    logger.error(f"FAQ URL: {url} | Error: {e}")
