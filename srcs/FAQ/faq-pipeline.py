#!/usr/bin/env python3


import requests
from bs4 import BeautifulSoup


response = requests.get("http://192.168.0.51:4000/faqs", timeout=15)
soup = BeautifulSoup(response.text, "html.parser")

for faq in soup.select("div.faq-list article.faq-item"):
    question = faq.select_one('h2')
    answer = faq.select_one('[data-field="answer"]')
    brand = faq.select_one("data-brand")
    category = faq.select_one("data-category")
    faq_id = faq.select_one("data-faq-id")
    source_url = faq.select_one("data-source-url")
    reviewed_at = faq.select_one("data-reviewed-at")
