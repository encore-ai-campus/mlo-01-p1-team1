import logging
import sys
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

# [포트폴리오 1.8] DB 접속정보 분리
# DB 비밀번호를 소스 코드가 아닌 EC2 내부 파일에서 읽고,
# pool_pre_ping으로 사용 전 DB 연결 상태를 확인하는 코드입니다.
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


# [포트폴리오 1.7] API 및 네트워크 오류 재시도
# 연결 실패·시간 초과·요청 제한·서버 오류가 발생했을 때
# 오류 유형에 맞게 대기한 후 같은 URL을 다시 요청하는 코드입니다.
def request_with_retry(url, headers=None):
    while True:
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=10,
            )

            # [포트폴리오 1.2] 매일 재생성되는 API Key 자동 수집
            # 기존 Key가 만료되어 403 응답이 오면 새로운 Key로 교체하고
            # 현재 요청을 다시 실행하는 코드입니다.
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


# [포트폴리오 1.2] 매일 재생성되는 API Key 자동 수집
# 공개 Key 발급 API에서 현재 유효한 Key를 조회하여
# 모든 차량 API 요청에 사용할 인증 헤더를 만드는 코드입니다.
def get_headers():
    key_response = request_with_retry(
        BASE + "/api/v1/public-key"
    )
    key_info = key_response.json()

    api_key = key_info["data"]["current"]["api_key"]

    return {"X-API-Key": api_key}


# [포트폴리오 1.3] 목록 및 상세 페이지 데이터 수집
# CSS 선택자로 HTML 요소를 조회하고 텍스트를 반환하며,
# 요소가 없으면 페이지 구조 변경을 감지할 수 있도록 예외를 발생시킵니다.
def text_of(node, selector):
    element = node.select_one(selector)

    if element is None:
        raise ValueError(
            f"선택자를 찾을 수 없습니다: {selector}"
        )

    return element.get_text(strip=True)


# [포트폴리오 1.1] 초기 전체 데이터 크롤링
# --full 옵션이면 기존 데이터만 있는 페이지를 만나도 최대 500페이지까지
# 계속 확인하고, 일반 실행이면 최신 데이터 구간만 확인합니다.
headers = get_headers()
url = BASE + "/cars?sort=newest&page=1&page_size=20"
total_saved = 0
page = 1
full_crawl = "--full" in sys.argv

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

    # [포트폴리오 1.3] 목록 및 상세 페이지 데이터 수집
    # 목록의 차량 카드를 순회하면서 상세 페이지 URL을 만들고,
    # 각 상세 페이지의 차량 정보 영역을 파싱하는 코드입니다.
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

            # [포트폴리오 1.4] 차량 데이터 구조화
            # 상세 페이지에서 추출한 차량 속성을 컬럼명과 매핑하여
            # 페이지 단위 DataFrame의 원본 데이터를 구성합니다.
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
        # [포트폴리오 1.5] 숫자 및 날짜 데이터 정제
        # 숫자형 컬럼의 단위와 구분자를 제거한 뒤 DB 저장용 숫자로 변환합니다.
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

        # [포트폴리오 1.5] 숫자 및 날짜 데이터 정제
        # 문자열 날짜의 구분자를 정리하고 MySQL DATE 컬럼에 맞는 값으로 변환합니다.
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

        # [포트폴리오 1.6] 15분마다 신규 데이터만 적재
        # 페이지 내부 중복과 DB에 이미 존재하는 car_id를 제거합니다.
        car_df = car_df.drop_duplicates(
            subset=["car_id"]
        )

        car_df = filter_new_cars(
            car_df,
            engine,
            connection_logger,
        )

        # [포트폴리오 1.1 / 1.6] 전체 적재와 정기 증분 적재 분기
        # --full 모드는 끝까지 순회하고, 15분 주기 일반 모드는
        # 기존 데이터 구간에 도달하면 조기 종료합니다.
        if car_df.empty:
            if not full_crawl:
                print("새로운 데이터가 없어 수집을 종료합니다.")
                break
            print(f"{page}페이지: 저장할 신규 데이터 없음")
        else:
            saved_count = save_to_mysql(
                car_df,
                engine,
                connection_logger,
                query_logger,
            )

            total_saved += saved_count

            print(
                f"{page}페이지: {saved_count}개 신규 데이터 저장 완료"
            )

    # [포트폴리오 1.1] 초기 전체 데이터 크롤링
    # 현재 페이지 저장이 끝난 뒤 next 링크로 다음 페이지를 요청합니다.
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
