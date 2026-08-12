#!/usr/bin/env python3


import requests

def run():
    base = "http://43.203.233.157"
    key_info = requests.get(base + "/api/v1/public-key", timeout=10).json()
    headers = {"X-API-Key": key_info["data"]["current"]["api_key"]}

    path = "/api/v1/cars/cursor?after_id=0&limit=500"

    while path:
        response = requests.get(base + path, headers=headers, timeout=10)

        if response.status_code == 403:
            key_info = requests.get(base + "/api/v1/public-key", timeout=10).json()
            headers["X-API-Key"] = key_info["data"]["current"]["api_key"]

            response = requests.get(base + path, headers=headers, timeout=10)

        response.raise_for_status()
        payload = response.json()

        # payload["data"]를 파일 또는 DB에 즉시 저장
        path = payload["links"]["next"]
