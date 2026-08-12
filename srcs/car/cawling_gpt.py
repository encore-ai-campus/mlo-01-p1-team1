import logging
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from log_config import createLogger
from sql_handler import filter_new_cars, save_to_mysql


BASE = "http://43.203.233.157"
RETRY_SECONDS = 180
MAX_PAGES = 500

connection_logger, query_logger = createLogger()

logging.basicConfig(
    filename="/home/ec2-user/crawler_error.log",
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)

db_password = Path("/home/ec2-user/db_password.txt").read_text(
    encoding="utf-8"
).strip()

engine = create_engine(
    URL.create(
        drivername="mysql+pymysql",
        username="MLO01_001",
        password=db_password,
        host="10.0.5.119",
        port=3306,
        database="car_db",
    ),
    pool_pre_ping=True,
)


def request_with_retry(url, headers=None):
    while True:
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=10,
            )

            # 자정 이후 API 키가 변경된 경우
            if response.status_code == 403 and headers is not None:
                headers.clear()
                headers.update(get_headers())

                response = requests.get(
                    url,
                    headers=headers,
                    timeout=10,
                )

            response.raise_for_status()
            return response

        # 네트워크 연결 및 시간 초과: 3분 후 같은 URL 재시도
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as error:
            logging.error("URL=%s | Network error | %s", url, error)
            print(f"서버 연결 실패. 3분 후 같은 URL을 재시도합니다: {url}")
            time.sleep(RETRY_SECONDS)

        # 서버 오류: 3분 후 같은 URL 재시도
        except requests.exceptions.HTTPError as error:
            status_code = error.response.status_code

            if status_code == 429:
                retry_after = error.response.headers.get("Retry-After")

                wait_seconds = (
                    int(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 180
                )

                logging.error(
                    "URL=%s | 429 Too Many Requests | %s초 후 재시도",
                    url,
                    wait_seconds,
                )

                print(
                    f"요청이 너무 많습니다. "
                    f"{wait_seconds}초 후 같은 차량부터 재시도합니다."
                )

                time.sleep(wait_seconds)
                continue

            if status_code >= 500:
                logging.error("URL=%s | Server error | %s", url, error)
                print(f"서버 오류. 3분 후 같은 URL을 재시도합니다: {url}")
                time.sleep(RETRY_SECONDS)
                continue

            # 401, 403, 404 등은 로그 기록 후 중단
            logging.error("URL=%s | HTTP error | %s", url, error)
            raise

        # 그 밖의 requests 오류는 로그 기록 후 중단
        except requests.exceptions.RequestException as error:
            logging.error("URL=%s | Request error | %s", url, error)
            raise


def get_headers():
    key_response = request_with_retry(
        BASE + "/api/v1/public-key"
    )
    key_info = key_response.json()

    api_key = key_info["data"]["current"]["api_key"]

    return {"X-API-Key": api_key}


def text_of(node, selector):
    element = node.select_one(selector)

    if element is None:
        raise ValueError(
            f"선택자를 찾을 수 없습니다: {selector}"
        )

    return element.get_text(strip=True)


headers = get_headers()
url = BASE + "/cars?sort=newest&page=1&page_size=20"
total_saved = 0
page = 1

while url and page <= MAX_PAGES:
    response = request_with_retry(
        url,
        headers=headers,
    )

    # 한글 깨짐 방지
    response.encoding = "utf-8"

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    page_data = []

    for row in soup.select(
        "div.board-list__body article.board-list__row.car-card"
    ):
        detail_url = response.url

        try:
            title_link = row.select_one("h2.car-title a")

            if title_link is None:
                raise ValueError("상세 페이지 링크가 없습니다.")

            detail_url = requests.compat.urljoin(
                response.url,
                title_link["href"],
            )

            detail_response = request_with_retry(
                detail_url,
                headers=headers,
            )

            # 상세 페이지 한글 깨짐 방지
            detail_response.encoding = "utf-8"

            detail_soup = BeautifulSoup(
                detail_response.text,
                "html.parser",
            )

            car = detail_soup.select_one(
                "div.shell.detail-shell"
            )

            if car is None:
                raise ValueError("상세정보 영역이 없습니다.")

            car_id_text = text_of(
                car,
                "p.product-detail__brand",
            )

            car_detail = []

            for section in car.select(
                "section.detail-section dd"
            ):
                car_detail.append(
                    section.get_text(strip=True)
                )

            if len(car_detail) < 16:
                raise ValueError(
                    f"상세 항목이 부족합니다: "
                    f"{len(car_detail)}개"
                )

            page_data.append({
                "brand_company": text_of(
                    car, "a.product-category"
                ),
                "product_stock": text_of(
                    car, "span[data-field='status']"
                ),
                "car_id": str(
                    row.get("data-car-id") or car_id_text[25:31]
                ),
                "car_UC": car_id_text[5:16],
                "car_price": text_of(
                    car, "data.product-price"
                ),
                "car_rating": text_of(
                    car, "span.product-rating"
                ),
                "car_model": text_of(
                    car, "dl.detail-list dd"
                ),
                "brand_model": car_detail[0],
                "trim": car_detail[1],
                "car_model_year": car_detail[2],
                "first_registration": car_detail[3],
                "mileage": car_detail[4],
                "fuel_transmission": car_detail[5],
                "color": car_detail[6],
                "displacement": car_detail[7],
                "accident_count": car_detail[8],
                "owner_change_count": car_detail[9],
                "inspection_status": car_detail[10],
                "vehicle_location": car_detail[11],
                "sales_manager": car_detail[12],
                "business_area": car_detail[13],
                "registration_date": car_detail[14],
                "api_path": car_detail[15],
            })

        # HTML 구조 또는 값에 문제가 있으면 중단
        except (
            AttributeError,
            KeyError,
            IndexError,
            ValueError,
        ) as error:
            logging.error(
                "URL=%s | Parsing error | %s",
                detail_url,
                error,
            )
            raise

    car_df = pd.DataFrame(page_data)

    if not car_df.empty:
        # 단위와 쉼표를 제거한 후 숫자형으로 변환
        numeric_columns = [
            "car_price",
            "car_model_year",
            "mileage",
            "displacement",
            "accident_count",
            "owner_change_count",
        ]

        for column in numeric_columns:
            car_df[column] = pd.to_numeric(
                car_df[column]
                .astype(str)
                .str.replace(
                    r"[^0-9]",
                    "",
                    regex=True,
                ),
                errors="raise",
            )

        # MySQL DATE 컬럼에 맞게 변환
        date_columns = [
            "first_registration",
            "registration_date",
        ]

        for column in date_columns:
            car_df[column] = pd.to_datetime(
                car_df[column]
                .astype(str)
                .str.replace(
                    r"\.\s*",
                    "-",
                    regex=True,
                )
                .str.rstrip("-"),
                errors="raise",
            ).dt.date

        # 이번 페이지 내부 중복 제거
        car_df = car_df.drop_duplicates(
            subset=["car_id"]
        )

        # MySQL에 이미 존재하는 car_id 제거
        car_df = filter_new_cars(
            car_df,
            engine,
            connection_logger,
        )

        # 최신순이므로 현재 페이지가 전부 기존 데이터면 종료
        if car_df.empty:
            print("새로운 데이터가 없어 수집을 종료합니다.")
            break

        saved_count = save_to_mysql(
            car_df,
            engine,
            connection_logger,
            query_logger,
        )

        total_saved += saved_count

        print(
            f"{saved_count}개 신규 데이터 저장 완료"
        )

    # 현재 페이지 저장을 완료한 뒤 다음 페이지로 이동
    next_link = soup.select_one("a[rel='next']")

    url = (
        requests.compat.urljoin(
            response.url,
            next_link["href"],
        )
        if next_link
        else None
    )
    page += 1

print(f"총 {total_saved}개 신규 데이터 저장 완료")
