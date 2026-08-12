import time

from sqlalchemy import bindparam, text
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
    SQLAlchemyError,
)


NETWORK_ERROR_CODES = {2003, 2006, 2013, 2055}


def mysql_error_code(error):
    return getattr(error.orig, "args", [None])[0]


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
            with engine.begin() as connection:
                car_df.to_sql(
                    name="car_data",
                    con=connection,
                    if_exists="append",
                    index=False,
                )
            return len(car_df)

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

        except DataError as error:
            code = mysql_error_code(error)
            query_logger.error(
                "SQL=%s | 오류 형식=데이터 형식 오류 | MySQL code=%s | %s",
                sql_info,
                code,
                error,
            )
            raise

        except SQLAlchemyError as error:
            query_logger.error(
                "SQL=%s | 오류 형식=기타 SQL 오류 | %s",
                sql_info,
                error,
            )
            raise