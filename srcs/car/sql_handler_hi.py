# sql_handler.py

import time

from sqlalchemy import text
from sqlalchemy.exc import (
    OperationalError,
    IntegrityError,
    DataError,
    SQLAlchemyError
)


# 재시도할 MySQL 네트워크 오류 코드
NETWORK_ERROR_CODES = {
    2003,  # MySQL 서버 연결 실패
    2006,  # MySQL 서버 연결 끊김
    2013,  # 쿼리 실행 중 연결 끊김
    2055   # MySQL 서버 연결 유실
}


def save_to_mysql(
    car_df,
    engine,
    connection_logger,
    query_logger,
    max_retries=3
):
    """DataFrame을 MySQL에 저장합니다."""

    if car_df.empty:
        return 0

    sql_info = (
        f"INSERT INTO car_data "
        f"({', '.join(car_df.columns)}) VALUES (...)"
    )

    for attempt in range(1, max_retries + 1):
        try:
            # 성공하면 commit, 오류가 발생하면 rollback
            with engine.begin() as connection:
                car_df.to_sql(
                    name="car_data",
                    con=connection,
                    if_exists="append",
                    index=False
                )

            return len(car_df)

        # MySQL 연결 오류
        except OperationalError as error:
            mysql_code = getattr(
                error.orig,
                "args",
                [None]
            )[0]

            connection_logger.error(
                "MySQL code=%s | retry=%s/%s | %s",
                mysql_code,
                attempt,
                max_retries,
                error
            )

            # 네트워크 오류인 경우에만 재시도