import time

from sqlalchemy import bindparam, text
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
    SQLAlchemyError,
)


# [포트폴리오 2.2 - DB 연결 오류 재시도]
# 일시적인 MySQL 연결 장애로 판단하여 재시도할 오류 코드 목록입니다.
NETWORK_ERROR_CODES = {2003, 2006, 2013, 2055}


# [포트폴리오 2.2 - DB 연결 오류 재시도]
# SQLAlchemy 예외 내부에서 실제 MySQL 오류 코드를 추출합니다.
def mysql_error_code(error):
    return getattr(error.orig, "args", [None])[0]


# [포트폴리오 2.2 - 신규 차량 필터링]
# 현재 수집한 car_id 중 DB의 car_data 테이블에 없는 ID만 남겨
# 중복 차량이 INSERT 대상에 포함되지 않도록 하는 코드입니다.
def filter_new_cars(
    car_df, # dataframe
    engine, #
    connection_logger,
    max_retries=3,
):
    if car_df.empty:
        return car_df

    car_ids = car_df["car_id"].astype(str).tolist()
    statement = text(
        "SELECT car_id FROM car_data WHERE car_id IN :car_ids"
    ).bindparams(bindparam("car_ids", expanding=True))

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as connection:
                existing_ids = {
                    str(row[0])
                    for row in connection.execute(
                        statement,
                        {"car_ids": car_ids},
                    )
                }

            return car_df[
                ~car_df["car_id"].astype(str).isin(existing_ids)
            ]

        # [포트폴리오 2.2 - DB 연결 오류 재시도]
        # 기존 ID 조회 중 연결 장애가 발생하면 로그를 남기고,
        # 연결 풀을 폐기한 뒤 3초 간격으로 최대 3회 재시도합니다.
        except OperationalError as error:
            code = mysql_error_code(error)
            connection_logger.error(
                "MySQL code=%s | retry=%s/%s | %s",
                code,
                attempt,
                max_retries,
                error,
            )

            if code in NETWORK_ERROR_CODES and attempt < max_retries:
                engine.dispose()
                time.sleep(3)
                continue
            raise


# [포트폴리오 2.2 - 트랜잭션 기반 저장]
# 신규 차량 DataFrame을 하나의 트랜잭션으로 car_data 테이블에 추가하고,
# 성공하면 저장 건수를 반환하는 코드입니다.
def save_to_mysql(
    car_df,
    engine,
    connection_logger,
    query_logger,
    max_retries=3,
):
    if car_df.empty:
        return 0

    sql_info = (
        f"INSERT INTO car_data "
        f"({', '.join(car_df.columns)}) VALUES (...)"
    )

    for attempt in range(1, max_retries + 1):
        try:
            # [포트폴리오 2.2 - 트랜잭션 기반 저장]
            # 모두 성공하면 자동 커밋되고 오류가 발생하면 자동 롤백됩니다.
            with engine.begin() as connection:
                car_df.to_sql(
                    name="car_data",
                    con=connection,
                    if_exists="append",
                    index=False,
                )
            return len(car_df)

        # [포트폴리오 2.2 - DB 연결 오류 재시도]
        # 저장 중 일시적인 연결 장애가 발생하면 연결 풀을 초기화하고 재시도합니다.
        except OperationalError as error:
            code = mysql_error_code(error)
            connection_logger.error(
                "MySQL code=%s | retry=%s/%s | %s",
                code,
                attempt,
                max_retries,
                error,
            )

            if code in NETWORK_ERROR_CODES and attempt < max_retries:
                engine.dispose()
                time.sleep(3)
                continue
            raise

        # [포트폴리오 2.2 - SQL 오류 분류]
        # PK 중복 코드 1062와 그 밖의 무결성 오류를 구분해 기록합니다.
        except IntegrityError as error:
            code = mysql_error_code(error)
            error_type = "중복 키 오류" if code == 1062 else "무결성 오류"
            query_logger.error(
                "SQL=%s | 오류 형식=%s | MySQL code=%s | %s",
                sql_info,
                error_type,
                code,
                error,
            )
            raise

        # [포트폴리오 2.2 - SQL 오류 분류]
        # 컬럼 크기 초과나 잘못된 값 등 데이터 형식 오류를 기록합니다.
        except DataError as error:
            code = mysql_error_code(error)
            query_logger.error(
                "SQL=%s | 오류 형식=데이터 형식 오류 | MySQL code=%s | %s",
                sql_info,
                code,
                error,
            )
            raise

        # [포트폴리오 2.2 - SQL 오류 분류]
        # 앞에서 분류되지 않은 나머지 SQLAlchemy 오류를 기록합니다.
        except SQLAlchemyError as error:
            query_logger.error(
                "SQL=%s | 오류 형식=기타 SQL 오류 | %s",
                sql_info,
                error,
            )
            raise
