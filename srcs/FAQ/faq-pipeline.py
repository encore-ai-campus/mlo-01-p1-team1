#!/usr/bin/env python3


import logging
import requests
from bs4 import BeautifulSoup

url = "http://192.168.0.51:4000/faqs"

logging.basicConfig(
    filename="/home/ec2-user/logs/request/non-exists-url-error.log",
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

try:
    response = requests.get(url, timeout=15)
    response.raise_for_status()  # 404, 500 오류도 예외로 처리

except requests.exceptions.RequestException as e:
    logging.error(f"URL: {url} | Error: {e}")

else:
    soup = BeautifulSoup(response.text, "html.parser")
    faq_item = []

    for faq in soup.select("div.faq-list article.faq-item"):
        question = faq.select_one('[data-field="question"]').get_text(strip=True)
        answer = faq.select_one('[data-field="answer"]').get_text(strip=True)
        brand = faq.select_one('[data-field="brand"]').get_text(strip=True)
        category = faq.get("data-category")
        faq_id = faq.get("data-faq-id")
        source_url = faq.get("data-source-url")
        reviewed_at = faq.get("data-reviewed-at")


        faq_item.append([question, answer, brand, category, faq_id, source_url, reviewed_at])




