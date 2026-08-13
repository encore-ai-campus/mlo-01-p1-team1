#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from crawler_logger import get_logger
from mongo_handler import save_faqs
import API

logger = get_logger()
faq_data = []


# API 키 자동 조회 및 인증 API 호출
try:
    API.run()

except requests.exceptions.RequestException as e:
    logger.error(f"API 인증 오류: {e}")


# FAQ HTML 크롤링
url = "http://192.168.0.51:4000/faqs"

try:
    response = requests.get(url, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # FAQ 데이터를 리스트에 수집
    for faq in soup.select("div.faq-list article.faq-item"):
        faq_data.append({
            "question": faq.select_one(
                '[data-field="question"]'
            ).get_text(strip=True),

            "answer": faq.select_one(
                '[data-field="answer"]'
            ).get_text(strip=True),

            "brand": faq.select_one(
                '[data-field="brand"]'
            ).get_text(strip=True),

            "category": faq.get("data-category"),
            "faq_id": faq.get("data-faq-id"),
            "source_url": faq.get("data-source-url"),
        })

    # 수집한 FAQ 데이터를 MongoDB에 저장
    save_faqs(faq_data)

except requests.exceptions.RequestException as e:
    logger.error(f"FAQ URL: {url} | Error: {e}")
